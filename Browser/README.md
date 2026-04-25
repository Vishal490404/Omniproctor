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
