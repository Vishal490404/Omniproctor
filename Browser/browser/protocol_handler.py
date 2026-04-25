"""Windows registration for the omniproctor-browser:// URL scheme.

The handler writes per-user registry entries under HKCU\\Software\\Classes so
that no admin elevation is required for registration itself. The browser is
still expected to elevate when launched, but registering / unregistering the
scheme can run as the unprivileged installer or first-launch user.

All functions are no-ops on non-Windows platforms.
"""

from __future__ import annotations

import os
import sys

SCHEME = "omniproctor-browser"
_FRIENDLY_NAME = "URL:OmniProctor Secure Browser"
_BASE_KEY = f"Software\\Classes\\{SCHEME}"


def _is_windows() -> bool:
    return sys.platform == "win32"


def _resolve_pythonw() -> str:
    """Prefer pythonw.exe next to the active interpreter to avoid console flashes."""
    exe_dir = os.path.dirname(sys.executable)
    candidate = os.path.join(exe_dir, "pythonw.exe")
    if os.path.isfile(candidate):
        return candidate
    return sys.executable


def _quote(path: str) -> str:
    return f'"{path}"'


def build_command() -> str:
    """Return the fully-quoted shell\\open\\command line for this process."""
    if getattr(sys, "frozen", False):
        target = os.path.abspath(sys.executable)
        return f'{_quote(target)} "%1"'

    interpreter = _resolve_pythonw()
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "main.py")
    )
    return f'{_quote(interpreter)} {_quote(script)} "%1"'


def _command_target_for_icon() -> str:
    """Path to use for DefaultIcon (no quoting, with ',0' suffix)."""
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return _resolve_pythonw()


def is_registered(expected_command: str | None = None) -> bool:
    """Return True if the scheme is registered (optionally matching expected_command)."""
    if not _is_windows():
        return False

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            f"{_BASE_KEY}\\shell\\open\\command",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "")
    except OSError:
        return False

    if expected_command is None:
        return bool(value)
    return value == expected_command


def register(command: str | None = None) -> bool:
    """Idempotently register the omniproctor-browser:// scheme under HKCU."""
    if not _is_windows():
        return False

    import winreg

    cmd = command or build_command()
    icon_target = _command_target_for_icon()

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _BASE_KEY) as root:
            winreg.SetValueEx(root, "", 0, winreg.REG_SZ, _FRIENDLY_NAME)
            winreg.SetValueEx(root, "URL Protocol", 0, winreg.REG_SZ, "")

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, f"{_BASE_KEY}\\DefaultIcon"
        ) as icon_key:
            winreg.SetValueEx(icon_key, "", 0, winreg.REG_SZ, f"{icon_target},0")

        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, f"{_BASE_KEY}\\shell\\open\\command"
        ) as cmd_key:
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, cmd)
    except OSError as exc:
        print(f"[protocol_handler] register failed: {exc}")
        return False

    print(f"[protocol_handler] registered {SCHEME}:// -> {cmd}")
    return True


def unregister() -> bool:
    """Remove all keys under HKCU\\Software\\Classes\\<SCHEME>."""
    if not _is_windows():
        return False

    import winreg

    subkeys = [
        f"{_BASE_KEY}\\shell\\open\\command",
        f"{_BASE_KEY}\\shell\\open",
        f"{_BASE_KEY}\\shell",
        f"{_BASE_KEY}\\DefaultIcon",
        _BASE_KEY,
    ]

    ok = True
    for sub in subkeys:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
        except FileNotFoundError:
            continue
        except OSError as exc:
            print(f"[protocol_handler] unregister failed for {sub}: {exc}")
            ok = False

    if ok:
        print(f"[protocol_handler] unregistered {SCHEME}://")
    return ok


def ensure_registered() -> bool:
    """Register the scheme only if it isn't already pointing at the current command."""
    if not _is_windows():
        return False

    expected = build_command()
    if is_registered(expected):
        return True
    return register(expected)
