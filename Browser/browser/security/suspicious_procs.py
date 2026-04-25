"""Background scan for known screen-share / remote-control / cheating tools.

Runs on a Qt timer (every 15s) - cheap because we only ask the OS for
process names. We intentionally do NOT iterate ``psutil.process_iter``
to avoid pulling in psutil; ``WMIC`` + ``tasklist`` give us everything
we need on Windows.

The same process won't be reported twice in a row - we keep a tiny
seen-set so we don't flood the bus when the candidate has TeamViewer
running for the whole session.
"""

from __future__ import annotations

import os
import subprocess
from typing import Callable, Iterable

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _hidden_startupinfo():
    """Return a STARTUPINFO that hides the console window on Windows."""
    if os.name != "nt":
        return None
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return si
    except Exception:
        return None

# Lower-cased process names. Keep this list maintainable; teachers can
# extend it via the SUSPICIOUS_PROCS_EXTRA env var (comma-separated).
_DEFAULT_SUSPICIOUS = {
    # Screen-sharing / streaming
    "obs64.exe", "obs32.exe", "obs.exe", "streamlabs obs.exe",
    "xsplit.broadcaster.exe", "xsplit.gamecaster.exe",
    "discord.exe", "discordcanary.exe", "discordptb.exe",
    "zoom.exe", "cpthost.exe", "skype.exe", "msteams.exe", "ms-teams.exe",
    "googlemeet.exe",
    # Remote control / desktop sharing
    "anydesk.exe", "teamviewer.exe", "tv_w32.exe", "tv_x64.exe",
    "rustdesk.exe", "parsecd.exe", "parsec.exe",
    "vnc.exe", "vncserver.exe", "tightvnc.exe", "ultravnc.exe",
    "chrome_remote_desktop.exe", "remoting_host.exe",
    # AI / answer-helper desktop apps (best-effort, common ones)
    "chatgpt.exe", "claude.exe", "perplexity.exe", "copilot.exe",
    "githubcopilot.exe",
    # Generic recording / capture
    "bandicam.exe", "camtasia.exe", "snagit32.exe", "snagit.exe",
    "sharex.exe", "lightshot.exe",
    # macros / cheat
    "autohotkey.exe", "ahk.exe", "cheatengine.exe", "cheatengine-x86_64.exe",
}

_seen_recently: set[str] = set()


def _load_extra() -> set[str]:
    raw = os.environ.get("SUSPICIOUS_PROCS_EXTRA", "").strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _list_running_processes() -> list[str]:
    """Return a list of running process basenames (lower-cased)."""
    try:
        # ``tasklist /fo csv /nh`` is fast (~80 ms) and bundled on every
        # Windows install. We parse just the first CSV column.
        out = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=3.0,
            creationflags=_CREATE_NO_WINDOW,
            startupinfo=_hidden_startupinfo(),
        ).stdout
    except Exception:
        return []

    procs: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # Expected format: "iexplore.exe","12345","Console","1","12,345 K"
        if line.startswith('"'):
            try:
                name = line.split('","', 1)[0].lstrip('"').lower()
                if name:
                    procs.append(name)
            except Exception:
                continue
    return procs


def scan_once(emit: Callable[[str, dict, str], None]) -> list[str]:
    """Run a single scan + emit SUSPICIOUS_PROCESS events. Returns matches."""
    suspicious = _DEFAULT_SUSPICIOUS | _load_extra()
    running = set(_list_running_processes())
    matches = sorted(suspicious & running)
    if not matches:
        # Process disappeared - allow re-reporting if it comes back.
        _seen_recently.intersection_update(running)
        return []

    new_matches = [m for m in matches if m not in _seen_recently]
    if new_matches:
        try:
            emit(
                "SUSPICIOUS_PROCESS",
                {
                    "processes": new_matches,
                    "all_active_matches": matches,
                },
                "warn",
            )
        except Exception:
            pass
        _seen_recently.update(new_matches)

    # Drop processes from the seen-set when they exit so we re-emit if
    # they come back later in the session.
    _seen_recently.intersection_update(running)
    return new_matches
