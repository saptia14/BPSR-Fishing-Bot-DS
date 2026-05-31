"""
BPSR Fishing Bot — DEBUG DOCTOR (console)

Self-diagnosis tool. The GUI runs the same checks during its LOADING phase via
src.fishbot.diagnostics; this console version is a fallback for headless use.
"""

import os
import sys
import datetime

# Make `import src.fishbot...` work both from source and from a PyInstaller exe.
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.fishbot.utils import winutil
winutil.enable_dpi_awareness()

from src.fishbot.diagnostics import run_diagnostics


def _hr(title=""):
    print("\n" + "=" * 64)
    if title:
        print(f" {title}")
        print("=" * 64)


def main():
    from src.fishbot import __version__
    print(f"BPSR Fishing Bot — DEBUG DOCTOR  (v{__version__})")
    rep = run_diagnostics(save_annotated=True)

    _hr("SYSTEM")
    print(f"  Date            : {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  Python          : {rep.python}")
    print(f"  OS              : {rep.os}")
    print(f"  Frozen exe      : {getattr(sys, 'frozen', False)}")
    scale_note = "(OK)" if abs(rep.dpi_scale - 1.0) < 0.01 else "(non-100% — DPI awareness is critical)"
    print(f"  Display scale   : {rep.dpi_scale*100:.0f}%  {scale_note}")
    print(f"  Bot is admin    : {rep.bot_admin}")
    print(f"  Input backend   : {rep.input_backend}")

    _hr("VISIBLE WINDOWS (game-like first)")
    if rep.candidates:
        chosen_hwnd = rep.screen_config.hwnd
        for i, w in enumerate(rep.candidates):
            elevated = winutil.is_process_elevated(w["pid"])
            tag = "★ CHOSEN" if w["hwnd"] == chosen_hwnd else ""
            print(f"  [{i}] {tag}")
            print(f"       title : {w['title']!r}")
            print(f"       class : {w['class_name']!r}  pid={w['pid']}  elevated={elevated}")
            print(f"       size  : {w['width']}x{w['height']} @ ({w['rect'][0]},{w['rect'][1]})")
    else:
        print("  ⚠️ No game-like windows found. All visible windows:")
        for w in winutil.list_windows():
            if w["title"]:
                print(f"     - {w['title']!r} [{w['class_name']}] {w['width']}x{w['height']}")

    _hr("CAPTURE REGION")
    x, y, w, h = rep.region
    print(f"  Detected        : {rep.found}")
    print(f"  Region          : {w}x{h} @ ({x}, {y})")
    print(f"  Scale vs 1080p  : x{rep.scale[0]:.3f}, y{rep.scale[1]:.3f}")
    if rep.screen_config.hwnd:
        print(f"  Game elevated   : {rep.game_elevated}")
        if rep.elevation_mismatch:
            print("  ❗ ELEVATION MISMATCH: run the bot as Administrator.")
        print(f"  Game focused    : {rep.game_focused}")

    _hr("TEMPLATE DETECTION (live confidence)")
    for name, conf, matched in rep.templates:
        mark = "MATCH ✅" if matched else "—"
        print(f"  {name:<18} conf {conf*100:5.1f}%  {mark}")
    if rep.annotated_path:
        print(f"\n  🖼️ Annotated screenshot saved: {rep.annotated_path}")

    _hr("SUMMARY")
    if rep.problems:
        print("  ⚠️ Likely issues:")
        for p in rep.problems:
            print(f"     - {p}")
    else:
        print("  ✅ No blocking problems detected.")
    if rep.notes:
        print("\n  ⚠️ REQUIREMENTS:")
        for n in rep.notes:
            print(f"     - {n}")
    print()

    if getattr(sys, "frozen", False):
        try:
            input("Press Enter to close...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
