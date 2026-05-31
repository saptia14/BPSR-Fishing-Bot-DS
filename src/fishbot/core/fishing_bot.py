import time

from src.fishbot.config import Config
from src.fishbot.core.game.controller import GameController
from src.fishbot.core.game.detector import Detector
from src.fishbot.core.interceptors.level_check_interceptor import LevelCheckInterceptor
from src.fishbot.core.interceptors.focus_guard_interceptor import FocusGuardInterceptor
from src.fishbot.core.state.impl.casting_bait_state import CastingBaitState
from src.fishbot.core.state.impl.checking_rod_state import CheckingRodState
from src.fishbot.core.state.impl.finishing_state import FinishingState
from src.fishbot.core.state.impl.playing_minigame_state import PlayingMinigameState
from src.fishbot.core.state.impl.starting_state import StartingState
from src.fishbot.core.state.impl.waiting_for_bite_state import WaitingForBiteState
from src.fishbot.core.state.state_machine import StateMachine
from src.fishbot.core.state.state_type import StateType
from src.fishbot.core.stats import StatsTracker
from src.fishbot.utils.logger import log


class FishingBot:
    def __init__(self):
        self.config = Config()
        self.stats = StatsTracker()
        self.log = log

        self.detector = Detector(self.config)
        self.controller = GameController(self.config)
        self.state_machine = StateMachine(self)

        self.level_check_interceptor = LevelCheckInterceptor(self)

        # Guard rails, run every frame before the active state (order matters:
        # focus guard first so we never act while the game isn't focused).
        self.interceptors = [
            FocusGuardInterceptor(self),
            self.level_check_interceptor,
        ]

        self._stopped = False
        self.debug_mode = self.config.bot.debug_mode

        self.target_delay = 0
        if self.config.bot.target_fps > 0:
            self.target_delay = 1.0 / self.config.bot.target_fps

        self._register_states()

    def _register_states(self):
        self.state_machine.add_state(StateType.STARTING, StartingState(self))
        self.state_machine.add_state(StateType.CHECKING_ROD, CheckingRodState(self))
        self.state_machine.add_state(StateType.CASTING_BAIT, CastingBaitState(self))
        self.state_machine.add_state(StateType.WAITING_FOR_BITE, WaitingForBiteState(self))
        self.state_machine.add_state(StateType.PLAYING_MINIGAME, PlayingMinigameState(self))
        self.state_machine.add_state(StateType.FINISHING, FinishingState(self))

    def start(self):
        log("[INFO] 🎣 Bot ready!")
        log("[INFO] ⚠️ IMPORTANT: Keep the game in FOCUS (active window)")
        log(f"[INFO] ⚙️ Accuracy: {self.config.bot.detection.precision * 100:.0f}%")
        log(f"[INFO] ⚙️ Target FPS: {'MAX' if self.config.bot.target_fps == 0 else self.config.bot.target_fps}")
        log("[INFO] ⚠️ Warming up detection system...")
        time.sleep(1)  # Allows enough time for the screen capture components to initialize
        self.state_machine.set_state(StateType.STARTING)

    def update(self):
        if self._stopped:
            return

        loop_start = time.time()

        try:
            screen = self.detector.capture_screen()
            self.state_machine.handle(screen)
        except Exception as e:
            # Never let a transient error crash the session or leave keys held.
            self.log(f"[ERROR] ⚠️ Recovered from loop error: {e}")
            try:
                self.controller.release_all_controls()
            except Exception:
                pass
            time.sleep(0.5)

        if self.target_delay > 0:
            loop_time = time.time() - loop_start
            sleep_time = max(0, self.target_delay - loop_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        # Always show stats once
        if not getattr(self, "_stats_shown", False):
            self.stats.show()
            self._stats_shown = True

        # Proceed with shutdown only once
        if not self._stopped:
            self.log("[BOT] 🛑 Shutting down the bot...")
            self._stopped = True

            try:
                self.controller.release_all_controls()
            except Exception as e:
                self.log(f"[ERROR] Failed to release controls: {e}")

    def is_stopped(self):
        return self._stopped