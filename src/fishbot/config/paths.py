import sys
from pathlib import Path

# When bundled by PyInstaller, data files live under sys._MEIPASS. Otherwise
# resolve relative to this source file.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    PACKAGE_ROOT = Path(sys._MEIPASS) / "src" / "fishbot"
else:
    PACKAGE_ROOT = Path(__file__).resolve().parent.parent

ASSETS_PATH = PACKAGE_ROOT / "assets"
TEMPLATES_PATH = ASSETS_PATH / "templates"
