"""Full-keystroke proctoring logger.

Hooks the existing ``keyboard`` library so every key down event becomes a
``KEYSTROKE`` telemetry event. The candidate is told about this on the
splash screen ("All keystrokes are recorded for proctoring"). Dev runs
can opt-out by setting ``KIOSK_DISABLE_KEYLOGGER=1``.

We deliberately do **not** reconstruct typed words/strings - we capture
``{key, scan_code, modifiers, is_blocked, foreground_proc, ts}`` so the
proctor can see *that* the candidate typed but the raw answer text never
hits the database.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from collections import deque
from typing import Optional

try:
    import keyboard  # type: ignore[import-not-found]
except Exception:
    keyboard = None  # type: ignore[assignment]

from .config import get_config
from .event_bus import get_event_bus

_BURST_FLUSH_INTERVAL = 1.0  # seconds - coalesce up to N events into a burst
_BURST_MAX_KEYS = 25         # at most N keystrokes per emitted event
_MODIFIER_KEYS = {"ctrl", "shift", "alt", "left ctrl", "right ctrl",
                  "left shift", "right shift", "left alt", "right alt",
                  "left windows", "right windows"}

_installed = False
_lock = threading.Lock()
_recent_modifiers: set[str] = set()
_pending: deque = deque()
_pending_lock = threading.Lock()
_flush_timer: Optional[threading.Timer] = None


def _foreground_proc_name() -> str:
    """Cheap Win32 foreground-process basename (so we can attribute the keystroke)."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        from ctypes import wintypes  # local import to keep top of file dep-light

        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
        )
        if not h_proc:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(520)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(h_proc)
    except Exception:
        pass
    return ""


def _flush_burst() -> None:
    """Drain the in-process burst queue into a single KEYSTROKE event."""
    global _flush_timer
    with _pending_lock:
        if not _pending:
            _flush_timer = None
            return
        events = list(_pending)
        _pending.clear()
        _flush_timer = None

    try:
        get_event_bus().emit(
            "keystroke",
            payload={"keys": events, "burst_size": len(events)},
            severity="info",
        )
    except Exception:
        pass


def _schedule_flush() -> None:
    global _flush_timer
    with _pending_lock:
        if _flush_timer is not None:
            return
        t = threading.Timer(_BURST_FLUSH_INTERVAL, _flush_burst)
        t.daemon = True
        _flush_timer = t
        t.start()


def _on_key_event(event) -> None:
    """``keyboard`` library callback. Runs on the keyboard hook thread."""
    try:
        # We track modifier state across events so we can tag the emitted
        # KEYSTROKE with the active modifier set without using a full
        # ``keyboard.is_pressed`` (which can be flaky inside the hook).
        name = (getattr(event, "name", None) or "").lower()
        etype = getattr(event, "event_type", "")
        if name in _MODIFIER_KEYS:
            if etype == "down":
                _recent_modifiers.add(name)
            elif etype == "up":
                _recent_modifiers.discard(name)
            return  # don't log bare modifier keys

        if etype != "down":
            return  # log only key-down for KEYSTROKE; key-up is uninteresting

        record = {
            "key": name,
            "scan_code": int(getattr(event, "scan_code", 0) or 0),
            "modifiers": sorted(_recent_modifiers),
            "ts": time.time(),
            "proc": _foreground_proc_name(),
        }

        with _pending_lock:
            if len(_pending) >= _BURST_MAX_KEYS:
                # Force an immediate flush + start a fresh burst.
                events = list(_pending)
                _pending.clear()
                try:
                    get_event_bus().emit(
                        "keystroke",
                        payload={"keys": events, "burst_size": len(events)},
                        severity="info",
                    )
                except Exception:
                    pass
            _pending.append(record)

        _schedule_flush()
    except Exception:
        pass


def install() -> bool:
    """Install the keystroke logger. Returns True if installed."""
    global _installed
    cfg = get_config()
    if not cfg.keylogger_enabled:
        print("[keylogger] disabled via KIOSK_DISABLE_KEYLOGGER")
        return False
    if keyboard is None:
        print("[keylogger] 'keyboard' module not available; skipping")
        return False
    with _lock:
        if _installed:
            return True
        try:
            keyboard.hook(_on_key_event)
            _installed = True
            print("[keylogger] installed (full keystroke capture active)")
            return True
        except Exception as exc:
            print(f"[keylogger] install failed: {exc}")
            return False


def uninstall() -> None:
    global _installed
    with _lock:
        if not _installed:
            return
        try:
            if keyboard is not None:
                keyboard.unhook(_on_key_event)
        except Exception:
            try:
                if keyboard is not None:
                    keyboard.unhook_all()
            except Exception:
                pass
        _installed = False
        print("[keylogger] uninstalled")


def emit_blocked_hotkey(description: str, combo: str = "") -> None:
    """Called by keyblocks.py when a suppressed hotkey is intercepted."""
    try:
        get_event_bus().emit(
            "blocked_hotkey",
            payload={
                "description": description,
                "combo": combo,
                "proc": _foreground_proc_name(),
            },
            severity="warn",
        )
    except Exception:
        pass
