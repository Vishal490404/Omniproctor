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
                raw = resp.read().decode("utf-8") or "{}"
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if "json" not in ctype:
                    # Almost always means the kiosk is pointed at the wrong
                    # base URL (e.g. Vite dev server returning index.html).
                    # Surface it loudly - silent 200s with HTML are the worst
                    # kind of telemetry failure to debug.
                    print(
                        f"[telemetry] BatchPoster: non-JSON {resp.status} from {url} "
                        f"(content-type={ctype!r}) - dropping {len(events)} events. "
                        f"Is api_base correct? It must point at the FastAPI backend, "
                        f"NOT the Vite dev server."
                    )
                    return
                payload = json.loads(raw)
                print(
                    f"[telemetry] BatchPoster: POST {url} -> {resp.status} "
                    f"(accepted={payload.get('accepted')}, "
                    f"latest_warning_id={payload.get('latest_warning_id')})"
                )
        except urllib.error.HTTPError as http_err:
            body_preview = ""
            try:
                body_preview = http_err.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if 400 <= http_err.code < 500:
                print(
                    f"[telemetry] BatchPoster: HTTP {http_err.code} from {url} - "
                    f"dropping {len(events)} events. Body: {body_preview!r}"
                )
                return
            print(
                f"[telemetry] BatchPoster: HTTP {http_err.code} from {url} - "
                f"requeueing {len(events)} events. Body: {body_preview!r}"
            )
            self._bus.requeue(events)
            self._sleep_backoff()
            return
        except (urllib.error.URLError, TimeoutError) as net_err:
            print(
                f"[telemetry] BatchPoster: network error {net_err} for {url} - "
                f"requeueing {len(events)} events"
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


def post_attempt_end(reason: str = "user_ended_session", timeout: float = 4.0) -> bool:
    """Best-effort POST to /tests/{test_id}/attempts/end.

    Called from the kiosk's ``safe_exit`` so the WebClient flips the
    attempt's status from IN_PROGRESS to COMPLETED. Silently returns
    ``False`` when telemetry is not configured or the request fails so
    shutdown is never blocked by network issues.
    """
    cfg = get_config()
    url = cfg.end_attempt_url()
    if not url:
        print(
            f"[telemetry] post_attempt_end: skipped - telemetry inactive "
            f"(api_base={cfg.api_base}, test_id={cfg.test_id}, "
            f"has_token={bool(cfg.auth_token)})"
        )
        return False

    body = json.dumps({"reason": reason}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.auth_token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            print(
                f"[telemetry] post_attempt_end: POST {url} -> {resp.status} "
                f"(attempt {cfg.attempt_id} marked completed)"
            )
        return True
    except urllib.error.HTTPError as http_err:
        body_preview = ""
        try:
            body_preview = http_err.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        print(
            f"[telemetry] post_attempt_end: HTTP {http_err.code} from {url}. "
            f"Body: {body_preview!r}"
        )
        return False
    except Exception as exc:
        print(f"[telemetry] post_attempt_end: network error for {url}: {exc}")
        return False
