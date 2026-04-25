"""Persistent QWebEngineProfile for the secure kiosk browser.

The previous implementation read the page's *default* off-the-record-ish
profile, which gave us no HTTP disk cache, no service-worker reuse, and no
persistent cookies/IndexedDB across launches. Every cold start paid the full
network round-trip cost for static assets.

This module builds a single named profile (``omniproctor-kiosk``) backed by
``%LOCALAPPDATA%/OmniProctor/kiosk-profile`` on Windows (and a sane fallback
on other platforms), with disk HTTP cache + persistent cookies + a custom
user-agent so server logs can identify our kiosk traffic.

The profile is also where we hook ``downloadRequested`` so files the page
asks to save actually land somewhere on disk instead of silently failing.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEngineProfile,
    QWebEngineSettings,
)

logger = logging.getLogger(__name__)

PROFILE_NAME = "omniproctor-kiosk"
KIOSK_VERSION = "0.1.0"


def _profile_storage_root() -> Path:
    """Return the directory that should hold persistent profile state.

    Prefers ``%LOCALAPPDATA%`` on Windows, falls back to Qt's standard
    AppLocalDataLocation otherwise. Created on first call.
    """
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            base = Path(local_appdata) / "OmniProctor"
        else:
            base = Path.home() / "AppData" / "Local" / "OmniProctor"
    else:
        qt_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        base = Path(qt_dir) if qt_dir else Path.home() / ".omniproctor"

    base.mkdir(parents=True, exist_ok=True)
    return base


def _downloads_dir() -> Path:
    """User-visible folder where in-page downloads will be written."""
    if sys.platform == "win32":
        downloads = Path.home() / "Downloads" / "OmniProctor"
    else:
        downloads = Path.home() / "Downloads" / "OmniProctor"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def _apply_persistent_permissions_policy(profile: QWebEngineProfile) -> None:
    """Force the safe ``AskEveryTime`` policy on Qt 6.8+.

    We intentionally do NOT enable ``StoreOnDisk`` here: combined with the
    legacy ``featurePermissionRequested`` signal we still rely on, PyQt6
    6.10 on Windows has been observed to hard-crash the whole process
    when the first ``setFeaturePermission`` call lands. Our Python-side
    handler auto-grants every request anyway, so re-asking each session
    is invisible to the candidate.
    """
    try:
        policy_enum = QWebEngineProfile.PersistentPermissionsPolicy
        profile.setPersistentPermissionsPolicy(policy_enum.AskEveryTime)
        logger.debug("Persistent permissions policy forced to AskEveryTime")
    except (AttributeError, TypeError):
        logger.debug("PersistentPermissionsPolicy not available on this Qt build")


def build_kiosk_profile(parent=None) -> QWebEngineProfile:
    """Construct the kiosk's persistent profile and configure all settings.

    Returns a profile that:
        * Stores cookies, IndexedDB, service workers, and HTTP disk cache
          under ``<LocalAppData>/OmniProctor/kiosk-profile``.
        * Identifies itself with a custom UA so server logs can spot us.
        * Has every web setting we need for a normal exam app to work
          (clipboard, PDF viewer, WebGL, smooth scrolling, autoplay, etc.).
        * Routes ``downloadRequested`` to ``~/Downloads/OmniProctor``.
    """
    base = _profile_storage_root()
    profile_dir = base / "kiosk-profile"
    cache_dir = base / "kiosk-cache"
    profile_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    profile = QWebEngineProfile(PROFILE_NAME, parent)
    profile.setPersistentStoragePath(str(profile_dir))
    profile.setCachePath(str(cache_dir))
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
    )
    profile.setHttpCacheMaximumSize(256 * 1024 * 1024)  # 256 MiB

    default_ua = profile.httpUserAgent() or ""
    profile.setHttpUserAgent(f"{default_ua} OmniProctorKiosk/{KIOSK_VERSION}".strip())

    _apply_persistent_permissions_policy(profile)
    _configure_settings(profile)

    profile.downloadRequested.connect(_on_download_requested)

    logger.info(
        "Kiosk profile ready: storage=%s cache=%s ua=%s",
        profile_dir,
        cache_dir,
        profile.httpUserAgent(),
    )
    return profile


def _configure_settings(profile: QWebEngineProfile) -> None:
    """Apply every web setting the exam UI is likely to depend on."""
    settings = profile.settings()
    if not settings:
        logger.warning("Profile returned no QWebEngineSettings")
        return

    Attr = QWebEngineSettings.WebAttribute
    dev_mode = os.getenv("OMNIPROCTOR_DEV", "").strip() in {"1", "true", "True"}

    # Look up every attribute by name via getattr() so a Qt build that drops
    # or renames any of these constants doesn't crash startup. (PyQt6 6.10
    # removed SmoothScrollingEnabled from the public WebAttribute enum, for
    # example.) Anything missing on the current Qt is silently skipped and
    # the kiosk continues without it.
    enabled_names = (
        "JavascriptEnabled",
        "JavascriptCanOpenWindows",
        "AllowWindowActivationFromJavaScript",
        "LocalStorageEnabled",
        "ScreenCaptureEnabled",
        "FullScreenSupportEnabled",
        "PluginsEnabled",
        "AutoLoadImages",
        "LocalContentCanAccessRemoteUrls",
        "LocalContentCanAccessFileUrls",
        # Performance + UX
        "Accelerated2dCanvasEnabled",
        "WebGLEnabled",
        "ScrollAnimatorEnabled",
        "SmoothScrollingEnabled",
        "SpatialNavigationEnabled",
        "HyperlinkAuditingEnabled",
        # Real exam UIs need these
        "JavascriptCanAccessClipboard",
        "JavascriptCanPaste",
        "PdfViewerEnabled",
    )
    disabled_names = (
        # Audio/video probes mustn't block on a click gesture in exam UIs.
        "PlaybackRequiresUserGesture",
        # Keep WebRTC visible to all interfaces (we firewall at the WFP layer).
        "WebRTCPublicInterfacesOnly",
        # The firewall blocks unknown lookups anyway.
        "DnsPrefetchEnabled",
    )

    skipped_enabled, skipped_disabled = [], []
    for name in enabled_names:
        attr = getattr(Attr, name, None)
        if attr is None:
            skipped_enabled.append(name)
            continue
        try:
            settings.setAttribute(attr, True)
        except (AttributeError, TypeError):
            skipped_enabled.append(name)

    for name in disabled_names:
        attr = getattr(Attr, name, None)
        if attr is None:
            skipped_disabled.append(name)
            continue
        try:
            settings.setAttribute(attr, False)
        except (AttributeError, TypeError):
            skipped_disabled.append(name)

    if skipped_enabled or skipped_disabled:
        logger.info(
            "WebAttribute(s) not present on this Qt build (skipped) -> "
            "enabled_missing=%s disabled_missing=%s",
            skipped_enabled,
            skipped_disabled,
        )

    # Safety / dev-only flips ------------------------------------------------
    for name, value in (
        ("AllowRunningInsecureContent", dev_mode),
        ("ShowScrollBars", True),
        ("TouchIconsEnabled", True),
        ("FocusOnNavigationEnabled", True),
        ("ErrorPageEnabled", True),
        ("ReadingFromCanvasEnabled", True),
    ):
        attr = getattr(Attr, name, None)
        if attr is None:
            continue
        try:
            settings.setAttribute(attr, value)
        except (AttributeError, TypeError):
            pass


def _on_download_requested(download: QWebEngineDownloadRequest) -> None:
    """Auto-accept downloads into ~/Downloads/OmniProctor/."""
    try:
        target_dir = _downloads_dir()
        suggested = download.downloadFileName() or "download.bin"
        target_path = target_dir / suggested

        # Avoid clobbering existing files.
        counter = 1
        stem = target_path.stem
        suffix = target_path.suffix
        while target_path.exists():
            target_path = target_dir / f"{stem} ({counter}){suffix}"
            counter += 1

        download.setDownloadDirectory(str(target_dir))
        download.setDownloadFileName(target_path.name)
        download.accept()
        logger.info("Accepting download -> %s", target_path)
    except Exception as exc:
        logger.error("Download handling failed (cancelling): %s", exc)
        try:
            download.cancel()
        except Exception:
            pass


def get_kiosk_profile_dir() -> Optional[Path]:
    """Return the profile dir if it exists (used by the uninstaller hook)."""
    base = _profile_storage_root()
    profile_dir = base / "kiosk-profile"
    return profile_dir if profile_dir.exists() else None
