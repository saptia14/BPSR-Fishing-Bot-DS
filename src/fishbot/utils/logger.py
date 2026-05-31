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


# Subscribers receive every formatted log line. The GUI registers one to mirror
# logs into its on-screen console. Each subscriber is called as fn(line: str).
_subscribers = []


def subscribe(callback):
    """Register a callback to receive every log line. Returns an unsubscribe fn."""
    _subscribers.append(callback)
    return lambda: _subscribers.remove(callback) if callback in _subscribers else None


def log(message):
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}"
    try:
        print(line)
    except Exception:
        # Last-resort fallback if a stream still can't encode the message.
        line = f"[{timestamp}] {message.encode('ascii', 'replace').decode('ascii')}"
        print(line)
    for cb in list(_subscribers):
        try:
            cb(line)
        except Exception:
            pass
