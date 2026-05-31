import time

from .base_interceptor import BaseInterceptor


class FocusGuardInterceptor(BaseInterceptor):
    """Guard rail: only act while the real game client is the foreground window.

    Without this, the bot's simulated clicks/keys land on whatever window is
    focused. If the official launcher (also titled "Blue Protocol") is in front,
    the center-click hits its Play button and spawns a *second* game instance.
    When the game isn't focused we release everything and skip the frame.
    """

    def __init__(self, bot):
        super().__init__(bot)
        self.screen = bot.config.bot.screen
        self._last_log = 0
        self._was_blocked = False

    def check(self, screen):
        if self.screen.is_game_foreground():
            if self._was_blocked:
                self.bot.log("[FOCUS] ✅ Game refocused — resuming.")
                self._was_blocked = False
            return False

        # Game not in focus: make sure we are not holding any input, and wait.
        if not self._was_blocked:
            self.controller.release_all_controls()
            self._was_blocked = True

        now = time.time()
        if now - self._last_log > 5:
            self.bot.log("[FOCUS] ⏸️ Game window not focused — input paused "
                         "(protects the launcher / other apps).")
            self._last_log = now

        time.sleep(0.2)
        return True
