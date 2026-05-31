"""
Build standalone Windows executables with PyInstaller.

    python build.py            # build the GUI app: dist\BPSR-Fishing.exe
    python build.py doctor     # also build the console Doctor.exe (optional)
    python build.py all        # build both
    python build.py console     # build the console fallback bot (main.py)

The GUI (BPSR-Fishing.exe) has the Doctor built in, so a separate Doctor.exe
is optional. Detection templates are bundled inside each exe.
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


def _common_args(name, excludes=()):
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile",
        "--name", name,
        "--add-data", DATA,
        "--paths", ROOT,
    ]
    for h in HIDDEN:
        args += ["--hidden-import", h]
    for x in excludes:
        args += ["--exclude-module", x]
    return args


def build_gui():
    print("=== Building BPSR-Fishing.exe (GUI) ===")
    # Windowed app (no console). PyQt6 is collected automatically by its hook.
    args = _common_args("BPSR-Fishing") + ["--windowed", os.path.join(ROOT, "gui.py")]
    subprocess.check_call(args, cwd=ROOT)


def build_doctor():
    print("=== Building Doctor.exe (console) ===")
    # The console Doctor doesn't need PyQt6.
    excludes = ["PyQt6", "PyQt6.sip", "pyqt6_sip", "src.fishbot.utils.roi_visualizer"]
    args = _common_args("Doctor", excludes) + ["--console", os.path.join(ROOT, "doctor.py")]
    subprocess.check_call(args, cwd=ROOT)


def build_console_bot():
    print("=== Building BPSR-Fishing-console.exe ===")
    excludes = ["PyQt6", "PyQt6.sip", "pyqt6_sip", "src.fishbot.utils.roi_visualizer"]
    args = _common_args("BPSR-Fishing-console", excludes) + ["--console", os.path.join(ROOT, "main.py")]
    subprocess.check_call(args, cwd=ROOT)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "gui"
    if target in ("gui", "bot", "all"):
        build_gui()
    if target in ("doctor", "all"):
        build_doctor()
    if target in ("console", "all"):
        build_console_bot()
    print("\n[OK] Done. Executables are in:", os.path.join(ROOT, "dist"))


if __name__ == "__main__":
    main()
