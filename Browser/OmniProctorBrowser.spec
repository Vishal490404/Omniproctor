# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the OmniProctor secure kiosk browser.

Build with:
    uv run pyinstaller OmniProctorBrowser.spec --noconfirm --clean

Output:
    dist/OmniProctorBrowser/OmniProctorBrowser.exe
    dist/OmniProctorBrowser/_internal/...

Key requirements that *must* hold for the kiosk to actually work in
production - if you tweak this file, re-validate each:

  * `--onedir` (collected by COLLECT below). Do NOT switch to onefile -
    the WFP firewall controller resolves QtWebEngineProcess.exe by
    walking sys.executable's directory, and onefile's _MEIxxxx temp
    extraction breaks that path on every launch.

  * `uac_admin=True`. Without an embedded requireAdministrator manifest
    the kiosk launches unelevated, the firewall controller throws
    AdminRightsError, and external traffic is NOT blocked.

  * QtWebEngineProcess.exe and the Qt6/resources + Qt6/translations
    directories must end up under _internal/PyQt6/Qt6/. The
    PyInstaller PyQt6 hook usually handles this, but we explicitly
    request the data files below as belt-and-braces.

  * `keyboard` package data files (DLL hooks for Windows). The hook
    that ships with PyInstaller covers this; collect_submodules is
    here to cover the rare case of a custom site-packages layout.
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# Data files: QtWebEngine resources + our own assets/themes
# ---------------------------------------------------------------------------
datas = []
datas += collect_data_files(
    "PyQt6",
    includes=[
        "Qt6/resources/*",
        "Qt6/translations/qtwebengine_locales/*",
        "Qt6/translations/qt_*.qm",
    ],
)

# Our bundled UI assets (icon, logo, theme).
_asset_pairs = [
    ("browser/assets/icon.ico", "browser/assets"),
    ("browser/assets/icon.svg", "browser/assets"),
    ("browser/assets/logo_white.svg", "browser/assets"),
    ("browser/ui/theme.qss", "browser/ui"),
]
for src, dst in _asset_pairs:
    if os.path.isfile(src):
        datas.append((src, dst))

# ---------------------------------------------------------------------------
# Hidden imports - things PyInstaller's static analysis misses.
# ---------------------------------------------------------------------------
hiddenimports = []
hiddenimports += collect_submodules("keyboard")
hiddenimports += collect_submodules("PyQt6.QtWebEngineCore")
# Telemetry modules are imported lazily inside main.py's safe_exit
# (see: from telemetry import post_attempt_end). PyInstaller usually
# picks these up from the explicit imports at module top, but list them
# explicitly so a future refactor can't silently break the build.
hiddenimports += [
    "telemetry",
    "telemetry.poster",
    "telemetry.event_bus",
    "telemetry.warning_poller",
    "telemetry.keystroke_logger",
    "telemetry.config",
    "security.vm_detect",
    "security.suspicious_procs",
    "network.wfp_native",
    "network.native_firewall_controller",
]

a = Analysis(
    ["browser/main.py"],
    pathex=["browser"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "test", "pytest", "IPython", "jedi"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OmniProctorBrowser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX is incompatible with QtWebEngineProcess.exe
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="browser/assets/icon.ico",
    # Mandatory: bake requireAdministrator into the manifest so the
    # kiosk always runs elevated. Firewall + global hotkey blocks
    # require admin and the kiosk aborts with a fatal error otherwise.
    uac_admin=True,
    uac_uiaccess=False,
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OmniProctorBrowser",
)
