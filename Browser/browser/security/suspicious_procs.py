"""Background scan for known screen-share / remote-control / cheating tools.

Runs on a Qt timer (every 15s) - cheap because we only ask the OS for
process names. We intentionally do NOT iterate ``psutil.process_iter``
to avoid pulling in psutil; ``WMIC`` + ``tasklist`` give us everything
we need on Windows.

The same process won't be reported twice in a row - we keep a tiny
seen-set so we don't flood the bus when the candidate has TeamViewer
running for the whole session.

Severity tiers
==============
* ``critical`` - high-confidence cheating infrastructure: remote
  desktop / screen-share *control* tools (AnyDesk, TeamViewer,
  RustDesk, HelpWire, Splashtop, Parsec, ...), tunneling daemons that
  often back them (ngrok, cloudflared, Hamachi, ZeroTier, Tailscale),
  and outright cheat utilities (CheatEngine, etc.). Seeing any of
  these during an exam is almost never benign and immediately pins
  the candidate to the "critical" risk band.
* ``warn`` - dual-use apps that are *capable* of cheating but are
  routinely on a student's machine for legitimate reasons: Discord,
  Slack, Zoom, Teams, OBS, Bandicam, AutoHotkey, ChatGPT desktop,
  etc. We surface them but don't auto-escalate.
"""

from __future__ import annotations

import os
import subprocess
from typing import Callable

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


