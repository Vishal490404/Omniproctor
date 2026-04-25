# OmniProctor Secure Kiosk Browser

Hardened, kiosk-mode Chromium browser used by OmniProctor candidates to take
exams. It runs as a single fullscreen Qt window with:

- A native Windows Filtering Platform (WFP) firewall that allows only the
  kiosk processes to reach the network.
- Keyboard hotkey suppression and gesture/Task-Manager lockdown.
- `WDA_EXCLUDEFROMCAPTURE` + DWM hardening so the kiosk is invisible to
  screen-recorders / Snipping Tool / Teams share on Windows 10 2004+ and
  Windows 11.
- A persistent `QWebEngineProfile` (HTTP disk cache, persistent cookies,
  service workers) so warm starts are fast.
- Strict single-monitor enforcement.
- Auto-grant for camera, microphone, and screen capture.

## Repository layout

```
Browser/
├── browser/
│   ├── main.py                # Application entrypoint
│   ├── web_profile.py         # Persistent QWebEngineProfile + downloads
│   ├── win11_compat.py        # SetWindowDisplayAffinity / DWM helpers
│   ├── keyblocks.py           # Keyboard + gesture lockdown
│   ├── log_setup.py           # File logger (for windowed/protocol launches)
│   ├── protocol_handler.py    # omniproctor-browser:// registration
│   ├── network/
│   │   ├── native_firewall_controller.py
│   │   └── wfp_native.py      # Direct fwpuclnt.dll bindings (the WFP backend)
│   ├── ui/
│   │   ├── top_bar.py         # Branded top bar with status pills + timer
│   │   ├── splash.py          # Branded startup splash
│   │   ├── dialogs.py         # OmniProctorMessageBox themed wrapper
│   │   ├── theme.qss          # Dark-mode QSS (uses @primary/@danger tokens)
│   │   └── theme.py           # QSS loader + asset path resolver
│   └── assets/                # Icons (icon.svg, icon.png, icon.ico, logo)
├── build/
│   ├── omniproctor-kiosk.spec # PyInstaller spec (one-folder)
│   ├── installer.iss          # Inno Setup 6 installer script
│   └── build.ps1              # PyInstaller + Inno one-shot build
├── pyproject.toml
└── README.md  (this file)
```

## Quick start (developer)

```powershell
# Windows 10/11, PowerShell as Administrator (the kiosk needs admin for WFP)
cd Browser
uv sync
uv run python browser\main.py "https://app.example.com/exam/123"
```

Useful flags:

| Flag                       | Effect |
|----------------------------|--------|
| `--no-system-lockdown`     | Skip Task Manager / gesture policy mutation (dev only) |
| `--register-protocol`      | Register `omniproctor-browser://` for the current user and exit |
| `--unregister-protocol`    | Remove the per-user protocol registration |
| `--firewall-recover`       | Wipe orphaned WFP filters from a previous crashed run |

Useful environment variables:

| Variable                   | Effect |
|----------------------------|--------|
| `OMNIPROCTOR_DEV=1`        | Enable insecure dev relaxations (`--ignore-certificate-errors`, etc.) |
| `OMNIPROCTOR_WFP_NO_BLOCK=1` | Diagnostic: skip the catch-all WFP BLOCK rule |
| `KIOSK_DISABLE_KEYLOGGER=1`  | Developer opt-out for the full keystroke recorder (telemetry still emits other events) |
| `OMNIPROCTOR_TELEMETRY_API` | Override the telemetry API base URL (normally embedded in the launch URL) |
| `OMNIPROCTOR_TELEMETRY_TOKEN` | Override the telemetry bearer token (normally embedded in the launch URL) |
| `OMNIPROCTOR_ATTEMPT_ID`     | Override the active attempt id used by the telemetry pipeline |

## Building the installer

Prerequisites:

