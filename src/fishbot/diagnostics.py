"""
Shared diagnostics ("Doctor") logic.

`run_diagnostics()` performs every cross-machine sanity check and returns a
structured `DiagReport`. Both the console Doctor (doctor.py) and the GUI use
this, so the diagnosis is identical whether you run the exe headless or click
through the app.
"""

import os
import sys
import platform
from dataclasses import dataclass, field

from src.fishbot.utils import winutil


@dataclass
class DiagReport:
    ok: bool = False
    problems: list = field(default_factory=list)

    # system
    python: str = ""
    os: str = ""
    dpi_scale: float = 1.0
    bot_admin: bool = False
    input_backend: str = ""

    # window / capture
    found: bool = False
    chosen: dict = None
    candidates: list = field(default_factory=list)
    region: tuple = (0, 0, 0, 0)
    scale: tuple = (1.0, 1.0)
    game_elevated: object = None
    game_focused: bool = False
    elevation_mismatch: bool = False

    # detection
    templates: list = field(default_factory=list)  # list of (name, confidence, matched)
    matched_count: int = 0
    annotated_path: str = None

    # the live ScreenConfig (so callers can reuse the detected window)
    screen_config: object = None


def _input_backend():
    try:
        import pydirectinput  # noqa: F401
        return "pydirectinput (scancode)"
    except Exception:
        return "pyautogui only"


def _output_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(os.path.join(__file__, "..", "..")))


def run_diagnostics(save_annotated=False, screen_config=None):
    """Run all checks. Pass an existing ScreenConfig to reuse a detected window
    (e.g. the one the bot is already using)."""
    winutil.enable_dpi_awareness()
    rep = DiagReport()

    # --- system ---
    rep.python = f"{platform.python_version()} ({platform.architecture()[0]})"
    rep.os = platform.platform()
    rep.dpi_scale = winutil.get_dpi_scale()
    rep.bot_admin = winutil.is_admin()
    rep.input_backend = _input_backend()

    # --- window / capture ---
    from src.fishbot.config.screen_config import ScreenConfig
    sc = screen_config or ScreenConfig(verbose=False)
    rep.screen_config = sc
    rep.found = sc.found
    rep.candidates = sc.candidates
    rep.region = (sc.monitor_x, sc.monitor_y, sc.monitor_width, sc.monitor_height)
    rep.scale = (sc.scale_x, sc.scale_y)
    rep.game_focused = sc.is_game_foreground()

    if sc.hwnd:
        rep.chosen = next((w for w in sc.candidates if w["hwnd"] == sc.hwnd), None)
        rep.game_elevated = winutil.is_process_elevated(sc.pid)
        rep.elevation_mismatch = (
            (rep.game_elevated or rep.game_elevated is None) and not rep.bot_admin
        )

    # --- detection ---
    try:
        from src.fishbot.config import Config
        from src.fishbot.core.game.detector import Detector
        config = Config()
        config.bot.screen = sc
        detector = Detector(config)
        screen = detector.capture_screen()
        for name in config.bot.detection.templates:
            p = detector.probe(screen, name)
            rep.templates.append((name, p["confidence"], p["matched"]))
        rep.matched_count = sum(1 for _, _, m in rep.templates if m)
        if save_annotated:
            rep.annotated_path = _save_annotated(screen, detector, config)
    except Exception as e:
        rep.problems.append(f"Detection probe failed: {e}")

    # --- problems summary ---
    if abs(rep.dpi_scale - 1.0) > 0.01:
        rep.problems.append(
            f"Display scaling is {rep.dpi_scale*100:.0f}% (handled by DPI "
            "awareness; verify the annotated screenshot lines up).")
    if not rep.found:
        rep.problems.append(
            "Game window not detected — set BPSR_WINDOW_TITLE or check the "
            "window list.")
    if rep.elevation_mismatch:
        rep.problems.append(
            "Elevation mismatch — the game looks elevated but the bot is not. "
            "Run the bot as Administrator or input will be ignored.")
    if rep.templates and rep.matched_count == 0:
        rep.problems.append(
            "No templates matched — likely the wrong screen (not at a fishing "
            "spot), wrong window/region, or scaling.")

    rep.ok = rep.found and not rep.elevation_mismatch
    return rep


def _save_annotated(screen, detector, config):
    try:
        import cv2 as cv
        annotated = screen.copy()
        for name in config.bot.detection.templates:
            p = detector.probe(screen, name)
            roi = p.get("roi")
            if not roi:
                continue
            x, y, w, h = roi
            color = (0, 200, 0) if p["matched"] else (0, 0, 200)
            cv.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv.putText(annotated, f"{name} {p['confidence']*100:.0f}%",
                       (x, max(0, y - 4)), cv.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        out = os.path.join(_output_dir(), "doctor_report.png")
        cv.imwrite(out, annotated)
        return out
    except Exception:
        return None
