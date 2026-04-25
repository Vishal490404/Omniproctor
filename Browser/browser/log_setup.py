"""File-based logging for the secure browser.

Background: when the kiosk is launched via the ``omniproctor-browser://``
protocol handler or directly through ``pythonw.exe`` / a frozen ``.exe``,
there is no console attached. Anything written to stdout, stderr, or via
``logging`` is silently discarded, which makes WFP / kiosk failures very
hard to diagnose in the field.

This module configures:
    * A rotating file handler at ``<log_dir>/omniproctor_kiosk.log``.
    * A console handler when one is available (dev mode in a terminal).
    * Stdout / stderr redirection so existing ``print()`` calls also land
      in the log file.

The log path is returned so callers can surface it to the operator (e.g.
in error dialogs).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import IO

LOG_LEVEL_ENV = "OMNIPROCTOR_LOG_LEVEL"
LOG_DIR_ENV = "OMNIPROCTOR_LOG_DIR"
LOG_FILE_NAME = "omniproctor_kiosk.log"


class _Tee:
    """Write-only stream that fans writes out to multiple underlying streams."""

    def __init__(self, *streams: IO[str]):
        self._streams = [s for s in streams if s is not None]

    def write(self, data: str) -> int:
        for s in self._streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        for s in self._streams:
            try:
                if s.isatty():
                    return True
            except Exception:
                continue
        return False


def _resolve_log_dir() -> Path:
    override = os.getenv(LOG_DIR_ENV)
    if override:
        return Path(override).expanduser()

    # For frozen builds (PyInstaller, etc.) ``sys.frozen`` is True and
    # ``sys.executable`` is the kiosk .exe — drop the log next to it so
    # field admins can find it without hunting.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    # Dev mode: write next to the entry-point script (Browser/browser/).
    try:
        return Path(__file__).resolve().parent
    except Exception:
        return Path.cwd()


def _resolve_log_level() -> int:
    raw = os.getenv(LOG_LEVEL_ENV, "INFO").strip().upper()
    return getattr(logging, raw, logging.INFO)


def configure_file_logging() -> Path:
    """Set up a rotating file logger and tee stdout/stderr into it.

    Returns the absolute log file path. Safe to call more than once; the
    second call is a no-op.
    """
    log_dir = _resolve_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_dir = Path.cwd()
        log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / LOG_FILE_NAME

    root = logging.getLogger()

    # Idempotency check: if we've already attached our handler, bail out.
    for h in root.handlers:
        if getattr(h, "_omniproctor_marker", False):
            return Path(getattr(h, "baseFilename", str(log_path)))

    root.setLevel(_resolve_log_level())

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
        delay=False,
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    file_handler._omniproctor_marker = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)

    # Console handler only when a real console is attached (dev terminal).
    try:
        if sys.stderr is not None and sys.stderr.isatty():
            console = logging.StreamHandler(sys.stderr)
            console.setFormatter(fmt)
            console.setLevel(logging.INFO)
            root.addHandler(console)
    except Exception:
        pass

    # Tee stdout / stderr so existing print() calls land in the log too.
    log_stream = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, log_stream)  # type: ignore[assignment]
    sys.stderr = _Tee(sys.__stderr__, log_stream)  # type: ignore[assignment]

    logging.getLogger(__name__).info(
        "=== OmniProctor kiosk log started (pid=%d, exe=%s) ===",
        os.getpid(),
        sys.executable,
    )
    return log_path.resolve()


def get_log_path() -> Path:
    """Return the resolved log path without changing logging configuration."""
    return _resolve_log_dir() / LOG_FILE_NAME