- Windows 10/11 build host with PowerShell.
- `uv` (https://github.com/astral-sh/uv) on `PATH`.
- Inno Setup 6 (https://jrsoftware.org/isinfo.php) installed at the default
  location, or pass `-InnoSetupPath` to `build.ps1`.
- `browser/assets/icon.ico` present (a 256x256 multi-resolution Windows .ico
  is recommended).

Build:

```powershell
cd Browser
.\build\build.ps1
```

This will:

1. Run `pyinstaller build/omniproctor-kiosk.spec` → `dist/OmniProctorKiosk/`.
2. Run `ISCC.exe build\installer.iss` → `build\Output\OmniProctorKioskSetup-<version>.exe`.

The output installer:

- Installs to `C:\Program Files\OmniProctor\Kiosk\`.
- Registers the `omniproctor-browser://` URL protocol machine-wide.
- Adds a Start Menu shortcut (and optional desktop shortcut).
- On uninstall, removes the install dir, the protocol registration, and the
  per-user kiosk profile under `%LOCALAPPDATA%\OmniProctor\`.

## Distribution via the WebClient

After building, drop the installer into the WebClient's `installers/` directory:

```powershell
Copy-Item .\build\Output\OmniProctorKioskSetup-0.1.0.exe `
          ..\WebClient\installers\OmniProctorKioskSetup.exe -Force
```

Authenticated users can then download it from `/portal/downloads` (admin /
teacher) or `/student/downloads` (student) inside the WebClient frontend.
The WebClient backend serves the installer through
`GET /api/v1/downloads/installer/windows`.

## Proctoring data captured

When the kiosk is launched via `omniproctor-browser://...?api_base=&attempt_id=&token=&...`
(the WebClient does this automatically), a background telemetry pipeline runs
in addition to the kiosk lockdown. All emissions go through a thread-safe
in-process `EventBus` and are batched to the WebClient's
`POST /api/v1/behavior/attempts/{id}/events:batch` endpoint every 5 seconds
(or immediately on a `critical` event).

| Event type             | Severity         | What it captures |
|------------------------|------------------|------------------|
| `FOCUS_LOSS`           | critical / info  | Foreground window left the kiosk. **critical** if the new foreground is any non-system process (browser, AI helper, comm app, remote-control tool, or unknown third-party app). **info** for unavoidable OS popups (UAC, login screen, taskbar shell host). The kiosk's own dialogs are filtered out and never emit FOCUS_LOSS. |
| `FOCUS_REGAIN`         | info             | Kiosk window regained foreground |
| `MONITOR_COUNT_CHANGE` | warn / info      | Number of attached displays changed. Only emitted on a *real* transition (the first observation establishes the baseline silently). `warn` when count > 1, `info` when reverting to a single display. Payload includes `previous_count → count`. |
| `FULLSCREEN_EXIT`      | warn             | Kiosk left fullscreen (rare; the watchdog re-asserts immediately) |
| `RENDERER_CRASH`       | critical         | The web renderer subprocess died — flushed immediately |
| `KEYSTROKE`            | info             | Every key press, batched up to 25 keys per event. Captures `{key, modifiers, foreground_proc, ts}` only — never a reconstructed string |
| `BLOCKED_HOTKEY`       | warn             | A suppressed hotkey (Win, Alt+Tab, Ctrl+Esc, etc.) was attempted |
| `CLIPBOARD_COPY`       | info / warn      | Clipboard contents changed. `warn` for payloads ≥ 200 chars (likely answer dump), `info` for shorter selections. Stores payload length + MIME hint + preview hash, never the raw payload. The signature is seeded with the pre-launch clipboard so stale content doesn't trigger a false copy event. |
| `VM_DETECTED`          | critical         | One-shot at startup; emitted only if VM/VDI indicators (CPUID hypervisor bit, BIOS strings, drivers, hostname patterns) match |
| `SUSPICIOUS_PROCESS`   | critical / warn  | Background scan (every 15 s). **critical** for high-confidence cheating infrastructure: remote-desktop tools (AnyDesk, TeamViewer, RustDesk, HelpWire, Splashtop, Parsec, Chrome Remote Desktop, Quick Assist, Ammyy, Supremo, LiteManager, Radmin, DameWare, ISL Light, Jump Desktop, NinjaRMM, Atera, ConnectWise, ScreenConnect, ZohoAssist, GoToMyPC, NoMachine, MeshCentral, AweRay, AnyViewer, ShowMyPC, AeroAdmin, NetSupport, VNC servers); tunnels (ngrok, cloudflared, tailscale, zerotier, hamachi, wireguard, openvpn, frp, playit, localxpose); cheat tools (Cheat Engine, ArtMoney, x64dbg, OllyDbg, IDA, Ghidra, WPE Pro); network sniffers (Wireshark, Fiddler, Charles, Burp). **warn** for dual-use apps (Discord, Slack, Zoom, Teams, OBS, AutoHotkey, ChatGPT desktop, etc.). |
| `WARNING_DELIVERED`    | info             | Confirms a teacher warning was rendered on the candidate's screen |

The teacher live monitoring page (`/portal/live`) computes a per-attempt
**risk score** from a sliding 60-second window of these events using the
documented weight table in
[`WebClient/app/services/risk_scorer.py`](../WebClient/app/services/risk_scorer.py).
When the score crosses the configured threshold (default 50) the page raises
an auto-popup notification with a "Send Warning" shortcut that pre-opens the
warning composer with a templated message.

### Privacy notice (full keystroke capture)

The kiosk performs **full keystroke capture** during proctored sessions. The
splash screen surfaces this clearly with a one-line consent notice
("All keystrokes are recorded for proctoring"). Storage is metadata-only
(`{key, modifiers, foreground_proc, ts}`) — accidental log dumps will not
trivially leak typed answer text — but the recording itself is exhaustive.
For local development, set `KIOSK_DISABLE_KEYLOGGER=1` to skip the recorder
(other telemetry monitors keep running).

### Manual smoke checklist

After every release build, on the target Windows host:

1. Launch via `omniproctor-browser://...` from the WebClient → kiosk opens
   fullscreen and a `MONITOR_COUNT_CHANGE` event appears in the live
   monitoring page within ~5 seconds.
2. Alt-Tab away → `FOCUS_LOSS` event arrives, page risk band turns warn.
3. Press a blocked hotkey (Win key) → `BLOCKED_HOTKEY` event arrives.
4. Copy text in the page → `CLIPBOARD_COPY` event arrives with payload length
   only (verify no plaintext leaked).
5. From the live page, send a warning → kiosk shows the slide-down banner
   within 3 seconds and `WARNING_DELIVERED` confirms the round trip.
6. End session → Task Manager and gestures are restored within 1 second
   (verify `Ctrl+Shift+Esc` opens Task Manager again).

## Code signing (out of scope, but recommended)

For production rollouts, sign both the bundled `.exe` (under
`dist/OmniProctorKiosk/`) and the Inno Setup installer with an EV code-signing
certificate. Without a signature, Windows SmartScreen will warn users on first
launch and Defender may flag the WFP / keyboard-hook behaviour.

## Troubleshooting

- **"Network protection failed" / page blank**: the WFP filters need admin
  privileges. Re-launch with `Run as administrator`. If a previous run
  crashed, use `--firewall-recover` (admin) to clear orphaned filters.
- **Task Manager still disabled after exit**: another OmniProctor process is
  still holding a keyboard hook. Kill any stray `pythonw.exe` /
  `OmniProctorKiosk.exe` from Task Manager (or run `--firewall-recover` which
  triggers full cleanup), then re-launch normally to restore the registry.
- **Camera doesn't work**: another app (Teams, Zoom, OBS) might be holding
  the device. Close it, then refresh the kiosk page.
- **Window visible in Snipping Tool / Teams share**: this requires Windows 10
  2004 or newer. On older builds, `WDA_EXCLUDEFROMCAPTURE` silently no-ops.
- **`omniproctor-browser://` link not opening anything**: the installer
  registers the protocol unconditionally per-machine (HKLM). If a prior
  install was uninstalled, simply re-run the installer or, for a quick
  per-user fix without admin rights, run
  `OmniProctorKiosk.exe --register-protocol`.

## License

Proprietary — internal OmniProctor use only.
