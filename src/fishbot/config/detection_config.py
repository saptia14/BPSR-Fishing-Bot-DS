from .paths import TEMPLATES_PATH

class DetectionConfig:
    def __init__(self):

        self.precision = 0.65

        self.templates_path = str(TEMPLATES_PATH)

        self.templates = {
            "fishing_spot_btn": "fishing_spot_btn.png",
            "broken_rod": "broken_rod.png",
            "new_rod": "new_rod.png",
            "reg_rod": "reg_pole.png",
            "sturdy_rod": "sturdy_pole.png",
            "flex_rod": "flex_pole.png",
            "exclamation": "exclamation.png",
            "left_arrow": "left_arrow.png",
            "right_arrow": "right_arrow.png",
            "failure": "fish_escaped.png",
            "success": "success.png",
            "continue": "continue.png",
            "level_check": "level_check.png",
            "connect_server": "connect.png",
            "no_pole_message": "no_pole_message.png"
        }

        # General Resolutions Config, But Slow Response Time
        # self.rois = {
        #     "fishing_spot": None,
        #     "broken_rod": None,
        #     "new_rod": None,
        #     "exclamation": None,
        #     "left_arrow": None,
        #     "right_arrow": None,
        #     "success": None,
        #     "continue": None,
        #     "level_check": None
        # }

        #FullHD 1080p Config
        self.rois = {
            "fishing_spot_btn": (1400, 540, 121, 55),
            "broken_rod": (1635, 982, 250, 63),
            "reg_rod": (1638, 985, 210, 33),
            "sturdy_rod": (1637, 984, 194, 37),
            "flex_rod": (1637, 984, 204, 36),
            # 'Use' button in the pole panel. The panel lists several poles, each
            # with its own 'Use' button, so the ROI is a tall right-side strip
            # covering wherever the (best-matching) button lands — we click any
            # available one to equip a pole. Tune with the ROI overlay (hotkey 9).
            "new_rod": (1590, 250, 260, 700),
            "exclamation": (929, 438, 52, 142),
            "left_arrow": (740, 490, 220, 100),
            "right_arrow": (960, 490, 220, 100),
            "failure": (973, 630, 702, 101),
            "success": (710, 620, 570, 130),
            "continue": (1439, 942, 306, 75),
            "level_check": (1101, 985, 48, 29),
            "connect_server": (1057, 763, 279, 67),
            # 'Please select the fishing pole you want to use' banner, shown at
            # upper-center when you try to cast with no pole. Generous ROI since
            # it's only used as a recovery safety net.
            "no_pole_message": (640, 60, 640, 140),
        }