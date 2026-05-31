"""
Build standalone Windows executables with PyInstaller.

    python build.py            # build both Doctor.exe and BPSR-Fishing.exe
    python build.py doctor     # build only Doctor.exe
    python build.py bot        # build only BPSR-Fishing.exe

Output goes to dist/. Detection templates are bundled inside each exe.
"""

import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
# PyInstaller --add-data uses ';' as the path separator on Windows.
SEP = ";" if os.name == "nt" else ":"
DATA = f"src{os.sep}fishbot{os.sep}assets{SEP}src/fishbot/assets"

# Hidden imports PyInstaller's static analysis can miss.
HIDDEN = ["pydirectinput", "pyautogui", "mss", "cv2", "numpy", "keyboard"]

# The PyQt6 ROI visualizer is an optional dev tool; keep it out of the exe so
# the build is small and doesn't require PyQt6 to be installed.
EXCLUDES = ["PyQt6", "PyQt6.sip", "pyqt6_sip", "src.fishbot.utils.roi_visualizer"]


def _common_args(name):
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile",
        "--name", name,
        "--add-data", DATA,
        "--paths", ROOT,
    ]
    for h in HIDDEN:
        args += ["--hidden-import", h]
    for x in EXCLUDES:
        args += ["--exclude-module", x]
    return args


def build_doctor():
    print("=== Building Doctor.exe ===")
    args = _common_args("Doctor") + ["--console", os.path.join(ROOT, "doctor.py")]
    subprocess.check_call(args, cwd=ROOT)


def build_bot():
    print("=== Building BPSR-Fishing.exe ===")
    args = _common_args("BPSR-Fishing") + ["--console", os.path.join(ROOT, "main.py")]
    subprocess.check_call(args, cwd=ROOT)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target in ("all", "doctor"):
        build_doctor()
    if target in ("all", "bot"):
        build_bot()
    print("\n[OK] Done. Executables are in:", os.path.join(ROOT, "dist"))


if __name__ == "__main__":
    main()
