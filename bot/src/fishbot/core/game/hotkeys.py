import keyboard
import multiprocessing
import sys
from bot.src.fishbot.utils.logger import log
from bot.src.fishbot.utils.roi_visualizer import main as show_roi_visualizer


class Hotkeys:
    def __init__(self, bot, autostart=False):
        self.bot = bot
        self.paused = not autostart
        self.visualizer_process = None
        self._register_hotkeys()

        if autostart:
            log("[INFO] 🚀 Modo Autostart ativado!")

    def _register_hotkeys(self):
        keyboard.add_hotkey('7', self._toggle_pause)
        keyboard.add_hotkey('8', self._stop)
        keyboard.add_hotkey('9', self._toggle_visualizer)
        keyboard.add_hotkey('esc', self._emergency_exit)

        log("[INFO] ✅ Hotkeys: '7' (Pause), '8' (Stop), '9' (ROI), 'ESC' (Sair)")

    def _toggle_pause(self):
        self.paused = not self.paused
        # Estas strings sao lidas pela UI para atualizar o botao
        status = "PAUSADO" if self.paused else "A EXECUTAR"
        log(f"[HOTKEY] Bot {status}.")

    def _stop(self):
        log("[HOTKEY] A parar o bot...")
        self._cleanup()
        self.bot.stop()

    def _emergency_exit(self):
        log("[HOTKEY] 🛑 SAIDA DE EMERGENCIA (ESC) 🛑")
        self._cleanup()
        self.bot.stop()
        sys.exit(0)

    def _toggle_visualizer(self):
        if self.visualizer_process and self.visualizer_process.is_alive():
            log("[HOTKEY] A fechar visualizador ROI.")
            self._cleanup_visualizer()
        else:
            log("[HOTKEY] A abrir visualizador ROI.")
            self.visualizer_process = multiprocessing.Process(target=show_roi_visualizer, daemon=True)
            self.visualizer_process.start()

    def _cleanup_visualizer(self):
        if self.visualizer_process:
            self.visualizer_process.terminate()
            self.visualizer_process = None

    def _cleanup(self):
        self._cleanup_visualizer()