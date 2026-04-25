"""Authenticated kiosk-installer download endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser
from app.controllers.download_controller import (
    get_download_manifest,
    get_windows_installer_path,
)
from app.core.config import settings
from app.schemas.download import DownloadManifest

router = APIRouter()


@router.get("/manifest", response_model=DownloadManifest)
def downloads_manifest(_: CurrentUser) -> DownloadManifest:
    """Return per-platform installer metadata (auth required)."""
    return get_download_manifest()


@router.get("/installer/windows")
def download_windows_installer(_: CurrentUser):
    """Stream the Windows kiosk installer (auth required)."""
    path = get_windows_installer_path()
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Windows installer is not available on the server. "
                f"Place '{settings.installer_windows_filename}' under "
                f"'{settings.installer_dir}'."
            ),
        )
    return FileResponse(
        path=str(path),
        media_type="application/octet-stream",
        filename=settings.installer_windows_filename,
    )
