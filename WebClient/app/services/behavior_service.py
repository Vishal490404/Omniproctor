from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.behavior_event import BehaviorEvent
from app.models.test_attempt import TestAttempt
from app.schemas.behavior import BehaviorEventCreateRequest


def _attempt_number_map(db: Session, test_id: int, student_id: int) -> dict[int, int]:
    """Return ``{attempt_id: 1-based sequence}`` for this (test, student).

    Sequence is by ``started_at`` ascending so the candidate's first
    attempt is #1, second is #2, etc. - independent of the global
    ``test_attempts.id`` PK.
    """
    attempts = (
        db.query(TestAttempt.id, TestAttempt.started_at)
        .filter(TestAttempt.test_id == test_id, TestAttempt.student_id == student_id)
        .order_by(TestAttempt.started_at.asc(), TestAttempt.id.asc())
        .all()
    )
    return {row.id: idx for idx, row in enumerate(attempts, start=1)}


def attempt_number_for(db: Session, attempt: TestAttempt) -> int:
    """1-based sequence for a single attempt (cheap path - just a COUNT)."""
    earlier = (
        db.query(TestAttempt.id)
        .filter(
            TestAttempt.test_id == attempt.test_id,
            TestAttempt.student_id == attempt.student_id,
            TestAttempt.started_at < attempt.started_at,
        )
        .count()
    )
    return earlier + 1


def create_behavior_event(
    db: Session,
    attempt: TestAttempt,
    event_type,
    payload: dict | None,
    severity: str,
    event_time: datetime | None = None,
) -> BehaviorEvent:
    if not event_time:
        event_time = datetime.now(timezone.utc)

    event = BehaviorEvent(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        student_id=attempt.student_id,
        event_type=event_type,
        payload=payload,
        severity=severity,
        event_time=event_time,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_attempt_or_404(db: Session, attempt_id: int) -> TestAttempt:
    attempt = db.query(TestAttempt).filter(TestAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found")
    return attempt


def create_behavior_events_bulk(
    db: Session,
    attempt: TestAttempt,
    events: Iterable[BehaviorEventCreateRequest],
) -> int:
    """Insert a batch of events in a single commit. Returns count inserted.

    Silently drops malformed entries (e.g. unknown event_type slipping in
    after the kiosk + server fall out of sync) so a single bad event
    doesn't reject the whole batch.
    """
    now = datetime.now(timezone.utc)
    rows: list[BehaviorEvent] = []
    for ev in events:
        try:
            rows.append(
                BehaviorEvent(
                    attempt_id=attempt.id,
                    test_id=attempt.test_id,
                    student_id=attempt.student_id,
                    event_type=ev.event_type,
                    payload=ev.payload,
                    severity=ev.severity,
                    event_time=ev.event_time or now,
                )
            )
        except Exception:
            continue
    if not rows:
        return 0
    db.add_all(rows)
    db.commit()
    return len(rows)


def _attach_attempt_numbers(
    events: list[BehaviorEvent], number_by_attempt: dict[int, int]
) -> list[BehaviorEvent]:
    """Stamp each ORM event with ``attempt_number`` so Pydantic's
    ``from_attributes=True`` picks it up in BehaviorEventResponse.

    Attaching as a plain Python attribute is fine - SQLAlchemy doesn't
    fight us as long as the name isn't a mapped column.
    """
    for event in events:
        event.attempt_number = number_by_attempt.get(event.attempt_id, 1)
    return events


def list_events_for_attempt(db: Session, attempt_id: int) -> list[BehaviorEvent]:
    events = (
        db.query(BehaviorEvent)
        .filter(BehaviorEvent.attempt_id == attempt_id)
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .all()
    )
    if not events:
        return events
    # All events in this list share one attempt_id. Use the cheap
    # single-attempt rank rather than building a full map.
    first = events[0]
    attempt = db.query(TestAttempt).filter(TestAttempt.id == first.attempt_id).first()
    if attempt is not None:
        number = attempt_number_for(db, attempt)
        return _attach_attempt_numbers(events, {attempt.id: number})
    return events


def list_events_for_test_student(db: Session, test_id: int, student_id: int) -> list[BehaviorEvent]:
    events = (
        db.query(BehaviorEvent)
        .filter(BehaviorEvent.test_id == test_id, BehaviorEvent.student_id == student_id)
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .all()
    )
    if not events:
        return events
    return _attach_attempt_numbers(events, _attempt_number_map(db, test_id, student_id))
