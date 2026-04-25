"""Process-wide telemetry configuration.

Populated once at startup from CLI args + the omniproctor-browser:// query
string + environment variables. The poster / warning poller / monitors all
read this. When ``attempt_id`` or ``api_base`` is missing, telemetry is
silently no-op'd so a kiosk launched without a backend (e.g. dev runs
against ``https://google.com``) still works fine.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TelemetryConfig:
    api_base: Optional[str] = None       # e.g. "https://omniproctor.local/api/v1"
    attempt_id: Optional[int] = None
    auth_token: Optional[str] = None     # Bearer token for the kiosk's session
    student_id: Optional[int] = None
    test_id: Optional[int] = None
    keylogger_enabled: bool = True

    @property
    def is_active(self) -> bool:
        return bool(self.api_base and self.attempt_id and self.auth_token)

    def events_url(self) -> Optional[str]:
        if not self.is_active:
            return None
        return f"{self.api_base.rstrip('/')}/behavior/attempts/{self.attempt_id}/events:batch"

    def warnings_url(self, since_id: int = 0) -> Optional[str]:
        if not self.is_active:
            return None
        base = f"{self.api_base.rstrip('/')}/proctor/attempts/{self.attempt_id}/warnings"
        return f"{base}?since_id={since_id}" if since_id else base

    def warning_ack_url(self, warning_id: int) -> Optional[str]:
        if not self.is_active:
            return None
        return f"{self.api_base.rstrip('/')}/proctor/warnings/{warning_id}/ack"


_singleton: Optional[TelemetryConfig] = None
_singleton_lock = threading.Lock()


def get_config() -> TelemetryConfig:
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = TelemetryConfig(
                    keylogger_enabled=os.environ.get("KIOSK_DISABLE_KEYLOGGER", "")
                    not in {"1", "true", "yes"}
                )
    return _singleton


def configure(
    *,
    api_base: Optional[str] = None,
    attempt_id: Optional[int] = None,
    auth_token: Optional[str] = None,
    student_id: Optional[int] = None,
    test_id: Optional[int] = None,
) -> TelemetryConfig:
    cfg = get_config()
    if api_base:
        cfg.api_base = api_base.strip()
    if attempt_id:
        cfg.attempt_id = int(attempt_id)
    if auth_token:
        cfg.auth_token = auth_token.strip()
    if student_id:
        cfg.student_id = int(student_id)
    if test_id:
        cfg.test_id = int(test_id)
    return cfg
