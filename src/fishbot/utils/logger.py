import sys
import time

# Make console output safe on every Windows machine. Legacy consoles use the
# cp1252 codepage, where the emoji used throughout the logs raise
# UnicodeEncodeError and can crash the bot. Reconfigure stdout/stderr to UTF-8
# with replacement so output never crashes, regardless of the user's console.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def log(message):
    timestamp = time.strftime("%H:%M:%S")
    try:
        print(f"[{timestamp}] {message}")
    except Exception:
        # Last-resort fallback if a stream still can't encode the message.
        print(f"[{timestamp}] {message.encode('ascii', 'replace').decode('ascii')}")
