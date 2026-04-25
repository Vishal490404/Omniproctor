"""Schemas for the kiosk-installer download endpoints."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class InstallerInfo(BaseModel):
    """Per-platform installer descriptor."""

    available: bool = Field(description="True if the file exists on the server")
    filename: Optional[str] = Field(
        default=None, description="Original filename of the installer"
    )
    version: Optional[str] = Field(
        default=None, description="Marketing version of the kiosk build"
    )
    size_bytes: Optional[int] = Field(default=None, description="File size in bytes")
    sha256: Optional[str] = Field(
        default=None, description="SHA-256 of the installer for verification"
    )
    url: Optional[str] = Field(
        default=None, description="Authenticated download URL (relative to API base)"
    )


class DownloadManifest(BaseModel):
    """All available kiosk installers, keyed by platform."""

    windows: InstallerInfo
