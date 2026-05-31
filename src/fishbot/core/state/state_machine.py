import time

from src.fishbot.utils.logger import log
from .state_type import StateType


class StateMachine:
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config.bot
        self.states = {}
        self.current_state_name = None
        self.current_state = None
        self.state_start_time = None

    def add_state(self, name, state_instance):
        self.states[name] = state_instance

    def set_state(self, new_state_name, force=False):
        if not force and new_state_name == self.current_state_name:
            return

        if new_state_name not in self.states:
            log(f"[ERROR] Attempted to switch to unknown state: {new_state_name}")
            return

        if self.current_state_name is None:
            log(f"[INFO] Starting state machine in: {new_state_name.name}")
        elif new_state_name != self.current_state_name:
            log(f"[INFO] Changing state: {self.current_state_name.name} -> {new_state_name.name}")
        elif force:
            log(f"[INFO] Forcing state reset: {new_state_name.name}")

        self.current_state_name = new_state_name
        self.current_state = self.states[self.current_state_name]
        self.state_start_time = time.time()

        # Let a state reset per-entry data (timers, held directions, ...).
        on_enter = getattr(self.current_state, "on_enter", None)
        if callable(on_enter):
            try:
                on_enter()
            except Exception as e:
                log(f"[ERROR] on_enter for {new_state_name.name} failed: {e}")

    def _check_state_timeout(self):
        timeout_limit = self.config.state_timeouts.get(self.current_state_name.name)
        if not timeout_limit:
            return False

        elapsed_time = time.time() - self.state_start_time
        if elapsed_time > timeout_limit:
            log(f"[TIMEOUT] 🚨 State '{self.current_state_name.name}' exceeded {timeout_limit}s!")
            log("[TIMEOUT] 🚨 Releasing controls and pressing 'ESC' to reset.")

            self.bot.controller.release_all_controls()
            self.bot.controller.press_key('esc')
            time.sleep(0.5)

            self.bot.stats.increment('timeouts')
            self.set_state(StateType.STARTING, force=True)
            return True
        return False

    def _run_interceptors(self, screen):
        """Run cross-cutting guard rails before the active state. If one of
        them handles the frame (e.g. game lost focus, level-check popup), we
        skip normal state handling this tick."""
        for interceptor in getattr(self.bot, "interceptors", []):
            try:
                if interceptor.check(screen):
                    return True
            except Exception as e:
                log(f"[ERROR] Interceptor {type(interceptor).__name__} failed: {e}")
        return False

    def handle(self, screen):
        if self._check_state_timeout():
            return

        if self._run_interceptors(screen):
            return

        new_state_name = self.current_state.handle(screen)
        self.set_state(new_state_name)