# ---------------------------------------------------------------------------
# Watchlists - lower-cased process names. Edit here to tune sensitivity.
# Operators can extend either tier via env vars
# (SUSPICIOUS_PROCS_CRITICAL_EXTRA / SUSPICIOUS_PROCS_WARN_EXTRA), comma-
# separated.
# ---------------------------------------------------------------------------
_CRITICAL_PROCS: dict[str, str] = {
    # === Remote-desktop / remote-control suites ===
    # AnyDesk
    "anydesk.exe": "AnyDesk remote desktop",
    # TeamViewer (multiple binary names depending on version)
    "teamviewer.exe": "TeamViewer",
    "teamviewer_service.exe": "TeamViewer service",
    "teamviewer_desktop.exe": "TeamViewer desktop",
    "teamviewerqs.exe": "TeamViewer QuickSupport",
    "tv_w32.exe": "TeamViewer (32-bit)",
    "tv_x64.exe": "TeamViewer (64-bit)",
    # RustDesk
    "rustdesk.exe": "RustDesk",
    "rustdesk-host.exe": "RustDesk host",
    "rustdesk_server.exe": "RustDesk server",
    # HelpWire
    "helpwire.exe": "HelpWire",
    "helpwire-host.exe": "HelpWire host",
    "helpwirehost.exe": "HelpWire host",
    "helpwireviewer.exe": "HelpWire viewer",
    "helpwire-operator.exe": "HelpWire operator",
    # Parsec
    "parsec.exe": "Parsec",
    "parsecd.exe": "Parsec daemon",
    # Splashtop
    "splashtop.exe": "Splashtop",
    "srclient.exe": "Splashtop streamer client",
    "srservice.exe": "Splashtop streamer service",
    "srfeature.exe": "Splashtop feature",
    "splashtopstreamer.exe": "Splashtop Streamer",
    # AweRay (aka AWERAY Remote)
    "aweray-remote.exe": "AweRay Remote",
    "aweray.exe": "AweRay Remote",
    "awerayremote.exe": "AweRay Remote",
    # LogMeIn
    "logmein.exe": "LogMeIn",
    "logmeinrcsvc.exe": "LogMeIn service",
    "logmeinsystray.exe": "LogMeIn tray",
    # GoToMyPC / GoToAssist
    "g2comm.exe": "GoToMyPC",
    "g2mhost.exe": "GoToMyPC",
    "g2mstart.exe": "GoToMyPC",
    "g2acommunicator.exe": "GoToAssist",
    # Chrome Remote Desktop
    "chrome_remote_desktop.exe": "Chrome Remote Desktop",
    "remoting_host.exe": "Chrome Remote Desktop host",
    "remoting_me2me_host.exe": "Chrome Remote Desktop me2me",
    # NoMachine
    "nxservice.exe": "NoMachine service",
    "nxnode.exe": "NoMachine node",
    "nxplayer.exe": "NoMachine player",
    # Zoho Assist
    "zohours.exe": "Zoho Assist",
    "assist-deluxe.exe": "Zoho Assist",
    "zaservice.exe": "Zoho Assist service",
    # ConnectWise Control / ScreenConnect
    "connectwisechat.exe": "ConnectWise Control",
    "connectwisecontrol.client.exe": "ConnectWise Control client",
    "screenconnect.clientservice.exe": "ScreenConnect",
    "screenconnect.windowsclient.exe": "ScreenConnect Windows client",
    # BeyondTrust / Bomgar
    "bomgar-scc.exe": "BeyondTrust Bomgar",
    "bombomgar.exe": "BeyondTrust Bomgar",
    # Iperius Remote
    "iperiusremote.exe": "Iperius Remote",
    # ShowMyPC
    "showmypc.exe": "ShowMyPC",
    # AnyViewer
    "anyviewer.exe": "AnyViewer",
    "rcclient.exe": "AnyViewer client",
    # DistantDesktop
    "distantdesktop.exe": "DistantDesktop",
    # GetScreen.me
    "getscreen.exe": "GetScreen.me",
    # AeroAdmin
    "aeroadmin.exe": "AeroAdmin",
    # NetSupport Manager (client32 is also used by unrelated tools - but
    # in an exam context the false-positive rate is low enough to keep)
    "client32.exe": "NetSupport Manager",
    # MeshCentral / MeshAgent
    "meshagent.exe": "MeshCentral agent",
    "meshrouter.exe": "MeshCentral router",
    # DWService / DWAgent
    "dwagent.exe": "DWAgent",
    "dwagsvc.exe": "DWAgent service",
    # Atera RMM
    "aterargt.exe": "Atera RMM",
    "ateraagent.exe": "Atera agent",
    # Action1 RMM
    "action1_agent.exe": "Action1 RMM",
    # NinjaOne / NinjaRMM
    "ninjarmmagent.exe": "NinjaRMM agent",
    "ninjarmmagentpatcher.exe": "NinjaRMM patcher",
    # Pulseway / Datto / Kaseya RMM
    "pulseway.exe": "Pulseway RMM",
    "kaseya.exe": "Kaseya RMM",
    "agentmon.exe": "Kaseya agent",
    # Ammyy Admin
    "aa_v3.exe": "Ammyy Admin",
    "ammyy.exe": "Ammyy Admin",
    # Supremo
    "supremo.exe": "Supremo",
    "supremosystem.exe": "Supremo system",
    # LiteManager
    "rmanager.exe": "LiteManager Free",
    "rmserver.exe": "LiteManager server",
    "litemanager.exe": "LiteManager",
    # Radmin
    "radmin.exe": "Radmin",
    "rserver3.exe": "Radmin server",
    "famitrayicon.exe": "Famatech (Radmin)",
    # DameWare
    "dameware.exe": "DameWare",
    "dwrcs.exe": "DameWare service",
    "dwrcc.exe": "DameWare console",
    # Quick Assist (Microsoft remote-help built into Windows 10/11)
    "quickassist.exe": "Microsoft Quick Assist",
    # ISL Online
    "isllight.exe": "ISL Light",
    "isllightservice.exe": "ISL Light service",
    "isl_alwaysonsupport.exe": "ISL AlwaysOn",
    # Jump Desktop
    "jump.exe": "Jump Desktop",
    "jumpconnect.exe": "Jump Desktop Connect",
    # SimpleHelp
    "simplehelp.exe": "SimpleHelp",
    "remote-access.exe": "SimpleHelp remote access",
    # ImpcRemote / Tixeo / RemotePC
    "remotepc.exe": "RemotePC",
    "remotepcservice.exe": "RemotePC service",
    "tixeo.exe": "Tixeo",
    # ScreenLeap
    "screenleap.exe": "Screenleap",
    # VNC family (server side)
    "vnc.exe": "VNC server",
    "vncserver.exe": "VNC server",
    "vncserverui.exe": "RealVNC server",
    "vncserverx64.exe": "RealVNC server (64-bit)",
    "tightvnc.exe": "TightVNC",
    "tvnserver.exe": "TightVNC server",
    "ultravnc.exe": "UltraVNC",
    "winvnc.exe": "UltraVNC server",
    "winvnc4.exe": "UltraVNC server",
    "tigervncserver.exe": "TigerVNC",
    # Mikogo
    "mikogo.exe": "Mikogo",
    # Bitvise SSH (tunnel + xterm sharing)
    "bvssh.exe": "Bitvise SSH client",

    # === Tunnelling / VPN daemons used to back remote-help sessions ===
    "ngrok.exe": "ngrok tunnel",
    "cloudflared.exe": "Cloudflare Tunnel",
    "tailscale.exe": "Tailscale VPN",
    "tailscaled.exe": "Tailscale VPN daemon",
    "tailscale-ipn.exe": "Tailscale IPN",
    "zerotier_desktop_ui.exe": "ZeroTier VPN UI",
    "zerotier-one.exe": "ZeroTier VPN",
    "zerotier-one_x64.exe": "ZeroTier VPN (64-bit)",
    "hamachi.exe": "LogMeIn Hamachi",
    "hamachi-2.exe": "LogMeIn Hamachi 2",
    "hamachi-2-ui.exe": "LogMeIn Hamachi UI",
    "wireguard.exe": "WireGuard VPN",
    "openvpn.exe": "OpenVPN",
    "openvpn-gui.exe": "OpenVPN GUI",
    "openvpnconnect.exe": "OpenVPN Connect",
    "softether.exe": "SoftEther VPN",
    "vpngate.exe": "VPN Gate",
    "frpc.exe": "frp client",
    "frps.exe": "frp server",
    "playit.exe": "playit.gg tunnel",
    "localxpose.exe": "LocalXpose tunnel",
    "serveo.exe": "Serveo tunnel",
    "pinggy.exe": "Pinggy tunnel",
    "expose.exe": "Expose tunnel",

    # === Virtual cameras / screen-pipe tools ===
    "obs-virtualcam.exe": "OBS Virtual Camera",
    "manycam.exe": "ManyCam virtual camera",
    "xsplit.vcam.exe": "XSplit VCam",
    "snap camera.exe": "Snap Camera",

    # === Outright cheat / memory editing tools ===
    "cheatengine.exe": "Cheat Engine",
    "cheatengine-x86_64.exe": "Cheat Engine (64-bit)",
    "cheatengine-i386.exe": "Cheat Engine (32-bit)",
    "wpehook.exe": "WPE Pro packet editor",
    "wallhack.exe": "Generic wallhack",
    "artmoney.exe": "ArtMoney memory editor",
    "ollydbg.exe": "OllyDbg debugger",
    "x64dbg.exe": "x64dbg debugger",
    "x32dbg.exe": "x32dbg debugger",
    "ida.exe": "IDA Pro",
    "ida64.exe": "IDA Pro (64-bit)",
    "ghidra.exe": "Ghidra reverse engineering",

    # === Network sniffers ===
    "wireshark.exe": "Wireshark packet capture",
    "tshark.exe": "Wireshark CLI",
    "fiddler.exe": "Fiddler proxy",
    "fiddler everywhere.exe": "Fiddler Everywhere",
    "charles.exe": "Charles proxy",
    "burpsuite.exe": "Burp Suite",
}


