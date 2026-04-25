from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.behavior_event import BehaviorEvent
from app.models.test_attempt import TestAttempt
from app.schemas.behavior import BehaviorEventCreateRequest


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


def list_events_for_attempt(db: Session, attempt_id: int) -> list[BehaviorEvent]:
    return (
        db.query(BehaviorEvent)
        .filter(BehaviorEvent.attempt_id == attempt_id)
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .all()
    )


def list_events_for_test_student(db: Session, test_id: int, student_id: int) -> list[BehaviorEvent]:
    return (
        db.query(BehaviorEvent)
        .filter(BehaviorEvent.test_id == test_id, BehaviorEvent.student_id == student_id)
        .order_by(BehaviorEvent.event_time.desc(), BehaviorEvent.id.desc())
        .all()
    )
