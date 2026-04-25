"""Batch poster: drains the EventBus and ships events to the WebClient.

Runs on a dedicated QThread so a slow / unreachable backend never stalls
the UI thread. Uses ``urllib`` to avoid adding ``requests`` / ``httpx`` as
a runtime dependency (PyInstaller bundles cleaner with stdlib-only HTTP).
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
from .event_bus import EventBus, get_event_bus

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SEC = 5.0
MAX_BATCH = 200
HTTP_TIMEOUT = 8.0
MAX_BACKOFF = 60.0


class BatchPoster(QThread):
    """Drains the bus + POSTs to /events:batch on a fixed cadence."""

    # Emitted whenever the server returns a fresh latest_warning_id so the
    # WarningPoller can advance its high-water mark without an extra GET.
    latest_warning_id_changed = pyqtSignal(int)

    def __init__(
        self,
        bus: Optional[EventBus] = None,
        config: Optional[TelemetryConfig] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._bus = bus or get_event_bus()
        self._config = config or get_config()
        self._stop = threading.Event()
        self._backoff = 1.0
        self._last_warning_id = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        logger.info(
            "BatchPoster started (api_base=%s, attempt_id=%s, active=%s)",
            self._config.api_base,
            self._config.attempt_id,
            self._config.is_active,
        )

        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                # Telemetry must never bring the kiosk down.
                logger.exception("BatchPoster tick failed: %s", exc)

            # Wake early if a critical event was emitted.
            self._bus.wait(FLUSH_INTERVAL_SEC)

        # Best-effort final flush on graceful shutdown so we don't lose
        # the last few events captured between the last tick and exit.
        try:
            self._tick()
        except Exception:
            pass
        logger.info("BatchPoster stopped (final queue depth=%d)", len(self._bus))

    # ------------------------------------------------------------------
    # One tick: drain → POST → on failure requeue.
    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if not self._config.is_active:
            # Telemetry disabled; just drop the buffer so it doesn't
            # grow forever in dev mode.
            self._bus.drain(max_items=MAX_BATCH)
            return

        events = self._bus.drain(max_items=MAX_BATCH)
        if not events:
            return

        body = json.dumps({"events": [ev.to_api_dict() for ev in events]}).encode("utf-8")
        url = self._config.events_url()
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.auth_token}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as http_err:
            # 4xx ⇒ permanent (bad auth, dropped attempt). Don't requeue
            # or we'll loop forever.
            if 400 <= http_err.code < 500:
                logger.warning(
                    "BatchPoster: server rejected %d events with HTTP %d - dropping",
                    len(events),
                    http_err.code,
                )
                return
            logger.warning(
                "BatchPoster: HTTP %d - requeueing %d events", http_err.code, len(events)
            )
            self._bus.requeue(events)
            self._sleep_backoff()
            return
        except (urllib.error.URLError, TimeoutError) as net_err:
            logger.warning(
                "BatchPoster: network error %s - requeueing %d events",
                net_err,
                len(events),
            )
            self._bus.requeue(events)
            self._sleep_backoff()
            return

        # Success path - reset backoff and surface the latest_warning_id
        # so the WarningPoller can advance.
        self._backoff = 1.0
        latest = payload.get("latest_warning_id") if isinstance(payload, dict) else None
        if isinstance(latest, int) and latest > self._last_warning_id:
            self._last_warning_id = latest
            try:
                self.latest_warning_id_changed.emit(latest)
            except Exception:
                pass

    def _sleep_backoff(self) -> None:
        time.sleep(self._backoff)
        self._backoff = min(self._backoff * 2, MAX_BACKOFF)