_WARN_PROCS: dict[str, str] = {
    # === Communication / collaboration apps that *can* screen-share ===
    "discord.exe": "Discord",
    "discordcanary.exe": "Discord Canary",
    "discordptb.exe": "Discord PTB",
    "slack.exe": "Slack",
    "zoom.exe": "Zoom",
    "cpthost.exe": "Zoom helper",
    "skype.exe": "Skype",
    "msteams.exe": "Microsoft Teams",
    "ms-teams.exe": "Microsoft Teams",
    "teams.exe": "Microsoft Teams",
    "googlemeet.exe": "Google Meet",
    "whatsapp.exe": "WhatsApp Desktop",
    "telegram.exe": "Telegram Desktop",
    "telegramdesktop.exe": "Telegram Desktop",
    "whereby.exe": "Whereby",
    "jitsi.exe": "Jitsi Meet",
    "wechat.exe": "WeChat",
    "line.exe": "LINE",
    "viber.exe": "Viber",
    "signal.exe": "Signal",
    "googlechat.exe": "Google Chat",
    "webexmta.exe": "Webex",
    "ciscowebexstart.exe": "Webex",

    # === Recording / streaming software ===
    "obs.exe": "OBS Studio",
    "obs64.exe": "OBS Studio (64-bit)",
    "obs32.exe": "OBS Studio (32-bit)",
    "streamlabs obs.exe": "Streamlabs OBS",
    "streamlabs.exe": "Streamlabs",
    "xsplit.broadcaster.exe": "XSplit Broadcaster",
    "xsplit.gamecaster.exe": "XSplit Gamecaster",
    "bandicam.exe": "Bandicam",
    "camtasia.exe": "Camtasia",
    "snagit.exe": "Snagit",
    "snagit32.exe": "Snagit",
    "snagiteditor.exe": "Snagit Editor",
    "sharex.exe": "ShareX",
    "lightshot.exe": "Lightshot",
    "loom.exe": "Loom",
    "vlc.exe": "VLC (capture-capable)",
    "screenpresso.exe": "Screenpresso",
    "greenshot.exe": "Greenshot",
    "flashback.exe": "Flashback recorder",
    "icecreamscreenrecorder.exe": "Icecream Screen Recorder",

    # === AI / answer-helper desktop apps ===
    "chatgpt.exe": "ChatGPT desktop",
    "claude.exe": "Claude desktop",
    "perplexity.exe": "Perplexity desktop",
    "copilot.exe": "Microsoft Copilot",
    "githubcopilot.exe": "GitHub Copilot",
    "monica.exe": "Monica AI",
    "phind.exe": "Phind",
    "you.exe": "You.com",
    "pi.exe": "Pi (Inflection)",
    "poe.exe": "Poe (Quora)",
    "raycast.exe": "Raycast (AI command bar)",
    "msty.exe": "Msty AI",
    "lmstudio.exe": "LM Studio",
    "gpt4all.exe": "GPT4All",
    "ollama.exe": "Ollama",

    # === Macro / automation / hotkey tools ===
    "autohotkey.exe": "AutoHotkey",
    "ahk.exe": "AutoHotkey",
    "autohotkey64.exe": "AutoHotkey (64-bit)",
    "macroexpress.exe": "Macro Express",
    "pulover.exe": "Pulover's Macro Creator",
    "automate.exe": "Automate scripting",
    "tinytask.exe": "TinyTask macro recorder",
    "keymapper.exe": "KeyMapper",

    # === Clipboard managers (potential answer-paste vectors) ===
    "ditto.exe": "Ditto clipboard manager",
    "clipx.exe": "ClipX",
    "clipboardfusion.exe": "ClipboardFusion",
    "1clipboard.exe": "1Clipboard",

    # === VNC viewers (less suspicious than servers) ===
    "tvnviewer.exe": "TightVNC viewer",
    "vncviewer.exe": "VNC viewer",
    "realvnc-viewer.exe": "RealVNC viewer",

    # === Sandboxes / virtualization controllers (host-side hints) ===
    "vboxmanage.exe": "VirtualBox CLI",
    "vmrun.exe": "VMware vmrun",
    "qemu-system-x86_64.exe": "QEMU emulator",
}


