"""Controller-layer helpers for the kiosk-installer download endpoints."""

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


def _windows_info() -> InstallerInfo:
    path = _installer_path()
    if not path.exists() or not path.is_file():
        return InstallerInfo(available=False)

    stat = path.stat()
    sha = _cached_sha256(str(path), stat.st_mtime_ns, stat.st_size)
    return InstallerInfo(
        available=True,
        filename=settings.installer_windows_filename,
        version=settings.installer_windows_version,
        size_bytes=stat.st_size,
        sha256=sha,
        url=WINDOWS_DOWNLOAD_PATH,
    )


def get_download_manifest() -> DownloadManifest:
    return DownloadManifest(windows=_windows_info())


def get_windows_installer_path() -> Optional[Path]:
    path = _installer_path()
    if path.exists() and path.is_file():
        return path
    return None
