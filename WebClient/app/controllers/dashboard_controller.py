from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.assignment import TestAssignment
from app.models.test import Test
from app.services.attempt_service import get_attempt_summary_map


def _normalize_for_compare(value: datetime) -> datetime:
    # Normalize datetimes to naive UTC for consistent comparisons.
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def my_assigned_tests_controller(db: Session, user_id: int):
    assigned_tests = (
        db.query(Test)
        .join(TestAssignment, TestAssignment.test_id == Test.id)
        .filter(TestAssignment.student_id == user_id)
        .order_by(Test.id.desc())
        .all()
    )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    visible_tests = []
    for test in assigned_tests:
        start = _normalize_for_compare(test.start_time)
        end = _normalize_for_compare(test.end_time)
        if test.is_active and start <= now <= end:
            visible_tests.append(test)

    response = []
    for test in visible_tests:
        summary = get_attempt_summary_map(db, test, [user_id])[user_id]
        response.append(
            {
                "id": test.id,
                "name": test.name,
                "description": test.description,
                "external_link": test.external_link,
                "is_active": test.is_active,
                "max_attempts": test.max_attempts,
                "start_time": test.start_time,
                "end_time": test.end_time,
                "attempts_used": summary.attempts_used,
                "attempts_remaining": summary.attempts_remaining,
                "can_attempt": summary.can_attempt,
            }
        )
    return response
