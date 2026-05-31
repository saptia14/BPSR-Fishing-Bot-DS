"""
Windows platform helpers (ctypes-based, no extra dependencies).

Centralises everything that makes the bot behave correctly across different
Windows machines: DPI awareness, admin/elevation checks, and robust top-level
window discovery (so we attach to the real game client and never to the
official launcher).

Everything degrades gracefully on non-Windows platforms or when a Win32 call
is unavailable, so importing this module never crashes the bot.
"""

import os
import sys
import ctypes
from ctypes import wintypes

# Make console output safe on legacy (cp1252) consoles so emoji in logs never
# raise UnicodeEncodeError. Runs on import, before anything prints.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IS_WINDOWS = os.name == "nt"

# Reference resolution the ROI table and templates are calibrated against.
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080


def _setup_prototypes():
    """Set restype/argtypes for the Win32 calls we use. Without this, ctypes
    defaults to 32-bit int for return values and arguments, which can truncate
    or sign-extend window handles on 64-bit Windows and break comparisons."""
    if not IS_WINDOWS:
        return
    u = ctypes.windll.user32
    HWND, DWORD, BOOL = wintypes.HWND, wintypes.DWORD, wintypes.BOOL
    INT, UINT, LPWSTR = ctypes.c_int, ctypes.c_uint, wintypes.LPWSTR
    PRECT = ctypes.POINTER(wintypes.RECT)
    PPOINT = ctypes.POINTER(wintypes.POINT)
    PDWORD = ctypes.POINTER(DWORD)
    specs = [
        ("GetForegroundWindow", HWND, []),
        ("GetWindowThreadProcessId", DWORD, [HWND, PDWORD]),
        ("IsWindowVisible", BOOL, [HWND]),
        ("GetWindowRect", BOOL, [HWND, PRECT]),
        ("GetClientRect", BOOL, [HWND, PRECT]),
        ("ClientToScreen", BOOL, [HWND, PPOINT]),
        ("GetWindowTextW", INT, [HWND, LPWSTR, INT]),
        ("GetWindowTextLengthW", INT, [HWND]),
        ("GetClassNameW", INT, [HWND, LPWSTR, INT]),
        ("SetForegroundWindow", BOOL, [HWND]),
        ("ShowWindow", BOOL, [HWND, INT]),
        ("AttachThreadInput", BOOL, [DWORD, DWORD, BOOL]),
        ("GetDpiForWindow", UINT, [HWND]),
        ("GetDpiForSystem", UINT, []),
    ]
    for name, restype, argtypes in specs:
        try:
            fn = getattr(u, name)
            fn.restype = restype
            fn.argtypes = argtypes
        except Exception:
            pass


_setup_prototypes()


# ---------------------------------------------------------------------------
# DPI awareness
# ---------------------------------------------------------------------------

def enable_dpi_awareness():
    """Make this process DPI-aware so pywinctl/mss/pyautogui coordinates agree.

    Without this, on a machine using display scaling (125%, 150%, ...) the
    window rectangle, the captured pixels and the click coordinates all
    disagree, and detection silently lands on empty pixels. Must be called
    once, as early as possible, before any capture or window query.

    Returns a short string describing which awareness mode was set.
    """
    if not IS_WINDOWS:
        return "non-windows"

    # Per-Monitor-v2 (best). Available on Windows 10 1703+.
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return "per-monitor-v2"
    except Exception:
        pass

    # Per-Monitor aware (Windows 8.1+).
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE == 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "per-monitor"
    except Exception:
        pass

    # System DPI aware (legacy fallback).
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "system"
    except Exception:
        return "unavailable"


def get_dpi_scale(hwnd=None):
    """Return the display scale factor (1.0 == 100%) for a window/monitor."""
    if not IS_WINDOWS:
        return 1.0
    try:
        if hwnd:
            dpi = ctypes.windll.user32.GetDpiForWindow(wintypes.HWND(hwnd))
        else:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


# ---------------------------------------------------------------------------
# Elevation / admin
# ---------------------------------------------------------------------------

