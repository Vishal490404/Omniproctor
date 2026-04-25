"""Windows 10/11 specific window-hardening helpers.

These wrap small ``user32`` / ``dwmapi`` calls used to make the kiosk window
behave correctly under proctoring scenarios on Windows 11:

* ``apply_capture_protection`` calls ``SetWindowDisplayAffinity`` with
  ``WDA_EXCLUDEFROMCAPTURE`` so the kiosk is invisible to screen recorders
  (Snipping Tool, OBS, Teams/Zoom screen share, GameBar, Win+Shift+S, ...).
  Available on Windows 10 2004+ and all Windows 11 builds.

* ``apply_dwm_hardening`` sets a few DWM attributes that defeat Win11 Snap
  Layouts, taskbar previews, and corner peeking on the kiosk window.

All functions are no-ops on non-Windows platforms.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

logger = logging.getLogger(__name__)

WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# DWM attribute IDs (from dwmapi.h).
DWMWA_NCRENDERING_POLICY = 2
DWMWA_DISALLOW_PEEK = 11
DWMWA_EXCLUDED_FROM_PEEK = 12
DWMWA_CLOAK = 13
DWMWA_FORCE_ICONIC_REPRESENTATION = 7
DWMNCRP_DISABLED = 1


def _is_windows() -> bool:
    return sys.platform == "win32"


def apply_capture_protection(hwnd: int) -> bool:
    """Hide the window from screen capture / recording.

    Returns True on success, False if the API is unavailable or fails.
    """
    if not _is_windows() or not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        SetWindowDisplayAffinity = user32.SetWindowDisplayAffinity
        SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        SetWindowDisplayAffinity.restype = wintypes.BOOL
        ok = bool(
            SetWindowDisplayAffinity(wintypes.HWND(hwnd), WDA_EXCLUDEFROMCAPTURE)
        )
        if ok:
            logger.info(
                "WDA_EXCLUDEFROMCAPTURE applied to hwnd=%s "
                "(window hidden from screen capture)",
                hwnd,
            )
        else:
            err = ctypes.get_last_error()
            logger.warning(
                "SetWindowDisplayAffinity failed (lasterror=%d) on hwnd=%s",
                err,
                hwnd,
            )
        return ok
    except Exception as exc:
        logger.warning("apply_capture_protection failed: %s", exc)
        return False


def remove_capture_protection(hwnd: int) -> bool:
    """Restore default capture behaviour (used during clean shutdown)."""
    if not _is_windows() or not hwnd:
        return False
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        return bool(user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), WDA_NONE))
    except Exception:
        return False


def apply_dwm_hardening(hwnd: int) -> bool:
    """Defeat Win11 Snap Layouts hover, peek, and taskbar previews."""
    if not _is_windows() or not hwnd:
        return False
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        DwmSetWindowAttribute = dwmapi.DwmSetWindowAttribute
        DwmSetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        DwmSetWindowAttribute.restype = ctypes.c_long  # HRESULT

        true_val = wintypes.BOOL(1)
        ncrp_disabled = wintypes.DWORD(DWMNCRP_DISABLED)

        any_set = False
        for attr, value, size in (
            (DWMWA_NCRENDERING_POLICY, ncrp_disabled, ctypes.sizeof(ncrp_disabled)),
            (DWMWA_DISALLOW_PEEK, true_val, ctypes.sizeof(true_val)),
            (DWMWA_EXCLUDED_FROM_PEEK, true_val, ctypes.sizeof(true_val)),
            (DWMWA_FORCE_ICONIC_REPRESENTATION, true_val, ctypes.sizeof(true_val)),
        ):
            hr = DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                wintypes.DWORD(attr),
                ctypes.byref(value),
                wintypes.DWORD(size),
            )
            if hr == 0:
                any_set = True
            else:
                logger.debug(
                    "DwmSetWindowAttribute attr=%d returned HRESULT=0x%08X",
                    attr,
                    hr & 0xFFFFFFFF,
                )
        if any_set:
            logger.info(
                "DWM hardening applied to hwnd=%s (peek/snap-layouts disabled)",
                hwnd,
            )
        return any_set
    except Exception as exc:
        logger.warning("apply_dwm_hardening failed: %s", exc)
        return False


def harden_kiosk_window(hwnd: int) -> None:
    """Apply every Win11-friendly hardening trick we know about."""
    apply_capture_protection(hwnd)
    apply_dwm_hardening(hwnd)
