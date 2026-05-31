"""
Screen / capture geometry configuration.

Responsible for locating the *real game client* window (never the official
launcher) and deriving the exact capture region in physical pixels, in a way
that works across resolutions, multi-monitor setups and DPI scaling.

Override hooks (env vars), useful when auto-detection needs help:
    BPSR_WINDOW_TITLE   - regex; force-match the game window by title.
    BPSR_WINDOW_CLASS   - regex; force-match the game window by class name.
"""

import os
import re

from src.fishbot.utils import winutil


class ScreenConfig:
    # Titles that identify the game client (case-insensitive regex, any match).
    GAME_TITLE_PATTERNS = [r"star\s*resonance", r"blue\s*protocol"]

    # Window classes that strongly indicate the real game client. The live
    # "Blue Protocol: Star Resonance" client reports class "UnityWndClass".
    GAME_CLASS_PATTERNS = [r"UnityWndClass", r"unreal"]

    # Anything matching these is the launcher / a browser shell, NOT the game.
    # The official launcher is an Electron/CEF app; clicking inside it is what
    # used to spawn a *second* game instance.
    EXCLUDE_TITLE_PATTERNS = [r"launcher", r"login", r"updater"]
    EXCLUDE_CLASS_PATTERNS = [r"Chrome_WidgetWin", r"CEF", r"Electron"]

    # Minimum sensible game window size to avoid matching tiny helper windows.
    MIN_GAME_WIDTH = 640
    MIN_GAME_HEIGHT = 480

    def __init__(self, verbose=True):
        self.window_title = "Blue Protocol: Star Resonance"
        self.monitor_x = 0
        self.monitor_y = 0
        self.monitor_width = winutil.REFERENCE_WIDTH
        self.monitor_height = winutil.REFERENCE_HEIGHT

        # Populated by detection.
        self.hwnd = None
        self.found = False
        self.pid = None
        self.candidates = []  # all game-like windows we considered

        self._detect(verbose=verbose)

        # Scale factors of the live capture vs the calibrated reference frame.
        self.scale_x = self.monitor_width / winutil.REFERENCE_WIDTH
        self.scale_y = self.monitor_height / winutil.REFERENCE_HEIGHT

    # -- detection ---------------------------------------------------------

    def _matches_any(self, text, patterns):
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _score_window(self, win):
        """Higher score == more likely to be the real game client."""
        title = win["title"] or ""
        cls = win["class_name"] or ""

        if self._matches_any(title, self.EXCLUDE_TITLE_PATTERNS):
            return None
        if self._matches_any(cls, self.EXCLUDE_CLASS_PATTERNS):
            return None
        if win["width"] < self.MIN_GAME_WIDTH or win["height"] < self.MIN_GAME_HEIGHT:
            return None

        title_hit = self._matches_any(title, self.GAME_TITLE_PATTERNS)
        class_hit = self._matches_any(cls, self.GAME_CLASS_PATTERNS)
        if not (title_hit or class_hit):
            return None

        score = 0
        if class_hit:
            score += 1000          # an Unreal client is the strongest signal
        if title_hit:
            score += 500
        score += (win["width"] * win["height"]) // 10000  # prefer the big one
        return score

    def _detect(self, verbose=True):
        # Manual override via env: force a specific title/class regex.
        title_override = os.environ.get("BPSR_WINDOW_TITLE")
        class_override = os.environ.get("BPSR_WINDOW_CLASS")
        if title_override:
            self.GAME_TITLE_PATTERNS = [title_override]
        if class_override:
            self.GAME_CLASS_PATTERNS = [class_override]

        windows = winutil.list_windows(visible_only=True)

        scored = []
        for win in windows:
            score = self._score_window(win)
            if score is not None:
                scored.append((score, win))

        self.candidates = [w for _, w in sorted(scored, key=lambda s: -s[0])]

        if not scored:
            if verbose:
                print("[SCREEN] ⚠️ Game window not found. Using full-screen "
                      f"defaults ({self.monitor_width}x{self.monitor_height} @ 0,0).")
                print("[SCREEN] 💡 Run the Doctor (doctor.py / Doctor.exe) to "
                      "list windows, or set BPSR_WINDOW_TITLE.")
            return

        scored.sort(key=lambda s: -s[0])
        best = scored[0][1]
        self.hwnd = best["hwnd"]
        self.pid = best["pid"]

        client = winutil.get_client_rect_on_screen(self.hwnd)
        if client:
            self.monitor_x, self.monitor_y, self.monitor_width, self.monitor_height = client
        else:
            # Fall back to the full window rect if client rect failed.
            left, top, right, bottom = best["rect"]
            self.monitor_x, self.monitor_y = left, top
            self.monitor_width, self.monitor_height = right - left, bottom - top

        self.found = True
        if verbose:
            print(f"[SCREEN] ✅ Game client: '{best['title']}' "
                  f"[{best['class_name']}] pid={self.pid}")
            print(f"[SCREEN] 📐 Capture region: "
                  f"{self.monitor_width}x{self.monitor_height} "
                  f"@ ({self.monitor_x}, {self.monitor_y})")
            if len(scored) > 1:
                print(f"[SCREEN] ℹ️ {len(scored)} game-like windows found; "
                      "picked the highest-scoring one.")

    # -- helpers used by states / detector ---------------------------------

    def is_game_foreground(self):
        """True when the real game client is the active window (or unknown)."""
        if not self.hwnd:
            return True
        return winutil.is_window_foreground(self.hwnd)

    def scale_point(self, x, y):
        """Scale a reference-resolution (1920x1080) point to live pixels,
        in absolute screen coordinates."""
        return (
            int(x * self.scale_x) + self.monitor_x,
            int(y * self.scale_y) + self.monitor_y,
        )

    def scale_rect(self, rect):
        """Scale a reference-resolution ROI (x, y, w, h) to live capture
        coordinates (relative to the capture region, not absolute screen)."""
        x, y, w, h = rect
        return (
            int(x * self.scale_x),
            int(y * self.scale_y),
            int(w * self.scale_x),
            int(h * self.scale_y),
        )
