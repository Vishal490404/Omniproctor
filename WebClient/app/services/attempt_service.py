from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, not_, or_
from sqlalchemy.orm import Session

from app.models.assignment import TestAssignment
from app.models.test import Test
from app.models.test_attempt import AttemptStatus, TestAttempt
from app.models.user import User
from app.schemas.attempt import AttemptSummaryResponse

# Reasons that mark an ENDED attempt as something the system closed on
# the candidate's behalf rather than a real attempt the candidate spent.
# These are excluded from ``attempts_used`` so an installer / network /
# kiosk-crash glitch can't burn a candidate's allowance of tries.
#
# - ``auto_closed_stale_after_*`` is set by ``_close_stale_attempt`` when
#   the kiosk goes idle for >120 s and we recycle its IN_PROGRESS row.
# - ``orphan_*`` is set when ``end_attempt`` is called with no live
#   IN_PROGRESS row and we synthesise an ENDED row purely for audit.
_NON_COUNTING_REASON_PREFIXES = ("auto_closed_stale_", "orphan_")


def _attempts_used_filter():
    """SQLAlchemy expression matching attempts that should count towards
    ``attempts_used``. A row counts iff it is ENDED AND its
    ``ended_reason`` is null (real End Session) or doesn't start with any
    non-counting prefix.
    """
    return (TestAttempt.status == AttemptStatus.ENDED) & or_(
        TestAttempt.ended_reason.is_(None),
        not_(
            or_(
                *(
                    TestAttempt.ended_reason.like(f"{prefix}%")
                    for prefix in _NON_COUNTING_REASON_PREFIXES
                )
            )
        ),
    )


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
            _attempts_used_filter(),
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
            _attempts_used_filter(),
        )
        .group_by(TestAttempt.student_id)
        .all()
    )
    used_map = {student_id: count for student_id, count in rows}
    return {
        student_id: _build_summary(test, student_id, used_map.get(student_id, 0))
        for student_id in student_ids
    }


# How long an IN_PROGRESS attempt can sit with no activity before we
# treat it as orphaned (kiosk crashed / network died on End Session) and
# auto-close it. Anything shorter than this and a true mid-test reload
# would lose the candidate's session.
STALE_ATTEMPT_SECONDS = 120


def _close_stale_attempt(db: Session, attempt: TestAttempt, *, reason: str) -> None:
    attempt.status = AttemptStatus.ENDED
    attempt.ended_at = datetime.now(timezone.utc)
    attempt.ended_reason = reason
    db.add(attempt)
    db.commit()


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
        # Decide whether the existing attempt is a genuine mid-test reload
        # (return it so the candidate doesn't lose state + spend an extra
        # attempt) or an orphan from a prior session whose End Session POST
        # never reached us (auto-close + create a fresh one so we don't
        # replay old warnings into the new session).
        last_activity = existing.started_at
        from app.models.behavior_event import BehaviorEvent
        latest_event_time = (
            db.query(func.max(BehaviorEvent.event_time))
            .filter(BehaviorEvent.attempt_id == existing.id)
            .scalar()
        )
        if latest_event_time and (
            last_activity is None or latest_event_time > last_activity
        ):
            last_activity = latest_event_time

        if last_activity is None:
            return existing

        now = datetime.now(timezone.utc)
        # Some DBs hand back naive datetimes; normalise to UTC so the
        # subtraction below doesn't raise.
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        idle_seconds = (now - last_activity).total_seconds()
        if idle_seconds < STALE_ATTEMPT_SECONDS:
            return existing

        # Orphaned attempt - close it server-side and fall through to
        # create a fresh one.
        _close_stale_attempt(
            db,
            existing,
            reason=f"auto_closed_stale_after_{int(idle_seconds)}s",
        )
        # Re-check the attempt limit now that we've consumed one. We use
        # the freshly committed state so the count includes the just-
        # closed orphan.
        summary = get_attempt_summary(db, test, student.id)
        if not summary.can_attempt:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt limit reached")

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

    # Audit-only row. The candidate has no live IN_PROGRESS attempt, so
    # nothing real is being ended - we record the End Session signal for
    # forensics but mark it ``orphan_*`` so it does NOT count against
    # ``attempts_used``. Otherwise a stray "End" ping (kiosk crash on
    # launch, double-click on the close button, etc.) would silently
    # burn one of the candidate's tries.
    orphan_reason = f"orphan_{reason}" if reason else "orphan_no_active_attempt"
    attempt = TestAttempt(
        test_id=test.id,
        student_id=student.id,
        assignment_id=assignment.id,
        status=AttemptStatus.ENDED,
        started_at=now,
        ended_at=now,
        ended_reason=orphan_reason,
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
