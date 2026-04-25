"""Polls the WebClient for new teacher-sent warnings.

Runs on its own QThread on a 3s cadence. New warnings are emitted as
``warning_received`` Qt signals - the main thread is responsible for
showing the banner UI. After a warning is shown we POST /warnings/{id}/ack
so the teacher dashboard knows it landed.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from .config import TelemetryConfig, get_config

logger = logging.getLogger(__name__)

POLL_INTERVAL_SEC = 3.0
HTTP_TIMEOUT = 6.0
MAX_BACKOFF = 30.0


class WarningPoller(QThread):
    """GET /warnings every 3s, surface new ones via Qt signal."""

    # Emitted on the poller thread; main-thread slot is responsible for UI.
    warning_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, config: Optional[TelemetryConfig] = None, parent=None):
        super().__init__(parent)
        self._config = config or get_config()
        self._stop = threading.Event()
        self._since_id = 0
        self._backoff = 1.0
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def advance_since(self, since_id: int) -> None:
        """BatchPoster can hint us to skip ahead when it sees a fresh latest_warning_id."""
        with self._lock:
            if since_id > self._since_id:
                self._since_id = since_id

    def run(self) -> None:
        if not self._config.is_active:
            logger.info("WarningPoller disabled (telemetry not configured)")
            return

        logger.info("WarningPoller started (attempt_id=%s)", self._config.attempt_id)
        while not self._stop.is_set():
            try:
                self._poll_once()
                self._backoff = 1.0
            except Exception as exc:
                logger.warning("WarningPoller failed: %s", exc)
                time.sleep(self._backoff)
                self._backoff = min(self._backoff * 2, MAX_BACKOFF)
                continue

            # Sleep in small slices so .stop() reacts quickly.
            slept = 0.0
            while slept < POLL_INTERVAL_SEC and not self._stop.is_set():
                time.sleep(0.25)
                slept += 0.25

        logger.info("WarningPoller stopped")

    # ------------------------------------------------------------------
    def _poll_once(self) -> None:
        with self._lock:
            since_id = self._since_id

        url = self._config.warnings_url(since_id=since_id)
        if not url:
            return

        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._config.auth_token}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as http_err:
            if http_err.code in (401, 403):
                # Don't keep hammering with bad credentials.
                logger.warning("WarningPoller auth failed (%d) - stopping", http_err.code)
                self.stop()
            raise

        if not body:
            return
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("WarningPoller got non-JSON body")
            return

        warnings = payload if isinstance(payload, list) else payload.get("warnings", [])
        if not warnings:
            return

        max_id = since_id
        for w in warnings:
            try:
                wid = int(w.get("id", 0))
            except (TypeError, ValueError):
                continue
            if wid <= since_id:
                continue
            try:
                self.warning_received.emit(dict(w))
            except Exception:
                pass
            self._ack(wid)
            if wid > max_id:
                max_id = wid

        with self._lock:
            if max_id > self._since_id:
                self._since_id = max_id

    def _ack(self, warning_id: int) -> None:
        url = self._config.warning_ack_url(warning_id)
        if not url:
            return
        req = urllib.request.Request(
            url,
            method="POST",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.auth_token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT):
                pass
        except Exception as exc:
            # Non-fatal - the server will redeliver if we don't ack.
            logger.debug("WarningPoller ack failed for %d: %s", warning_id, exc)
