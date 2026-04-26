"""Aggregate per-attempt proctoring snapshot for the live dashboard.

Hot-path - hit every 3s by every teacher viewing the page. Uses a 1s
in-process cache keyed on (test_id) so simultaneous polls collapse to a
single DB hit; absolute correctness within the 1s window is not required.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.behavior_event import BehaviorEvent, BehaviorEventType
from app.models.proctor_warning import ProctorWarning
from app.models.test import Test
from app.models.test_attempt import AttemptStatus, TestAttempt
from app.models.user import User
from app.schemas.live import LiveAttemptRow, LiveTestSnapshot
from app.services.risk_scorer import compute_attempt_risk

_CACHE_TTL_SECONDS = 1.0
_cache: dict[int, tuple[float, LiveTestSnapshot]] = {}
_cache_lock = threading.Lock()


def _focus_state_from_payload(payload: dict | None) -> str:
    if not payload:
        return "unknown"
    state = payload.get("state")
    if state in ("in_focus", "out_of_focus"):
        return state
    return "unknown"


def _build_row(
    db: Session,
    attempt: TestAttempt,
    student: User,
    attempt_number: int,
) -> LiveAttemptRow:
    risk = compute_attempt_risk(db, attempt.id)

    # Latest event drives the "last_seen_at" + "latest_event" fields.
    latest_event = (
        db.query(BehaviorEvent)
        .filter(BehaviorEvent.attempt_id == attempt.id)
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .first()
    )

    # Focus state: most recent FOCUS_LOSS / FOCUS_REGAIN wins.
    focus_state = "unknown"
    focus_event = (
        db.query(BehaviorEvent)
        .filter(
            BehaviorEvent.attempt_id == attempt.id,
            BehaviorEvent.event_type.in_(
                [BehaviorEventType.FOCUS_LOSS, BehaviorEventType.FOCUS_REGAIN]
            ),
        )
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .first()
    )
    if focus_event:
        if focus_event.event_type == BehaviorEventType.FOCUS_REGAIN:
            focus_state = "in_focus"
        else:
            focus_state = "out_of_focus"

    # Monitor count: most recent MONITOR_COUNT_CHANGE event wins.
    monitor_count: int | None = None
    monitor_event = (
        db.query(BehaviorEvent)
        .filter(
            BehaviorEvent.attempt_id == attempt.id,
            BehaviorEvent.event_type == BehaviorEventType.MONITOR_COUNT_CHANGE,
        )
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .first()
    )
    if monitor_event and isinstance(monitor_event.payload, dict):
        try:
            monitor_count = int(monitor_event.payload.get("count"))
        except (TypeError, ValueError):
            monitor_count = None

    # VM flag: any VM_DETECTED event in the attempt's lifetime is sticky.
    vm_detected = (
        db.query(BehaviorEvent.id)
        .filter(
            BehaviorEvent.attempt_id == attempt.id,
            BehaviorEvent.event_type == BehaviorEventType.VM_DETECTED,
        )
        .first()
        is not None
    )

    warnings_sent = (
        db.query(ProctorWarning)
        .filter(ProctorWarning.attempt_id == attempt.id)
        .count()
    )

    return LiveAttemptRow(
        attempt_id=attempt.id,
        attempt_number=attempt_number,
        student_id=student.id,
        student_name=student.full_name,
        student_email=student.email,
        status=attempt.status.value if hasattr(attempt.status, "value") else str(attempt.status),
        started_at=attempt.started_at,
        last_seen_at=latest_event.event_time if latest_event else attempt.started_at,
        risk_score=risk.score,
        risk_band=risk.band,
        top_contributors=risk.top_contributors,
        event_count_window=risk.event_count,
        monitor_count=monitor_count,
        focus_state=focus_state,
        vm_detected=vm_detected,
        warnings_sent=warnings_sent,
        latest_event_type=latest_event.event_type.value if latest_event else None,
        latest_event_severity=latest_event.severity if latest_event else None,
    )


def get_live_snapshot(db: Session, test: Test) -> LiveTestSnapshot:
    now_monotonic = time.monotonic()

    with _cache_lock:
        cached = _cache.get(test.id)
        if cached and (now_monotonic - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]

    # Active attempts only; ended attempts fall off the live board after a
    # short tail. We include ended attempts with events in the last 60s so
    # the row doesn't disappear the instant the candidate hits End Session.
    attempts = (
        db.query(TestAttempt)
        .filter(TestAttempt.test_id == test.id)
        .filter(
            (TestAttempt.status == AttemptStatus.IN_PROGRESS)
            | (TestAttempt.ended_at.is_(None))
        )
        .all()
    )

    student_ids = {a.student_id for a in attempts}
    students = (
        db.query(User).filter(User.id.in_(student_ids)).all() if student_ids else []
    )
    student_by_id = {s.id: s for s in students}

    # Per-(test, student) attempt sequence so the UI can show "attempt #1"
    # for a candidate's first try regardless of the global PK. We compute
    # the full ranking from ALL attempts (not just live ones), then look
    # up each row by id - one extra query per active student, capped to
    # the cohort size and well within the 1s cache window.
    attempt_number_by_id: dict[int, int] = {}
    for sid in student_ids:
        ranked = (
            db.query(TestAttempt.id)
            .filter(
                TestAttempt.test_id == test.id,
                TestAttempt.student_id == sid,
            )
            .order_by(TestAttempt.started_at.asc(), TestAttempt.id.asc())
            .all()
        )
        for idx, row in enumerate(ranked, start=1):
            attempt_number_by_id[row.id] = idx

    rows: list[LiveAttemptRow] = []
    for attempt in attempts:
        student = student_by_id.get(attempt.student_id)
        if not student:
            continue
        rows.append(
            _build_row(
                db,
                attempt,
                student,
                attempt_number=attempt_number_by_id.get(attempt.id, 1),
            )
        )

    # Highest-risk first so the teacher sees who needs attention.
    rows.sort(key=lambda r: (-r.risk_score, r.student_name.lower()))

    snapshot = LiveTestSnapshot(
        test_id=test.id,
        test_name=test.name,
        generated_at=datetime.now(timezone.utc),
        rows=rows,
    )

    with _cache_lock:
        _cache[test.id] = (now_monotonic, snapshot)

    return snapshot


def invalidate_cache(test_id: int | None = None) -> None:
    """Test hook - drop the cache so a fresh snapshot is computed."""
    with _cache_lock:
        if test_id is None:
            _cache.clear()
        else:
            _cache.pop(test_id, None)
