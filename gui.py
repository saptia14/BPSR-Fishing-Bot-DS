"""
BPSR Fishing Bot — Demon Soul GUI entry point.

This is the primary application: a single window that runs the Doctor
diagnostics (LOADING -> READY) and the bot (F9 start, F10 stop). The console
`main.py` remains as a fallback.
"""

import os
import sys

# Make `import src.fishbot...` work from source and from a PyInstaller exe.
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# DPI awareness must be set before any window query / capture.
from src.fishbot.utils import winutil
winutil.enable_dpi_awareness()

from src.fishbot.ui.app import run


if __name__ == "__main__":
    run()
