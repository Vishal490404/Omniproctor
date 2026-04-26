"""Authenticated kiosk-installer download endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse

from app.api.deps import CurrentUser
from app.controllers.download_controller import (
    get_download_manifest,
    get_windows_installer_external_url,
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
    """Deliver the Windows kiosk installer.

    When ``INSTALLER_WINDOWS_URL`` is configured, this endpoint 307-redirects
    to that URL. We use 307 (Temporary Redirect) instead of 302 specifically
    so HTTP method and any Authorization header semantics are preserved on
    the rebound - GitHub Releases ignores Authorization but we don't want
    a future deployment behind a private CDN to break silently because the
    SPA fell through to a GET-only redirect.

    Otherwise, the file is streamed from the bind-mounted ``installer_dir``.
    """
    external_url = get_windows_installer_external_url()
    if external_url:
        return RedirectResponse(url=external_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    path = get_windows_installer_path()
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Windows installer is not available on the server. "
                "Either set INSTALLER_WINDOWS_URL to a GitHub Releases "
                f"asset URL, or place '{settings.installer_windows_filename}' "
                f"under '{settings.installer_dir}'."
            ),
        )
    return FileResponse(
        path=str(path),
        media_type="application/octet-stream",
        filename=settings.installer_windows_filename,
    )
