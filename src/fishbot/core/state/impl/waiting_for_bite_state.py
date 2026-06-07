import time

from ..bot_state import BotState
from ..state_type import StateType


class WaitingForBiteState(BotState):

    def __init__(self, bot):
        super().__init__(bot)
        self._last_wait_log = 0

    def handle(self, screen):

        pos = self.detector.find(screen, "exclamation", 1, debug=self.bot.debug_mode)

        if pos:
            self.bot.log("[WAITING_FOR_BITE] ❗ Fish hooked!")
            self.controller.mouse_down('left')
            return StateType.PLAYING_MINIGAME

        # Safety net: if the no-pole banner is up, we cast without a pole. Recover
        # by going back to equip one — no bite is coming, and waiting would only
        # end in the destructive timeout ESC that closes the fishing UI.
        if self.detector.find(screen, "no_pole_message", 5, debug=self.bot.debug_mode):
            self.controller.release_all_controls()
            self.bot.log("[WAITING_FOR_BITE] ⚠️ No-pole banner detected — going "
                         "back to replace the pole.")
            return StateType.CHECKING_ROD
        else:
            current_time = time.time()
            if current_time - self._last_wait_log > 5:
                self.bot.log("[WAITING_FOR_BITE] ⏳ Waiting for fish...")
                self._last_wait_log = current_time

            return StateType.WAITING_FOR_BITE