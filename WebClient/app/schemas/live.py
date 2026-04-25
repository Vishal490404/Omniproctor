"""Pydantic models for the live monitoring dashboard."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LiveAttemptRow(BaseModel):
    attempt_id: int
    student_id: int
    student_name: str
    student_email: str
    status: str
    started_at: datetime
    last_seen_at: datetime | None
    risk_score: int
    risk_band: str  # ok | warn | critical
    top_contributors: list[tuple[str, int]]
    event_count_window: int
    monitor_count: int | None
    focus_state: str  # in_focus | out_of_focus | unknown
    vm_detected: bool
    warnings_sent: int
    latest_event_type: str | None
    latest_event_severity: str | None


class LiveTestSnapshot(BaseModel):
    test_id: int
    test_name: str
    generated_at: datetime
    rows: list[LiveAttemptRow]
