import cv2 as cv
import numpy as np

from src.fishbot.utils.logger import log

try:
    import mss
except ImportError:
    log("[ERROR] ❌ MSS library not found! Install with: pip install mss")
    log("[ERROR] The bot cannot run without MSS.")
    exit(1)


class Detector:
    """Screen capture + OpenCV template matching.

    Performance choices:
      * Template grayscale (and any alpha mask) are computed ONCE at load,
        not on every match.
      * Templates are resized once to the live resolution, so the same PNGs
        calibrated at 1920x1080 work on 1440p / 768p / ultrawide.
      * A small ROI is cropped first, then grayscaled — so we never grayscale
        a full 1080p frame per lookup.
      * A failed ROI match falls back to a single match on a *padded* ROI,
        instead of re-running matchTemplate over hundreds of shifted offsets.
    """

    def __init__(self, config):
        self.unified_config = config
        self.detection_config = config.bot.detection
        self.screen_config = config.bot.screen

        self.scale_x = getattr(self.screen_config, "scale_x", 1.0)
        self.scale_y = getattr(self.screen_config, "scale_y", 1.0)
        self._needs_scaling = abs(self.scale_x - 1.0) > 0.01 or abs(self.scale_y - 1.0) > 0.01

        self.templates = self._load_templates()
        self.sct = None
        self.monitor = {
            'left': self.screen_config.monitor_x,
            'top': self.screen_config.monitor_y,
            'width': self.screen_config.monitor_width,
            'height': self.screen_config.monitor_height
        }

    # -- loading -----------------------------------------------------------

    def _resize(self, img, interp):
        if not self._needs_scaling or img is None:
            return img
        return cv.resize(img, None, fx=self.scale_x, fy=self.scale_y, interpolation=interp)

    def _load_templates(self):
        loaded = {}
        log("[INFO] 📦 Loading templates...")
        if self._needs_scaling:
            log(f"[INFO] 🔍 Scaling templates to live resolution "
                f"(x{self.scale_x:.3f}, y{self.scale_y:.3f})")

        for name in self.detection_config.templates:
            path = self.unified_config.get_template_path(name)
            if not (path and path.exists()):
                log(f"[INFO] ❌ {name} - not found at '{path}'")
                continue

            img = cv.imread(str(path), cv.IMREAD_UNCHANGED)
            if img is None:
                log(f"[INFO] ❌ {name} - failed to read image")
                continue

            mask = None
            if img.ndim == 3 and img.shape[2] == 4:
                log(f"[INFO] ✅ {name} (with transparency mask)")
                mask = img[:, :, 3]
                template_img = cv.cvtColor(img, cv.COLOR_BGRA2BGR)
            else:
                log(f"[INFO] ✅ {name}")
                template_img = img if img.ndim == 3 else cv.cvtColor(img, cv.COLOR_GRAY2BGR)

            # Resize once to the live resolution.
            shrink = self.scale_x < 1.0 or self.scale_y < 1.0
            interp = cv.INTER_AREA if shrink else cv.INTER_LINEAR
            template_img = self._resize(template_img, interp)
            if mask is not None:
                mask = self._resize(mask, cv.INTER_NEAREST)

            # Pre-compute grayscale ONCE (the hot path no longer re-converts).
            template_gray = cv.cvtColor(template_img, cv.COLOR_BGR2GRAY)
            loaded[name] = {
                "gray": template_gray,
                "mask": mask,
                "shape": template_gray.shape[:2],  # (h, w)
            }
        return loaded

    # -- capture -----------------------------------------------------------

    def capture_screen(self):
        if self.sct is None:
            self.sct = mss.mss()
            log("[INFO] ✅ MSS initialized in bot thread")

        screenshot = self.sct.grab(self.monitor)
        img = np.array(screenshot)
        return cv.cvtColor(img, cv.COLOR_BGRA2BGR)

    # -- matching ----------------------------------------------------------

    def _perform_match(self, search_gray, template):
        template_gray = template["gray"]
        if (search_gray.shape[0] < template_gray.shape[0] or
                search_gray.shape[1] < template_gray.shape[1]):
            return None, None

        mask = template["mask"]
        if mask is not None:
            result = cv.matchTemplate(search_gray, template_gray,
                                      cv.TM_CCOEFF_NORMED, mask=mask)
            # Masked matching can yield inf/nan; sanitise before the peak search.
            result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
        else:
            result = cv.matchTemplate(search_gray, template_gray, cv.TM_CCOEFF_NORMED)

        _, confidence, _, location = cv.minMaxLoc(result)
        return confidence, location

    def _resolve_roi(self, template_name, screen_w, screen_h):
        """Return the scaled, clamped ROI (x, y, w, h) for a template, or None
        to search the whole frame."""
        roi_config = self.detection_config.rois.get(template_name)
        if isinstance(roi_config, str):  # alias to another template's ROI
            roi_config = self.detection_config.rois.get(roi_config)
        if not roi_config:
            return None

        x, y, w, h = self.screen_config.scale_rect(roi_config)
        x = max(0, min(x, screen_w - 1))
        y = max(0, min(y, screen_h - 1))
        w = min(w, screen_w - x)
        h = min(h, screen_h - y)
        if w <= 0 or h <= 0:
            return None
        return (x, y, w, h)

    def _calculate_center(self, location, template_shape, roi_offset):
        h_t, w_t = template_shape
        off_x, off_y = roi_offset
        return (
            location[0] + w_t // 2 + off_x + self.screen_config.monitor_x,
            location[1] + h_t // 2 + off_y + self.screen_config.monitor_y,
        )

    def probe(self, screen, template_name):
        """Diagnostic helper: return the best confidence and matched flag for a
        template regardless of the precision threshold. Used by the Doctor."""
        template = self.templates.get(template_name)
        if template is None:
            return {"loaded": False, "confidence": 0.0, "matched": False, "roi": None}

        screen_h, screen_w = screen.shape[:2]
        roi = self._resolve_roi(template_name, screen_w, screen_h)
        x, y, w, h = roi if roi else (0, 0, screen_w, screen_h)
        crop = screen[y:y + h, x:x + w]
        if crop.size == 0:
            return {"loaded": True, "confidence": 0.0, "matched": False, "roi": roi}
        search_gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)
        confidence, _ = self._perform_match(search_gray, template)
        confidence = float(confidence) if confidence is not None else 0.0
        return {
            "loaded": True,
            "confidence": confidence,
            "matched": confidence >= self.detection_config.precision,
            "roi": roi,
        }

    def find(self, screen, template_name, radius=0, debug=False):
        """Locate *template_name* on *screen*. Returns the absolute on-screen
        center (x, y) of the match, or None.

        `radius` (in reference pixels) pads the ROI on a retry, tolerating
        small UI drift with a single extra match instead of a pixel sweep.
        """
        template = self.templates.get(template_name)
        if template is None:
            log(f"[INFO] ❌ Template '{template_name}' was not loaded.")
            return None

        screen_h, screen_w = screen.shape[:2]
        roi = self._resolve_roi(template_name, screen_w, screen_h)

        precision = self.detection_config.precision

        def try_region(x, y, w, h):
            crop = screen[y:y + h, x:x + w]
            if crop.size == 0:
                return None
            search_gray = cv.cvtColor(crop, cv.COLOR_BGR2GRAY)
            confidence, location = self._perform_match(search_gray, template)
            if confidence is None:
                return None
            if debug and confidence >= 0.3:
                status = 'MATCH' if confidence >= precision else 'NO MATCH'
                log(f"[DEBUG] [{template_name}] @({x},{y}) "
                    f"conf {confidence:.2%} (need {precision:.0%}) -> {status}")
            if confidence >= precision:
                return self._calculate_center(location, template["shape"], (x, y))
            return None

        if roi is None:
            return try_region(0, 0, screen_w, screen_h)

        x, y, w, h = roi
        hit = try_region(x, y, w, h)
        if hit is not None or radius <= 0:
            return hit

        # Single padded retry instead of a concentric pixel sweep.
        pad_x = int(radius * self.scale_x)
        pad_y = int(radius * self.scale_y)
        px = max(0, x - pad_x)
        py = max(0, y - pad_y)
        pw = min(screen_w - px, w + 2 * pad_x)
        ph = min(screen_h - py, h + 2 * pad_y)
        return try_region(px, py, pw, ph)