def is_admin():
    """True if the current process runs with administrator rights."""
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    """Relaunch the current program elevated. Returns True if a relaunch was
    triggered (the caller should then exit), False if already admin or failed."""
    if not IS_WINDOWS or is_admin():
        return False
    try:
        params = " ".join(f'"{a}"' for a in sys.argv)
        # SW_SHOWNORMAL = 1
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        return int(rc) > 32
    except Exception:
        return False


def is_process_elevated(pid):
    """Best-effort: is the process behind *pid* running elevated?

    Returns True/False, or None when it can't be determined (e.g. access
    denied, which usually itself means the target is higher-integrity).
    """
    if not IS_WINDOWS or not pid:
        return None

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TOKEN_QUERY = 0x0008
    TokenElevation = 20

    kernel32 = ctypes.windll.kernel32
    advapi32 = ctypes.windll.advapi32

    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_proc:
        return None
    try:
        h_token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(h_proc, TOKEN_QUERY, ctypes.byref(h_token)):
            return None
        try:
            elevation = wintypes.DWORD()
            ret_len = wintypes.DWORD()
            ok = advapi32.GetTokenInformation(
                h_token, TokenElevation,
                ctypes.byref(elevation), ctypes.sizeof(elevation),
                ctypes.byref(ret_len),
            )
            if not ok:
                return None
            return bool(elevation.value)
        finally:
            kernel32.CloseHandle(h_token)
    finally:
        kernel32.CloseHandle(h_proc)


# ---------------------------------------------------------------------------
# Window enumeration / geometry
# ---------------------------------------------------------------------------

def _get_window_text(hwnd):
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _get_pid(hwnd):
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def list_windows(visible_only=True):
    """Enumerate top-level windows as a list of dicts."""
    if not IS_WINDOWS:
        return []

    results = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        if visible_only and not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        title = _get_window_text(hwnd)
        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if visible_only and (w <= 0 or h <= 0):
            return True
        results.append({
            "hwnd": hwnd,
            "title": title,
            "class_name": _get_class_name(hwnd),
            "pid": _get_pid(hwnd),
            "rect": (rect.left, rect.top, rect.right, rect.bottom),
            "width": w,
            "height": h,
        })
        return True

    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
    return results


def get_foreground_hwnd():
    if not IS_WINDOWS:
        return None
    return ctypes.windll.user32.GetForegroundWindow()


def get_foreground_pid():
    """PID that owns the current foreground window, or None."""
    if not IS_WINDOWS:
        return None
    hwnd = get_foreground_hwnd()
    if not hwnd:
        return None
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value or None
    except Exception:
        return None


def is_window_foreground(hwnd):
    if not IS_WINDOWS or not hwnd:
        return True  # can't tell -> don't block input
    return get_foreground_hwnd() == hwnd


def is_pid_foreground(pid):
    """True when the foreground window belongs to *pid*. More robust than HWND
    equality: survives window recreation, child/overlay windows and handle
    quirks (the game's main and active windows can differ)."""
    if not IS_WINDOWS or not pid:
        return True  # can't tell -> don't block input
    fg = get_foreground_pid()
    if fg is None:
        return True
    return fg == pid


def focus_window(hwnd):
    """Best-effort: bring a window to the foreground so input reaches it.
    Useful right before the bot starts acting, so pressing F9 'just works'
    even if the GUI had focus."""
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        user32.ShowWindow(hwnd, SW_RESTORE)
        # AttachThreadInput trick helps SetForegroundWindow succeed across
        # processes when initiated from a different foreground thread.
        fg = user32.GetForegroundWindow()
        cur_tid = user32.GetWindowThreadProcessId(fg, None)
        tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
        if cur_tid and tgt_tid and cur_tid != tgt_tid:
            user32.AttachThreadInput(cur_tid, tgt_tid, True)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(cur_tid, tgt_tid, False)
        else:
            user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def get_client_rect_on_screen(hwnd):
    """Return the *client* (content) area of a window in screen pixels as
    (x, y, width, height). This is the exact region we should capture, with
    no title-bar/border guesswork."""
    if not IS_WINDOWS or not hwnd:
        return None
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    pt = wintypes.POINT(rect.left, rect.top)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None
    return (pt.x, pt.y, w, h)
