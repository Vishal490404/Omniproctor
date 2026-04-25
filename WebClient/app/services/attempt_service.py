from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignment import TestAssignment
from app.models.test import Test
from app.models.test_attempt import AttemptStatus, TestAttempt
from app.models.user import User
from app.schemas.attempt import AttemptSummaryResponse


def _build_summary(test: Test, student_id: int, attempts_used: int) -> AttemptSummaryResponse:
    attempts_remaining = max(test.max_attempts - attempts_used, 0)
    return AttemptSummaryResponse(
        test_id=test.id,
        student_id=student_id,
        max_attempts=test.max_attempts,
        attempts_used=attempts_used,
        attempts_remaining=attempts_remaining,
        can_attempt=attempts_remaining > 0,
    )


def get_attempts_used(db: Session, test_id: int, student_id: int) -> int:
    return (
        db.query(func.count(TestAttempt.id))
        .filter(
            TestAttempt.test_id == test_id,
            TestAttempt.student_id == student_id,
            TestAttempt.status == AttemptStatus.ENDED,
        )
        .scalar()
        or 0
    )


def get_attempt_summary(db: Session, test: Test, student_id: int) -> AttemptSummaryResponse:
    used = get_attempts_used(db, test.id, student_id)
    return _build_summary(test, student_id, used)


def get_attempt_summary_map(db: Session, test: Test, student_ids: list[int]) -> dict[int, AttemptSummaryResponse]:
    if not student_ids:
        return {}

    rows = (
        db.query(TestAttempt.student_id, func.count(TestAttempt.id))
        .filter(
            TestAttempt.test_id == test.id,
            TestAttempt.student_id.in_(student_ids),
            TestAttempt.status == AttemptStatus.ENDED,
        )
        .group_by(TestAttempt.student_id)
        .all()
    )
    used_map = {student_id: count for student_id, count in rows}
    return {
        student_id: _build_summary(test, student_id, used_map.get(student_id, 0))
        for student_id in student_ids
    }


def start_attempt(db: Session, test: Test, student: User) -> TestAttempt:
    assignment = (
        db.query(TestAssignment)
        .filter(TestAssignment.test_id == test.id, TestAssignment.student_id == student.id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is not assigned to this test")

    summary = get_attempt_summary(db, test, student.id)
    if not summary.can_attempt:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt limit reached")

    existing = (
        db.query(TestAttempt)
        .filter(
            TestAttempt.test_id == test.id,
            TestAttempt.student_id == student.id,
            TestAttempt.status == AttemptStatus.IN_PROGRESS,
        )
        .order_by(TestAttempt.id.desc())
        .first()
    )
    if existing:
        return existing

    attempt = TestAttempt(
        test_id=test.id,
        student_id=student.id,
        assignment_id=assignment.id,
        status=AttemptStatus.IN_PROGRESS,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def end_attempt(db: Session, test: Test, student: User, reason: str | None = None) -> TestAttempt:
    assignment = (
        db.query(TestAssignment)
        .filter(TestAssignment.test_id == test.id, TestAssignment.student_id == student.id)
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student is not assigned to this test")

    active = (
        db.query(TestAttempt)
        .filter(
            TestAttempt.test_id == test.id,
            TestAttempt.student_id == student.id,
            TestAttempt.status == AttemptStatus.IN_PROGRESS,
        )
        .order_by(TestAttempt.id.desc())
        .first()
    )

    now = datetime.now(timezone.utc)
    if active:
        active.status = AttemptStatus.ENDED
        active.ended_at = now
        active.ended_reason = reason
        db.add(active)
        db.commit()
        db.refresh(active)
        return active

    summary = get_attempt_summary(db, test, student.id)
    if not summary.can_attempt:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt limit reached")

    attempt = TestAttempt(
        test_id=test.id,
        student_id=student.id,
        assignment_id=assignment.id,
        status=AttemptStatus.ENDED,
        started_at=now,
        ended_at=now,
        ended_reason=reason,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def list_attempts_for_student(db: Session, test_id: int, student_id: int) -> list[TestAttempt]:
    return (
        db.query(TestAttempt)
        .filter(TestAttempt.test_id == test_id, TestAttempt.student_id == student_id)
        .order_by(TestAttempt.id.desc())
        .all()
    )
