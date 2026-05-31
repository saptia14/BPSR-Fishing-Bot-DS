import time

# DPI awareness must be enabled before any window query or screen capture so
# that pywinctl/mss/pyautogui coordinates agree on scaled displays.
from src.fishbot.utils import winutil
winutil.enable_dpi_awareness()

from src.fishbot.core.fishing_bot import FishingBot
from src.fishbot.core.game.hotkeys import Hotkeys
from src.fishbot.utils.logger import log


def _elevation_advisory(bot):
    """Warn if the game is elevated but the bot isn't — in that case Windows
    silently drops our input (UIPI) and nothing seems to happen."""
    screen = bot.config.bot.screen
    if not screen.found or not screen.pid:
        return
    game_elevated = winutil.is_process_elevated(screen.pid)
    bot_admin = winutil.is_admin()
    # game_elevated is None when we can't read the token, which usually itself
    # means the target is higher-integrity than us.
    if (game_elevated or game_elevated is None) and not bot_admin:
        log("[WARN] ⚠️ The game appears to run as Administrator but this bot "
            "does not.")
        log("[WARN] ⚠️ Windows will IGNORE the bot's keypresses/clicks until "
            "you run the bot as Administrator too.")
        log("[WARN] 👉 Close the bot and 'Run as administrator' (or use "
            "run_as_admin.bat).")


def main():
    winutil.enable_dpi_awareness()

    bot = FishingBot()
    _elevation_advisory(bot)

    hotkeys = Hotkeys(bot)
    bot.start()

    log("[INFO] Press F9 to start the bot (console fallback — the GUI is gui.py).")

    try:
        while not bot.is_stopped():
            if not hotkeys.paused:
                bot.update()
            time.sleep(0.1)
    except KeyboardInterrupt:
        log("[INFO] Interrupted by user.")
    finally:
        # Always release inputs and print stats, no matter how we exit.
        bot.stop()

    log("[INFO] Bot finished.")


if __name__ == "__main__":
    main()
