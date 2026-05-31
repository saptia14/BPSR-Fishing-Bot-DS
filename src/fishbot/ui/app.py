"""
BPSR Fishing Bot — Demon Soul GUI.

A single window that integrates the Doctor diagnostics and the bot:

    LOADING  -> runs Doctor diagnostics -> READY
       -> F9 / Start -> LOADING (warm-up) -> FISHING
       -> F10 / Stop -> STOPPED

Global hotkeys: F9 = start / resume, F10 = stop.
"""

import sys

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QPlainTextEdit,
)

from src.fishbot.utils import winutil
from src.fishbot.utils.logger import subscribe
from src.fishbot.diagnostics import run_diagnostics

try:
    import keyboard
except Exception:
    keyboard = None


# Status -> (label text, accent color)
STATUS_STYLE = {
    "LOADING":   ("LOADING…", "#d9a521"),
    "READY":     ("READY", "#2f80ed"),
    "ATTENTION": ("READY — CHECK ISSUES", "#e2742a"),
    "FISHING":   ("FISHING", "#27ae60"),
    "STOPPED":   ("STOPPED", "#7a7f87"),
    "ERROR":     ("ERROR", "#c0392b"),
}


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class DiagnosticsWorker(QThread):
    done = pyqtSignal(object)

    def run(self):
        try:
            rep = run_diagnostics(save_annotated=True)
        except Exception as e:  # never crash the GUI
            rep = None
            self._error = str(e)
        self.done.emit(rep)


