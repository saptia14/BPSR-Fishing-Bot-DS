"""
BPSR Fishing Bot — DEBUG DOCTOR

A self-diagnosis tool. Run this first when "it doesn't work on my machine".
It reports everything that commonly differs between PCs and makes the bot fail:

  * DPI / display scaling
  * Administrator / elevation mismatch (the silent input-blocking bug)
  * Which windows look like the game vs the launcher
  * The exact capture region and resolution scale
  * A live confidence score for every detection template
  * An annotated screenshot saved next to the program

Build as a standalone Doctor.exe with build.py / build.bat.
"""

import os
import sys
import platform
import datetime

# Make `import src.fishbot...` work both from source and from a PyInstaller exe.
if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.fishbot.utils import winutil
winutil.enable_dpi_awareness()


def _hr(title=""):
    print("\n" + "=" * 64)
    if title:
        print(f" {title}")
        print("=" * 64)


def section_system():
    _hr("SYSTEM")
    print(f"  Date            : {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  Python          : {platform.python_version()} ({platform.architecture()[0]})")
    print(f"  OS              : {platform.platform()}")
    print(f"  Frozen exe      : {getattr(sys, 'frozen', False)}")
    scale = winutil.get_dpi_scale()
    print(f"  Display scale   : {scale*100:.0f}%  {'(OK)' if abs(scale-1.0)<0.01 else '(non-100% — DPI awareness is critical)'}")
    print(f"  Bot is admin    : {winutil.is_admin()}")
    try:
        import pydirectinput  # noqa: F401
        print("  Input backend   : pydirectinput (scancode) ✅")
    except Exception:
        print("  Input backend   : pyautogui only ⚠️ (install pydirectinput)")


def section_windows():
    _hr("VISIBLE WINDOWS (game-like first)")
    from src.fishbot.config.screen_config import ScreenConfig
    sc = ScreenConfig(verbose=False)

    if sc.candidates:
        for i, w in enumerate(sc.candidates):
            elevated = winutil.is_process_elevated(w["pid"])
            tag = "★ CHOSEN" if w["hwnd"] == sc.hwnd else ""
            print(f"  [{i}] {tag}")
            print(f"       title : {w['title']!r}")
            print(f"       class : {w['class_name']!r}  pid={w['pid']}  "
                  f"elevated={elevated}")
            print(f"       size  : {w['width']}x{w['height']} @ "
                  f"({w['rect'][0]},{w['rect'][1]})")
    else:
        print("  ⚠️ No game-like windows found.")
        print("  All visible windows:")
        for w in winutil.list_windows():
            if w["title"]:
                print(f"     - {w['title']!r} [{w['class_name']}] "
                      f"{w['width']}x{w['height']}")
    return sc


def section_capture(sc):
    _hr("CAPTURE REGION")
    if not sc.found:
        print("  ⚠️ Game window NOT detected — using full-screen defaults.")
    print(f"  Detected        : {sc.found}")
    print(f"  Region          : {sc.monitor_width}x{sc.monitor_height} "
          f"@ ({sc.monitor_x}, {sc.monitor_y})")
    print(f"  Scale vs 1080p  : x{sc.scale_x:.3f}, y{sc.scale_y:.3f}")
    if sc.hwnd:
        print(f"  Game elevated   : {winutil.is_process_elevated(sc.pid)}")
        if (winutil.is_process_elevated(sc.pid) or
                winutil.is_process_elevated(sc.pid) is None) and not winutil.is_admin():
            print("  ❗ ELEVATION MISMATCH: game looks elevated, bot is not.")
            print("     -> Input will be ignored. Run the bot as Administrator.")
        print(f"  Game focused    : {sc.is_game_foreground()}")


def section_templates(sc):
    _hr("TEMPLATE DETECTION (live confidence)")
    from src.fishbot.config import Config
    from src.fishbot.core.game.detector import Detector

    config = Config()
    config.bot.screen = sc  # reuse the already-detected screen config
    detector = Detector(config)
    screen = detector.capture_screen()

    rows = []
    for name in config.bot.detection.templates:
        p = detector.probe(screen, name)
        rows.append((name, p))
        if not p["loaded"]:
            mark = "NOT LOADED"
        elif p["matched"]:
            mark = "MATCH ✅"
        else:
            mark = "—"
        print(f"  {name:<18} conf {p['confidence']*100:5.1f}%  "
              f"(need {config.bot.detection.precision*100:.0f}%)  {mark}")

    _save_annotated(screen, detector, config, rows)
    return rows


def _save_annotated(screen, detector, config, rows):
    try:
        import cv2 as cv
        annotated = screen.copy()
        for name, p in rows:
            roi = p.get("roi")
            if not roi:
                continue
            x, y, w, h = roi
            color = (0, 200, 0) if p["matched"] else (0, 0, 200)
            cv.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv.putText(annotated, f"{name} {p['confidence']*100:.0f}%",
                       (x, max(0, y - 4)), cv.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        out_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.dirname(os.path.abspath(__file__))
        out = os.path.join(out_dir, "doctor_report.png")
        cv.imwrite(out, annotated)
        print(f"\n  🖼️ Annotated screenshot saved: {out}")
    except Exception as e:
        print(f"\n  (could not save annotated screenshot: {e})")


def section_summary(sc, rows):
    _hr("SUMMARY")
    problems = []
    if abs(winutil.get_dpi_scale() - 1.0) > 0.01:
        problems.append("Display scaling is not 100% (handled by DPI awareness, "
                        "but verify the annotated screenshot lines up).")
    if not sc.found:
        problems.append("Game window not detected — set BPSR_WINDOW_TITLE or "
                        "check the window list above.")
    if sc.hwnd:
        elev = winutil.is_process_elevated(sc.pid)
        if (elev or elev is None) and not winutil.is_admin():
            problems.append("Elevation mismatch — run the bot as Administrator.")
    matched = sum(1 for _, p in rows if p["matched"])
    if rows and matched == 0:
        problems.append("No templates matched — likely wrong window/region, "
                        "scaling, or you're not on the fishing screen.")

    if problems:
        print("  ⚠️ Likely issues:")
        for p in problems:
            print(f"     - {p}")
    else:
        print("  ✅ No blocking problems detected. "
              "If a specific template reads 0%, open that screen and re-run.")
    print()


def main():
    print("BPSR Fishing Bot — DEBUG DOCTOR")
    try:
        section_system()
        sc = section_windows()
        section_capture(sc)
        rows = section_templates(sc)
        section_summary(sc, rows)
    except Exception as e:
        import traceback
        print("\n[DOCTOR] ❌ Unexpected error during diagnosis:")
        traceback.print_exc()
        _ = e
    finally:
        if not getattr(sys, "frozen", False):
            return
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
