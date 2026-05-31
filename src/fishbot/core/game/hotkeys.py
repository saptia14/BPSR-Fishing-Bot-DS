import keyboard
import multiprocessing
from src.fishbot.utils.logger import log

class Hotkeys:
    def __init__(self, bot):
        self.bot = bot
        self.paused = True
        self.visualizer_process = None
        self._register_hotkeys()

    def _register_hotkeys(self):
        keyboard.add_hotkey('f9', self._toggle_pause)
        keyboard.add_hotkey('f10', self._stop)
        keyboard.add_hotkey('f8', self._toggle_visualizer)
        log("[INFO] ✅ Hotkeys registered: F9 (Start/Pause), F10 (Stop), F8 (ROI Visualizer)")

    def _toggle_pause(self):
        self.paused = not self.paused
        status = "PAUSED" if self.paused else "RUNNING"
        log(f"[HOTKEY] Bot {status}.")

    def _stop(self):
        log("[HOTKEY] Stopping the bot...")
        if self.visualizer_process and self.visualizer_process.is_alive():
            self.visualizer_process.terminate()
        self.bot.stop()

    def _toggle_visualizer(self):
        if self.visualizer_process and self.visualizer_process.is_alive():
            log("[HOTKEY] Closing the ROI visualizer.")
            self.visualizer_process.terminate()
            self.visualizer_process = None
        else:
            # Imported lazily so the bot (and the packaged .exe) can run without
            # PyQt6 installed; the visualizer is an optional dev tool.
            try:
                from src.fishbot.utils.roi_visualizer import main as show_roi_visualizer
            except Exception as e:
                log(f"[HOTKEY] ⚠️ ROI visualizer unavailable (PyQt6 missing?): {e}")
                return
            log("[HOTKEY] Opening the ROI visualizer.")
            # Runs the visualizer in a separate process so it doesn’t block the main UI
            self.visualizer_process = multiprocessing.Process(target=show_roi_visualizer, daemon=True)
            self.visualizer_process.start()

    def wait_for_exit(self):
        """Keeps the script running until the exit hotkey is pressed."""
        keyboard.wait('8')