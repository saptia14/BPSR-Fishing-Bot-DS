import time
import sys
import threading
import argparse
import io

# --- FIX: Forçar UTF-8 na consola para suportar emojis no Windows ---
# Isto resolve o erro: UnicodeEncodeError: 'charmap' codec...
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# ------------------------------------------------------------------

from bot.src.fishbot.core.fishing_bot import FishingBot
from bot.src.fishbot.core.game.hotkeys import Hotkeys
from bot.src.fishbot.utils.logger import log


def listen_for_commands(bot, hotkeys):
    """
    Escuta comandos vindos da UI (Electron) via stdin
    """
    while not bot.is_stopped():
        try:
            # Le a linha enviada pelo Electron
            line = sys.stdin.readline()
            if not line:
                break

            command = line.strip()

            if command == "stop":
                hotkeys._stop()
            elif command == "toggle_roi":
                hotkeys._toggle_visualizer()
            elif command == "pause":
                hotkeys.paused = True
                log("[UI] Bot PAUSADO via Interface.")
            elif command == "resume":
                hotkeys.paused = False
                log("[UI] Bot RETOMADO via Interface.")

        except Exception as e:
            log(f"[ERRO] Falha ao ler comando: {e}")
            break


def main():
    # 1. Configurar Argumentos (Configuracoes vindas da UI)
    parser = argparse.ArgumentParser()
    parser.add_argument("--autostart", action="store_true", help="Inicia a pesca automaticamente")
    parser.add_argument("--precision", type=float, default=0.65, help="Precisao da deteccao (0.0 a 1.0)")
    parser.add_argument("--casting_delay", type=float, default=0.5, help="Delay antes de lancar a isca")
    parser.add_argument("--fps", type=int, default=0, help="Target FPS (0 = ilimitado)")

    args = parser.parse_args()

    # 2. Inicializar Bot
    bot = FishingBot()

    # 3. Aplicar Configuracoes (Overrides)
    bot.config.bot.detection.precision = args.precision
    bot.config.bot.casting_delay = args.casting_delay
    bot.config.bot.target_fps = args.fps

    # 4. Inicializar Hotkeys
    hotkeys = Hotkeys(bot, autostart=args.autostart)

    # 5. Iniciar Thread de Escuta da UI
    cmd_thread = threading.Thread(target=listen_for_commands, args=(bot, hotkeys), daemon=True)
    cmd_thread.start()

    bot.start()

    if not args.autostart:
        log("[INFO] Pressione '7' ou use a UI para iniciar.")
    else:
        log(f"[CONFIG] Precisao: {args.precision} | Delay Lancamento: {args.casting_delay}s")

    # Loop Principal
    while not bot.is_stopped():
        if not hotkeys.paused:
            bot.update()
        time.sleep(0.1)

    log("[INFO] Bot finalizado.")


if __name__ == "__main__":
    main()