class BotThread(QThread):
    status = pyqtSignal(str)
    stats = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._stop = False
        self.bot = None

    def run(self):
        self.status.emit("LOADING")
        try:
            from src.fishbot.core.fishing_bot import FishingBot
            self.bot = FishingBot()
            # Bring the game to the foreground so input reaches it (pressing F9
            # from the GUI would otherwise leave the GUI focused).
            hwnd = getattr(self.bot.config.bot.screen, "hwnd", None)
            if hwnd:
                winutil.focus_window(hwnd)
                self.msleep(300)
            self.bot.start()  # warm-up (initialises capture, ~1s)
        except Exception as e:
            self.status.emit("ERROR")
            from src.fishbot.utils.logger import log
            log(f"[GUI] ❌ Failed to start bot: {e}")
            return

        self.status.emit("FISHING")
        while not self._stop and not self.bot.is_stopped():
            try:
                self.bot.update()
                self.stats.emit(dict(self.bot.stats.stats))
            except Exception as e:
                from src.fishbot.utils.logger import log
                log(f"[GUI] ⚠️ loop error: {e}")
            self.msleep(60)

        try:
            self.bot.stop()
            self.stats.emit(dict(self.bot.stats.stats))
        except Exception:
            pass
        self.status.emit("STOPPED")

    def request_stop(self):
        self._stop = True
        if self.bot:
            try:
                self.bot.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)
    hotkey_start = pyqtSignal()
    hotkey_stop = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BPSR Fishing Bot — Demon Soul")
        self.setMinimumSize(640, 620)
        self.bot_thread = None
        self.last_report = None

        self._build_ui()
        self._apply_theme()

        # Mirror logs into the on-screen console (thread-safe via queued signal).
        self.log_signal.connect(self._append_log)
        self._unsub = subscribe(lambda line: self.log_signal.emit(line))

        # Hotkeys -> Qt signals -> slots (thread-safe).
        self.hotkey_start.connect(self.start_fishing)
        self.hotkey_stop.connect(self.stop_fishing)
        self._register_hotkeys()

        self._set_status("LOADING")
        self.start_btn.setEnabled(False)
        # Kick off diagnostics after the window is shown.
        self.diag = DiagnosticsWorker()
        self.diag.done.connect(self._on_diagnostics)
        self.diag.start()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Status banner
        self.status_label = QLabel("LOADING…")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(22); f.setBold(True)
        self.status_label.setFont(f)
        self.status_label.setObjectName("statusBanner")
        self.status_label.setMinimumHeight(70)
        root.addWidget(self.status_label)

        # Controls
        controls = QHBoxLayout()
        self.start_btn = QPushButton("▶  Start  (F9)")
        self.stop_btn = QPushButton("■  Stop  (F10)")
        self.doctor_btn = QPushButton("🩺  Re-run Doctor")
        self.start_btn.clicked.connect(self.start_fishing)
        self.stop_btn.clicked.connect(self.stop_fishing)
        self.doctor_btn.clicked.connect(self.run_doctor)
        self.stop_btn.setEnabled(False)
        for b in (self.start_btn, self.stop_btn, self.doctor_btn):
            b.setMinimumHeight(40)
            controls.addWidget(b)
        root.addLayout(controls)

        # Diagnostics panel
        diag_box = QGroupBox("Doctor")
        grid = QGridLayout(diag_box)
        self.diag_labels = {}
        rows = ["Game window", "Capture region", "Scale", "Bot admin",
                "Game elevated", "Game focused", "Templates matched", "Issues"]
        for i, name in enumerate(rows):
            key = QLabel(name + ":")
            key.setStyleSheet("color:#9aa0a6;")
            val = QLabel("—")
            val.setWordWrap(True)
            grid.addWidget(key, i, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(val, i, 1)
            self.diag_labels[name] = val
        grid.setColumnStretch(1, 1)
        root.addWidget(diag_box)

        # Stats panel
        stats_box = QGroupBox("Session stats")
        sgrid = QGridLayout(stats_box)
        self.stat_labels = {}
        stat_names = ["cycles", "fish_caught", "fish_escaped", "rod_breaks", "timeouts"]
        titles = ["Cycles", "Caught", "Escaped", "Rod breaks", "Timeouts"]
        for i, (k, t) in enumerate(zip(stat_names, titles)):
            box = QVBoxLayout()
            num = QLabel("0"); num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nf = QFont(); nf.setPointSize(16); nf.setBold(True); num.setFont(nf)
            cap = QLabel(t); cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap.setStyleSheet("color:#9aa0a6;")
            box.addWidget(num); box.addWidget(cap)
            w = QWidget(); w.setLayout(box)
            sgrid.addWidget(w, 0, i)
            self.stat_labels[k] = num
        root.addWidget(stats_box)

        # Log console
        log_box = QGroupBox("Log")
        lv = QVBoxLayout(log_box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setFont(QFont("Consolas", 9))
        lv.addWidget(self.log_view)
        root.addWidget(log_box, 1)

        self.setCentralWidget(central)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#1b1d22; color:#e6e6e6; }
            QGroupBox { border:1px solid #2c2f36; border-radius:8px; margin-top:10px; padding-top:8px; }
            QGroupBox::title { subcontrol-origin: margin; left:10px; color:#9aa0a6; }
            QPushButton { background:#2a2d34; border:1px solid #3a3e46; border-radius:6px;
                          padding:6px 10px; font-weight:600; }
            QPushButton:hover { background:#343842; }
            QPushButton:disabled { color:#666; border-color:#2a2d34; }
            QPlainTextEdit { background:#121317; border:1px solid #2c2f36; border-radius:6px; }
            #statusBanner { border-radius:10px; color:white; }
        """)

    # -- status ------------------------------------------------------------

    def _set_status(self, status):
        text, color = STATUS_STYLE.get(status, (status, "#7a7f87"))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"#statusBanner {{ background:{color}; border-radius:10px; color:white; }}")
        self.current_status = status

    # -- diagnostics -------------------------------------------------------

    def run_doctor(self):
        if self.bot_thread and self.bot_thread.isRunning():
            return
        self._set_status("LOADING")
        self.start_btn.setEnabled(False)
        self.doctor_btn.setEnabled(False)
        self.diag = DiagnosticsWorker()
        self.diag.done.connect(self._on_diagnostics)
        self.diag.start()

    def _on_diagnostics(self, rep):
        self.doctor_btn.setEnabled(True)
        if rep is None:
            self._set_status("ERROR")
            self.diag_labels["Issues"].setText("Diagnostics failed to run.")
            return
        self.last_report = rep

        chosen = rep.chosen
        self.diag_labels["Game window"].setText(
            f"{chosen['title']} [{chosen['class_name']}]" if chosen
            else "NOT FOUND")
        x, y, w, h = rep.region
        self.diag_labels["Capture region"].setText(f"{w}×{h} @ ({x}, {y})")
        self.diag_labels["Scale"].setText(f"x{rep.scale[0]:.3f}, y{rep.scale[1]:.3f}")
        self.diag_labels["Bot admin"].setText(str(rep.bot_admin))
        self.diag_labels["Game elevated"].setText(str(rep.game_elevated))
        self.diag_labels["Game focused"].setText(str(rep.game_focused))
        self.diag_labels["Templates matched"].setText(
            f"{rep.matched_count}/{len(rep.templates)}")
        self.diag_labels["Issues"].setText(
            "\n".join(f"• {p}" for p in rep.problems) if rep.problems
            else "None ✅")

        if rep.found and not rep.elevation_mismatch:
            self._set_status("READY")
        else:
            self._set_status("ATTENTION")
        self.start_btn.setEnabled(True)

    # -- start / stop ------------------------------------------------------

    def start_fishing(self):
        if self.bot_thread and self.bot_thread.isRunning():
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.doctor_btn.setEnabled(False)
        self.bot_thread = BotThread()
        self.bot_thread.status.connect(self._set_status)
        self.bot_thread.stats.connect(self._update_stats)
        self.bot_thread.finished.connect(self._on_bot_finished)
        self.bot_thread.start()

    def stop_fishing(self):
        if self.bot_thread and self.bot_thread.isRunning():
            self.bot_thread.request_stop()

    def _on_bot_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.doctor_btn.setEnabled(True)
        if getattr(self, "current_status", "") != "ERROR":
            self._set_status("STOPPED")

    def _update_stats(self, stats):
        for k, label in self.stat_labels.items():
            label.setText(str(stats.get(k, 0)))

    # -- log ---------------------------------------------------------------

    def _append_log(self, line):
        self.log_view.appendPlainText(line)

    # -- hotkeys -----------------------------------------------------------

    def _register_hotkeys(self):
        if keyboard is None:
            self._append_log("[GUI] ⚠️ 'keyboard' unavailable — F9/F10 hotkeys disabled.")
            return
        try:
            keyboard.add_hotkey("f9", lambda: self.hotkey_start.emit())
            keyboard.add_hotkey("f10", lambda: self.hotkey_stop.emit())
        except Exception as e:
            self._append_log(f"[GUI] ⚠️ could not register hotkeys: {e}")

    def closeEvent(self, event):
        try:
            self.stop_fishing()
            if self.bot_thread:
                self.bot_thread.wait(3000)
        except Exception:
            pass
        try:
            if keyboard is not None:
                keyboard.clear_all_hotkeys()
        except Exception:
            pass
        try:
            self._unsub()
        except Exception:
            pass
        event.accept()


def run():
    winutil.enable_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("BPSR Fishing Bot — Demon Soul")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
