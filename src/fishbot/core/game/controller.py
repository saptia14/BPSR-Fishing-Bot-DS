import time

import pyautogui as auto

from src.fishbot.utils.logger import log

# DirectX/Unreal games frequently ignore PyAutoGUI's virtual-key events.
# pydirectinput sends hardware scancodes, which the game honors. We use it for
# keyboard input when available and fall back to pyautogui otherwise.
try:
    import pydirectinput
    pydirectinput.FAILSAFE = True
    pydirectinput.PAUSE = 0.02
    _HAS_DIRECTINPUT = True
except Exception:
    pydirectinput = None
    _HAS_DIRECTINPUT = False


class GameController:
    def __init__(self, config):
        self.config = config.bot
        auto.FAILSAFE = True
        auto.PAUSE = 0.05
        if _HAS_DIRECTINPUT:
            log("[CONTROLLER] ✅ Using scancode input (pydirectinput)")
        else:
            log("[CONTROLLER] ⚠️ pydirectinput missing — falling back to "
                "pyautogui keys (some games may ignore them). "
                "Install with: pip install pydirectinput")

        # Track held keys so release_all_controls is always complete.
        self._held_keys = set()
        self._held_buttons = set()

    # -- keyboard ----------------------------------------------------------

    def press_key(self, key):
        log(f"[CONTROLLER] 🔘 Pressing key: {key}")
        if _HAS_DIRECTINPUT:
            pydirectinput.press(key)
        else:
            auto.press(key)
        time.sleep(0.1)

    def key_down(self, key):
        log(f"[CONTROLLER] 🔘 ⬇️ Holding key: {key}")
        self._held_keys.add(key)
        if _HAS_DIRECTINPUT:
            pydirectinput.keyDown(key)
        else:
            auto.keyDown(key)

    def key_up(self, key):
        log(f"[CONTROLLER] 🔘 ⬆️ Releasing key: {key}")
        self._held_keys.discard(key)
        if _HAS_DIRECTINPUT:
            pydirectinput.keyUp(key)
        else:
            auto.keyUp(key)

    # -- mouse (absolute positioning via pyautogui) ------------------------

    def click(self, button='left', clicks=1, interval=0.1):
        log(f"[CONTROLLER] 🖱️ Clicking: {button} ({clicks}x)")
        auto.click(button=button, clicks=clicks, interval=interval)
        time.sleep(0.15)

    def click_at(self, x, y, button='left'):
        log(f"[CONTROLLER] 🖱️ Clicking at ({x}, {y})")
        auto.click(x, y, button=button)
        time.sleep(0.15)

    def move_to(self, x, y):
        log(f"[CONTROLLER] 📍 Moving mouse to: ({x}, {y})")
        auto.moveTo(x, y, duration=0.2)
        time.sleep(0.1)

    def mouse_down(self, button='left'):
        log(f"[CONTROLLER] 🖱️ ⬇️ Holding mouse: {button}")
        self._held_buttons.add(button)
        auto.mouseDown(button=button)
        time.sleep(0.1)

    def mouse_up(self, button='left'):
        log(f"[CONTROLLER] 🖱️ ⬆️ Releasing mouse: {button}")
        self._held_buttons.discard(button)
        auto.mouseUp(button=button)
        time.sleep(0.1)

    # -- safety ------------------------------------------------------------

    def release_all_controls(self):
        log("[CONTROLLER] ⚠️ Releasing all controls...")
        # Release everything we know we are holding, plus the usual suspects,
        # de-duplicated so we don't emit the same key-up twice.
        for button in dict.fromkeys(list(self._held_buttons) + ['left', 'right']):
            try:
                auto.mouseUp(button=button)
            except Exception:
                pass
        self._held_buttons.clear()

        for key in dict.fromkeys(list(self._held_keys) + ['a', 'd', 's', 'w']):
            try:
                self.key_up(key)
            except Exception:
                pass
        self._held_keys.clear()
