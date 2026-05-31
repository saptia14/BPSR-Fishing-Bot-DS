import time

from .base_interceptor import BaseInterceptor
from ..state.state_type import StateType


class LevelCheckInterceptor(BaseInterceptor):
    """Guard rail: if the 'level check' UI appears mid-cycle, abandon whatever
    we were doing and re-sync from a known-good state."""

    def check(self, screen):
        if not self.detector.find(screen, "level_check"):
            return False

        self.bot.log("[GUARD RAIL] ⚠️ 'Level Check' UI detected — resyncing.")
        self.controller.release_all_controls()

        # Clear any in-progress minigame direction so we don't resume holding.
        minigame = self.bot.state_machine.states.get(StateType.PLAYING_MINIGAME)
        if minigame is not None and hasattr(minigame, "_current_direction"):
            minigame._current_direction = None

        self.bot.state_machine.set_state(StateType.CHECKING_ROD, force=True)
        time.sleep(1)
        return True
