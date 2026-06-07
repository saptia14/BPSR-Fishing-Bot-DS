from .screen_config import ScreenConfig
from .detection_config import DetectionConfig

class BotConfig:
    def __init__(self):

        self.screen = ScreenConfig()
        self.detection = DetectionConfig()

        self.state_timeouts = {
            # CHECKING_ROD may open the pole panel and retry the equip a few
            # times, so it needs more headroom than the other states.
            "STARTING": 10,
            "CHECKING_ROD": 45,
            "CASTING_BAIT": 15,
            "WAITING_FOR_BITE": 25,
            "PLAYING_MINIGAME": 30,
            "FINISHING": 10
        }

        # Enable quick finish after the minigame
        self.quick_finish_enabled = False

        self.debug_mode = False

        # Target FPS (frames per second)
        # 0 means unlimited
        self.target_fps = 0

        # Delays (in seconds)
        self.default_delay = 0.5
        self.finish_wait_delay = 0.5
        self.casting_delay = 0.5
