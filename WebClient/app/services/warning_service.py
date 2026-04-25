"""Service layer for ``ProctorWarning`` (teacher → student channel)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.proctor_warning import ProctorWarning
from app.models.test_attempt import TestAttempt
from app.models.user import User


def create_warning(
    db: Session,
    attempt: TestAttempt,
    sender: User,
    message: str,
    severity: str,
) -> ProctorWarning:
    warning = ProctorWarning(
        attempt_id=attempt.id,
        sender_id=sender.id,
        message=message.strip(),
        severity=severity,
    )
    db.add(warning)
    db.commit()
    db.refresh(warning)
    return warning


def list_warnings_for_attempt(
    db: Session,
    attempt_id: int,
    *,
    since_id: int | None = None,
) -> list[ProctorWarning]:
    query = db.query(ProctorWarning).filter(ProctorWarning.attempt_id == attempt_id)
    if since_id:
        query = query.filter(ProctorWarning.id > since_id)
    return query.order_by(ProctorWarning.id.asc()).all()


def latest_warning_id_for_attempt(db: Session, attempt_id: int) -> int | None:
    row = (
        db.query(ProctorWarning.id)
        .filter(ProctorWarning.attempt_id == attempt_id)
        .order_by(ProctorWarning.id.desc())
        .first()
    )
    return row[0] if row else None


def get_warning_or_404(db: Session, warning_id: int) -> ProctorWarning:
    warning = db.query(ProctorWarning).filter(ProctorWarning.id == warning_id).first()
    if not warning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warning not found")
    return warning


def acknowledge_warning(
    db: Session,
    warning: ProctorWarning,
    delivered_at: datetime | None = None,
) -> ProctorWarning:
    now = datetime.now(timezone.utc)
    if warning.delivered_at is None:
        warning.delivered_at = delivered_at or now
    warning.acknowledged_at = now
    db.commit()
    db.refresh(warning)
    return warning


def warning_count_for_attempt(db: Session, attempt_id: int) -> int:
    return (
        db.query(ProctorWarning)
        .filter(ProctorWarning.attempt_id == attempt_id)
        .count()
    )
