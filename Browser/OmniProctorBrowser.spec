# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the OmniProctor secure kiosk browser.

Build with (from the Browser/ directory, with the project venv active):

    uv sync                                        # ensure deps are present
    uv run pyinstaller OmniProctorBrowser.spec --noconfirm --clean

Output:

    dist/OmniProctorBrowser/OmniProctorBrowser.exe
    dist/OmniProctorBrowser/_internal/...

Hard requirements - if you tweak this file, re-validate each:

  * `--onedir` (collected by COLLECT below). Do NOT switch to onefile -
    the WFP firewall controller resolves QtWebEngineProcess.exe by
    walking sys.executable's directory, and onefile's _MEIxxxx temp
    extraction breaks that path on every launch.

  * `uac_admin=True`. Without an embedded requireAdministrator manifest
    the kiosk launches unelevated, the firewall controller throws
    AdminRightsError, and external traffic is NOT blocked.

  * `_internal/PyQt6/Qt6/bin/Qt6WebEngineCore.dll` and
    `_internal/PyQt6/Qt6/QtWebEngineProcess.exe` MUST exist after build.
    `collect_all('PyQt6')` below guarantees this; do not replace it
    with `collect_data_files` alone (data files do not include
    binaries, which is what bit a previous iteration of this spec).

  * Build interpreter parity. PyInstaller bundles whatever is on
    `sys.path` at analysis time. If you run pyinstaller from a venv
    that doesn't have PyQt6 installed, the resulting EXE imports it at
    runtime and crashes with `ModuleNotFoundError: No module named
    'PyQt6'`. The `uv run` form above forces use of the project venv.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------------
# PyQt6 + QtWebEngine - bundle every binary, data file, and submodule.
#
# collect_all() returns (datas, binaries, hiddenimports). This is the
# bulletproof idiom: it pulls in Qt6 DLLs, QtWebEngineProcess.exe, ICU
# data, locales, and every QtCore/QtGui/QtWidgets/QtWebEngine* module so
# we don't have to guess what main.py imports today vs. tomorrow.
# ---------------------------------------------------------------------------
pyqt6_datas, pyqt6_binaries, pyqt6_hidden = collect_all("PyQt6")

# Some PyQt6 wheels split QtWebEngine into a sibling distribution
# ("PyQt6-WebEngine") whose top-level Python package is still "PyQt6".
# collect_all gracefully no-ops when the dist isn't installed under that
# name, so calling it is safe either way.
try:
    we_datas, we_binaries, we_hidden = collect_all("PyQt6_WebEngine")
except Exception:
    we_datas, we_binaries, we_hidden = [], [], []

# `keyboard` ships Windows-specific hooks loaded via importlib at
# runtime; collect_submodules ensures every backend gets bundled.
keyboard_hidden = collect_submodules("keyboard")

# ---------------------------------------------------------------------------
# Our own assets (icon, logo, theme).
# ---------------------------------------------------------------------------
asset_datas = []
for src, dst in (
    ("browser/assets/icon.ico", "browser/assets"),
    ("browser/assets/icon.svg", "browser/assets"),
    ("browser/assets/logo_white.svg", "browser/assets"),
    ("browser/ui/theme.qss", "browser/ui"),
):
    if os.path.isfile(src):
        asset_datas.append((src, dst))
    else:
        # Fail loud during build - shipping without an icon or theme is
        # almost always a mistake.
        print(f"[spec] WARNING: missing asset {src!r} - it will not be bundled.",
              file=sys.stderr)

datas = pyqt6_datas + we_datas + asset_datas
binaries = pyqt6_binaries + we_binaries

# ---------------------------------------------------------------------------
# Hidden imports - things PyInstaller's static analysis cannot see.
#
# main.py imports the in-tree packages by their bare names (`from
# telemetry import ...`) thanks to pathex below. List them explicitly
# so they survive a future refactor where some are imported lazily.
# ---------------------------------------------------------------------------
hiddenimports = (
    pyqt6_hidden
    + we_hidden
    + keyboard_hidden
    + [
        "PyQt6",
        "PyQt6.sip",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        # In-tree packages
        "telemetry",
        "telemetry.poster",
        "telemetry.event_bus",
        "telemetry.warning_poller",
        "telemetry.keystroke_logger",
        "telemetry.config",
        "security",
        "security.vm_detect",
        "security.suspicious_procs",
        "network",
        "network.wfp_native",
        "network.native_firewall_controller",
        "ui",
        "ui.splash",
        "ui.warning_banner",
        "ui.top_bar",
        "ui.dialogs",
        "ui.theme",
        "keyblocks",
        "log_setup",
        "protocol_handler",
        "web_profile",
        "win11_compat",
    ]
)

a = Analysis(
    ["browser/main.py"],
    # pathex adds `browser/` to sys.path so the in-tree imports above
    # (`from keyblocks import ...`, `from telemetry import ...`, etc.)
    # resolve. Without this PyInstaller would fail at analysis time.
    pathex=["browser"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # NOTE: do NOT exclude "test" here - it transitively prunes any
    # module under a `.test.` namespace, including some PyQt6 internals
    # in older wheels. tkinter/IPython/jedi are safe to drop.
    excludes=["tkinter", "IPython", "jedi", "pytest"],
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
    upx=False,  # UPX corrupts QtWebEngineProcess.exe + signed binaries
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="browser/assets/icon.ico",
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
