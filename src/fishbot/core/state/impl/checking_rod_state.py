import os
import time

from ..bot_state import BotState
from ..state_type import StateType


class CheckingRodState(BotState):
    """Verify a usable rod is equipped and replace it if it's broken.

    The rod slot lives in the fishing HUD. A good rod shows one of the
    flex/sturdy/reg icons; a broken rod shows the `broken_rod` icon. We decide
    using BOTH signals (positive broken detection + absence of a good rod) so a
    broken rod is never mistaken for an OK one.
    """

    GOOD_ROD_TEMPLATES = ("flex_rod", "sturdy_rod", "reg_rod")

    # The click on the new rod lands a touch above-left of the selectable icon,
    # so nudge it down-right (reference px @ 1920x1080, scaled to live size).
    # Tune without rebuilding via env var:  BPSR_ROD_OFFSET="dx,dy"
    DEFAULT_SELECT_OFFSET = (20, 25)

    def __init__(self, bot):
        super().__init__(bot)
        self.select_offset = self._read_offset()

    def _read_offset(self):
        raw = os.environ.get("BPSR_ROD_OFFSET")
        if raw:
            try:
                dx, dy = (int(v.strip()) for v in raw.split(","))
                return (dx, dy)
            except Exception:
                self.bot.log(f"[CHECKING_ROD] ⚠️ Bad BPSR_ROD_OFFSET '{raw}', "
                             "expected 'dx,dy'. Using default.")
        return self.DEFAULT_SELECT_OFFSET

    def _rod_present(self, screen):
        for name in self.GOOD_ROD_TEMPLATES:
            if self.detector.find(screen, name, 5, debug=self.bot.debug_mode):
                return name
        return None

    def handle(self, screen):
        self.bot.log("[CHECKING_ROD] Checking rod...")
        time.sleep(1)

        # Re-capture: the frame handed in predates the settle above (and any
        # animation right after entering fishing), so detection is more reliable
        # on a fresh frame.
        screen = self.detector.capture_screen()

        good = self._rod_present(screen)
        broken = self.detector.find(screen, "broken_rod", 5, debug=self.bot.debug_mode)

        if good and not broken:
            self.bot.log(f"[CHECKING_ROD] ✅ Rod OK ({good})")
            time.sleep(0.5)
            return StateType.CASTING_BAIT

        self.bot.log("[CHECKING_ROD] ⚠️ Broken/missing rod — replacing"
                     f"{' (broken icon detected)' if broken else ''}...")
        self.bot.stats.increment('rod_breaks')
        self._replace_rod()

        # Verify the replacement actually equipped a rod.
        time.sleep(1)
        verify = self.detector.capture_screen()
        if self._rod_present(verify):
            self.bot.log("[CHECKING_ROD] ✅ Rod replaced")
        else:
            self.bot.log("[CHECKING_ROD] ⚠️ Rod still not detected after replacing. "
                         "Check the equip slot / templates (run the Doctor on the "
                         "rod-replace screen to see confidences).")

        return StateType.CASTING_BAIT

    def _apply_offset(self, x, y):
        """Nudge the click target down-right onto the selectable rod icon."""
        dx, dy = self.select_offset
        return (x + int(dx * self.window.scale_x),
                y + int(dy * self.window.scale_y))

    def _replace_rod(self):
        # Open the bag/equip menu.
        self.controller.press_key('m')
        time.sleep(1)

        # Prefer clicking the detected replacement-rod icon; fall back to a
        # resolution-scaled fixed slot if detection fails.
        fresh = self.detector.capture_screen()
        pos = self.detector.find(fresh, "new_rod", 5, debug=self.bot.debug_mode)
        if pos:
            x, y = pos
            self.bot.log(f"[CHECKING_ROD] 🎯 New rod detected at {pos}")
        else:
            x, y = self.window.scale_point(1650, 580)
            self.bot.log("[CHECKING_ROD] ↩️ New rod not detected; using scaled "
                         f"slot ({x}, {y})")

        # Land squarely on the rod icon (down-right nudge; tune via BPSR_ROD_OFFSET).
        x, y = self._apply_offset(x, y)
        self.bot.log(f"[CHECKING_ROD] 🖱️ Selecting rod at ({x}, {y}) "
                     f"[offset {self.select_offset}]")

        self.controller.move_to(x, y)
        time.sleep(0.5)
        self.controller.move_to(x, y)
        time.sleep(0.5)
        self.controller.click('left')
        time.sleep(1)
