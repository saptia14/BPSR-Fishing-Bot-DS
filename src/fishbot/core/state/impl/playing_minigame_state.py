import time

from ..bot_state import BotState
from ..state_type import StateType


class PlayingMinigameState(BotState):

    def __init__(self, bot):
        super().__init__(bot)
        self._current_direction = None
        self.switch_delay = 0.5
        # If neither an arrow nor a result is seen for this long, the catch is
        # almost certainly over (we likely missed the brief success banner).
        # Finish gracefully rather than holding a key until the global 30s
        # timeout fires its ESC, which closes the fishing UI.
        self.inactivity_timeout = 6.0
        self._last_activity = time.time()

    def on_enter(self):
        # Fresh catch: reset the activity timer and any leftover held direction.
        self._last_activity = time.time()
        self._current_direction = None

    def _handle_arrow(self, direction, screen):
        arrow_template = f"{direction}_arrow"
        key_to_press = 'a' if direction == 'left' else 'd'
        key_to_release = 'd' if direction == 'left' else 'a'
        opposite_direction = 'right' if direction == 'left' else 'left'

        if self.detector.find(screen, arrow_template):
            self._last_activity = time.time()  # the minigame is still active
            if self._current_direction is None:
                self.bot.log(f"[MINIGAME] ▶️ Moving to the {direction} (Holding '{key_to_press}')")
                self.controller.key_down(key_to_press)
                self._current_direction = direction
                time.sleep(self.switch_delay)

            if self._current_direction == opposite_direction:
                self.bot.log(f"[MINIGAME] ◀️ Switching to the {direction} (Releasing '{key_to_release}')")
                self.controller.key_up(key_to_release)
                self._current_direction = None
                time.sleep(self.switch_delay)

    def _leave(self, next_state, message):
        self.controller.release_all_controls()
        self._current_direction = None
        self.bot.log(message)
        return next_state

    def _after_catch(self, failed):
        if self.config.quick_finish_enabled:
            self.bot.log("[MINIGAME] ⏩ Quick finishing...")
            self.controller.press_key('esc')
            time.sleep(0.5)
            return StateType.STARTING
        if failed:
            time.sleep(2)
            return StateType.CHECKING_ROD
        return StateType.FINISHING

    def handle(self, screen):
        # 1) Explicit result banners.
        if self.detector.find(screen, "success", 1, debug=False):
            self.bot.stats.increment('fish_caught')
            return self._leave(self._after_catch(failed=False), "[MINIGAME] 🐟 Fish caught!")

        if self.detector.find(screen, "failure", 1, debug=False):
            self.bot.stats.increment('fish_escaped')
            return self._leave(self._after_catch(failed=True), "[MINIGAME] 🐟 Fish got away!")

        # 2) The Continue / results button means the catch already resolved even
        #    if we missed the brief success banner. Go click it — never ESC out.
        if self.detector.find(screen, "continue", 5, debug=False):
            self.bot.stats.increment('fish_caught')
            return self._leave(StateType.FINISHING,
                               "[MINIGAME] ✅ Results screen detected — finishing.")

        # 3) Play the minigame.
        self._handle_arrow('left', screen)
        self._handle_arrow('right', screen)

        # 4) Inactivity fallback: nothing happening -> assume the catch is over
        #    and hand off to FINISHING (which clicks Continue), well before the
        #    destructive global timeout.
        if time.time() - self._last_activity > self.inactivity_timeout:
            return self._leave(StateType.FINISHING,
                               "[MINIGAME] ⏱️ No activity — assuming the catch is "
                               "done, going to finish.")

        return StateType.PLAYING_MINIGAME
