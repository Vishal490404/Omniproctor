from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.behavior_event import BehaviorEvent
from app.models.test_attempt import TestAttempt


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
