"""Thread-safe in-memory event bus shared by every kiosk monitor.

The bus decouples emission (cheap, called from the UI thread, focus
poller, keyboard hook, etc.) from network I/O (handled by ``BatchPoster``
on a dedicated QThread). A bounded deque drops the oldest events when
the backend is unreachable for a long time so the kiosk never grows
unbounded memory.

Severity ``critical`` events also set a flag the poster watches so it
flushes the queue immediately instead of waiting for the next 5s tick.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

# Hard cap on buffered events. With the default 5s flush + 200/batch
# server cap, a healthy connection drains comfortably under this.
# We keep the cap large enough to hold ~10 minutes of worst-case
# activity (~30 events/sec) before we start dropping.
DEFAULT_MAX_BUFFER = 20_000


@dataclass
class TelemetryEvent:
    event_type: str
    payload: Optional[dict] = None
    severity: str = "info"
    event_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_api_dict(self) -> dict:
        """Shape matches BehaviorEventCreateRequest on the server."""
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "severity": self.severity,
            "event_time": self.event_time.isoformat(),
        }


class EventBus:
    """Thread-safe FIFO with a wake-event for the poster QThread."""

    def __init__(self, max_buffer: int = DEFAULT_MAX_BUFFER):
        self._dq: deque[TelemetryEvent] = deque(maxlen=max_buffer)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._dropped_count = 0

    # ------------------------------------------------------------------
    # Producer API
    # ------------------------------------------------------------------
    def emit(
        self,
        event_type: str,
        payload: Optional[dict] = None,
        severity: str = "info",
    ) -> None:
        """Cheap, non-blocking. Safe to call from any thread."""
        try:
            ev = TelemetryEvent(
                event_type=event_type,
                payload=payload,
                severity=(severity or "info").lower(),
            )
            with self._lock:
                # ``deque(maxlen=...)`` discards from the LEFT on overflow;
                # we want to know if that happened so the poster can log it.
                if len(self._dq) == self._dq.maxlen:
                    self._dropped_count += 1
                self._dq.append(ev)
            # Wake the poster if it's blocked on the empty queue.
            if severity == "critical":
                self._wake.set()
        except Exception:
            # Telemetry must NEVER raise into the caller. A broken bus
            # is bad, but a broken kiosk UI thread is worse.
            pass

    # ------------------------------------------------------------------
    # Consumer API (used by the BatchPoster)
    # ------------------------------------------------------------------
    def drain(self, max_items: int = 200) -> list[TelemetryEvent]:
        """Pop up to ``max_items`` events (FIFO). Empty list if nothing buffered."""
        out: list[TelemetryEvent] = []
        with self._lock:
            while self._dq and len(out) < max_items:
                out.append(self._dq.popleft())
            self._wake.clear()
        return out

    def requeue(self, events: Iterable[TelemetryEvent]) -> None:
        """Put events back at the FRONT of the queue (used after a failed POST)."""
        with self._lock:
            # appendleft in reverse so the original order is preserved.
            for ev in reversed(list(events)):
                self._dq.appendleft(ev)

    def wait(self, timeout: float) -> bool:
        """Block until a critical event arrives or ``timeout`` elapses."""
        return self._wake.wait(timeout)

    def __len__(self) -> int:
        with self._lock:
            return len(self._dq)

    @property
    def dropped_count(self) -> int:
        return self._dropped_count


# ---------------------------------------------------------------------------
# Module-level singleton. Created lazily so unit tests can swap implementations.
# ---------------------------------------------------------------------------
_singleton: Optional[EventBus] = None
_singleton_lock = threading.Lock()


def get_event_bus() -> EventBus:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = EventBus()
    return _singleton
