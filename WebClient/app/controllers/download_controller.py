"""Controller-layer helpers for the kiosk-installer download endpoints.

The kiosk EXE can be delivered two ways - configured via env vars on the
WebClient:

  1. ``INSTALLER_WINDOWS_URL`` is set
     We treat the URL as authoritative (typically a GitHub Releases asset
     like ``https://github.com/<org>/<repo>/releases/download/v0.1.0/...``)
     and the manifest just echoes it back, optionally with a SHA-256 the
     operator copied off the GitHub release page.

  2. ``INSTALLER_WINDOWS_URL`` is unset
     Fall back to streaming a local file from ``installer_dir`` (bind-
     mounted into the API container in docker-compose). SHA-256 is
     computed lazily from the file itself and cached by (path, mtime, size).

Mode 1 is the recommended way to ship to production - it keeps the EXE
out of the git repo and out of the docker image, and lets you publish
new builds by uploading to GitHub instead of redeploying the API.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.schemas.download import DownloadManifest, InstallerInfo

WINDOWS_DOWNLOAD_PATH = "/api/v1/downloads/installer/windows"


def _installer_path() -> Path:
    return Path(settings.installer_dir) / settings.installer_windows_filename


@lru_cache(maxsize=4)
def _cached_sha256(path_str: str, mtime_ns: int, size: int) -> str:
    """Cache SHA-256 by (path, mtime, size). Recomputes on file replacement."""
    h = hashlib.sha256()
    with open(path_str, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_external_url_configured() -> bool:
    return bool((settings.installer_windows_url or "").strip())


def _windows_info_external() -> InstallerInfo:
    """Build the manifest entry when the EXE lives on an external host."""
    return InstallerInfo(
        available=True,
        external=True,
        filename=settings.installer_windows_filename,
        version=settings.installer_windows_version,
        size_bytes=settings.installer_windows_size_bytes,
        sha256=settings.installer_windows_sha256,
        url=settings.installer_windows_url,
    )


def _windows_info_local() -> InstallerInfo:
    """Build the manifest entry from the bind-mounted local file."""
    path = _installer_path()
    if not path.exists() or not path.is_file():
        return InstallerInfo(available=False)

    stat = path.stat()
    sha = _cached_sha256(str(path), stat.st_mtime_ns, stat.st_size)
    return InstallerInfo(
        available=True,
        external=False,
        filename=settings.installer_windows_filename,
        version=settings.installer_windows_version,
        size_bytes=stat.st_size,
        sha256=sha,
        url=WINDOWS_DOWNLOAD_PATH,
    )


def _windows_info() -> InstallerInfo:
    if _is_external_url_configured():
        return _windows_info_external()
    return _windows_info_local()


def get_download_manifest() -> DownloadManifest:
    return DownloadManifest(windows=_windows_info())


def get_windows_installer_path() -> Optional[Path]:
    """Return the local file path, or ``None`` if it isn't available locally."""
    if _is_external_url_configured():
        return None
    path = _installer_path()
    if path.exists() and path.is_file():
        return path
    return None


def get_windows_installer_external_url() -> Optional[str]:
    """Return the externally-hosted URL when configured, otherwise ``None``."""
    url = (settings.installer_windows_url or "").strip()
    return url or None
