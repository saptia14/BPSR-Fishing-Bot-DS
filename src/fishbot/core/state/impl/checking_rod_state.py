import os
import time

from ..bot_state import BotState
from ..state_type import StateType


class CheckingRodState(BotState):
    """Verify a usable pole is equipped and equip a new one if it's broken.

    The pole slot lives in the fishing HUD. A good pole shows one of the
    flex/sturdy/reg icons; with no pole the HUD shows the "Add a pole [M]"
    button (`broken_rod` template). When you try to cast with no pole the game
    also throws a "Please select the fishing pole you want to use" banner
    (`no_pole_message`).

    Equipping: pressing `M` opens a panel listing the available poles, each with
    its own `Use` button (`new_rod` template). We don't care *which* pole — we
    click any available `Use` to equip one, then verify the HUD no longer shows
    "no pole". We never advance to casting without a confirmed pole, because
    casting with none triggers the banner and, eventually, the destructive ESC.
    """

    GOOD_ROD_TEMPLATES = ("flex_rod", "sturdy_rod", "reg_rod")

    # How many times to (re)open the panel and try to equip before giving up for
    # this visit. If it fails we re-enter CHECKING_ROD rather than cast.
    MAX_REPLACE_ATTEMPTS = 3

    # Optional click nudge on the detected `Use` button center (reference px @
    # 1920x1080, scaled to live size). Default 0,0 = click the detected center.
    # Tune without rebuilding via env var:  BPSR_ROD_OFFSET="dx,dy"
    DEFAULT_SELECT_OFFSET = (0, 0)

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

    def _no_pole(self, screen):
        """Return a label if we positively see we have NO usable pole: either the
        'Add a pole' button in the HUD, or the 'select a fishing pole' banner."""
        if self.detector.find(screen, "broken_rod", 5, debug=self.bot.debug_mode):
            return "add-a-pole button"
        if self.detector.find(screen, "no_pole_message", 5, debug=self.bot.debug_mode):
            return "no-pole banner"
        return None

    def handle(self, screen):
        self.bot.log("[CHECKING_ROD] Checking rod...")
        time.sleep(1)

        # Re-capture: the frame handed in predates the settle above (and any
        # animation right after entering fishing), so detection is more reliable
        # on a fresh frame.
        screen = self.detector.capture_screen()

        good = self._rod_present(screen)
        no_pole = self._no_pole(screen)

        if good and not no_pole:
            self.bot.log(f"[CHECKING_ROD] ✅ Rod OK ({good})")
            time.sleep(0.5)
            return StateType.CASTING_BAIT

        self.bot.log("[CHECKING_ROD] ⚠️ No usable pole"
                     f"{f' ({no_pole})' if no_pole else ''} — equipping a new one...")
        self.bot.stats.increment('rod_breaks')

        if self._equip_pole():
            self.bot.log("[CHECKING_ROD] ✅ Pole equipped")
            time.sleep(0.5)
            return StateType.CASTING_BAIT

        # Could not equip (panel didn't open, click missed, or out of poles). Do
        # NOT cast without a pole — that triggers the 'select a pole' banner and
        # the destructive ESC. Re-enter CHECKING_ROD to try again.
        self.bot.log(f"[CHECKING_ROD] ❌ Could not equip a pole after "
                     f"{self.MAX_REPLACE_ATTEMPTS} attempts. Retrying — make sure "
                     "you still have poles in your bag.")
        return StateType.CHECKING_ROD

    def _apply_offset(self, x, y):
        """Optional nudge on the click target (default none)."""
        dx, dy = self.select_offset
        return (x + int(dx * self.window.scale_x),
                y + int(dy * self.window.scale_y))

    def _panel_use_button(self, screen):
        """Locate any 'Use' button in the open pole panel (None if not open)."""
        return self.detector.find(screen, "new_rod", 10, debug=self.bot.debug_mode)

    def _close_panel(self):
        """Close the pole panel if it's open, using M (the panel's own toggle)
        rather than ESC — so we never risk ESC exiting fishing when the panel is
        already closed."""
        if self._panel_use_button(self.detector.capture_screen()):
            self.controller.press_key('m')
            time.sleep(0.7)

    def _equip_pole(self):
        for attempt in range(1, self.MAX_REPLACE_ATTEMPTS + 1):
            self.bot.log(f"[CHECKING_ROD] 🎒 Opening pole panel "
                         f"(attempt {attempt}/{self.MAX_REPLACE_ATTEMPTS})")
            self.controller.press_key('m')
            time.sleep(1)

            use_pos = self._panel_use_button(self.detector.capture_screen())
            if not use_pos:
                self.bot.log("[CHECKING_ROD] ↩️ Pole panel / 'Use' button not "
                             "found; closing and retrying.")
                self._close_panel()
                continue

            x, y = self._apply_offset(*use_pos)
            self.bot.log(f"[CHECKING_ROD] 🖱️ Clicking 'Use' at ({x}, {y})")
            self.controller.move_to(x, y)
            time.sleep(0.3)
            self.controller.click('left')
            time.sleep(1)

            # Equipping usually closes the panel; make sure it's closed so the
            # HUD is visible for verification and no menu is left up.
            self._close_panel()

            time.sleep(0.5)
            verify = self.detector.capture_screen()
            if self._rod_present(verify) or not self._no_pole(verify):
                return True

            self.bot.log("[CHECKING_ROD] ⚠️ Still no pole after clicking 'Use'; "
                         "retrying.")
        return False