_seen_recently: set[str] = set()


def _load_extra(env_var: str) -> set[str]:
    raw = os.environ.get(env_var, "").strip()
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
        if line.startswith('"'):
            try:
                name = line.split('","', 1)[0].lstrip('"').lower()
                if name:
                    procs.append(name)
            except Exception:
                continue
    return procs


def _classify(running: set[str]) -> tuple[list[dict], list[dict]]:
    """Return (critical_matches, warn_matches) as dicts ready for JSON.

    Each match dict has keys: ``name`` (process basename), ``label``
    (human-readable tool name).
    """
    critical_extra = _load_extra("SUSPICIOUS_PROCS_CRITICAL_EXTRA")
    warn_extra = _load_extra("SUSPICIOUS_PROCS_WARN_EXTRA")

    critical: list[dict] = []
    warn: list[dict] = []

    for proc in sorted(running):
        if proc in _CRITICAL_PROCS:
            critical.append({"name": proc, "label": _CRITICAL_PROCS[proc], "tier": "critical"})
        elif proc in critical_extra:
            critical.append({"name": proc, "label": proc, "tier": "critical"})
        elif proc in _WARN_PROCS:
            warn.append({"name": proc, "label": _WARN_PROCS[proc], "tier": "warn"})
        elif proc in warn_extra:
            warn.append({"name": proc, "label": proc, "tier": "warn"})
    return critical, warn


def scan_once(emit: Callable[[str, dict, str], None]) -> list[str]:
    """Run a single scan + emit SUSPICIOUS_PROCESS events. Returns matches.

    Critical-tier processes are emitted as a separate event with
    ``severity="critical"`` so the WebClient can pin the candidate's
    risk score immediately and pop a teacher alert. Warn-tier processes
    keep ``severity="warn"`` (dual-use tools that may be legitimately
    open).
    """
    running = set(_list_running_processes())
    critical_matches, warn_matches = _classify(running)

    critical_names = [m["name"] for m in critical_matches]
    warn_names = [m["name"] for m in warn_matches]

    new_critical = [m for m in critical_matches if m["name"] not in _seen_recently]
    new_warn = [m for m in warn_matches if m["name"] not in _seen_recently]

    if new_critical:
        try:
            emit(
                "SUSPICIOUS_PROCESS",
                {
                    "processes": [m["name"] for m in new_critical],
                    "details": new_critical,
                    "tier": "critical",
                    "all_active_matches": critical_names + warn_names,
                },
                "critical",
            )
        except Exception:
            pass
        _seen_recently.update(m["name"] for m in new_critical)

    if new_warn:
        try:
            emit(
                "SUSPICIOUS_PROCESS",
                {
                    "processes": [m["name"] for m in new_warn],
                    "details": new_warn,
                    "tier": "warn",
                    "all_active_matches": critical_names + warn_names,
                },
                "warn",
            )
        except Exception:
            pass
        _seen_recently.update(m["name"] for m in new_warn)

    # Drop processes from the seen-set when they exit so we re-emit if
    # they come back later in the session.
    _seen_recently.intersection_update(running)
    return [m["name"] for m in (new_critical + new_warn)]
