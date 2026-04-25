import pytest
from fastapi import HTTPException

from app.models.user import UserRole
from app.services.assignment_service import assign_student


def test_assign_student_creates_assignment(db_session, sample_test, student_user, teacher_user):
    assignment = assign_student(
        db_session,
        sample_test,
        student_user,
        teacher_user.id,
        "seat A1",
    )

    assert assignment.id is not None
    assert assignment.test_id == sample_test.id
    assert assignment.student_id == student_user.id


def test_assign_student_rejects_duplicate(db_session, sample_test, student_user, teacher_user):
    assign_student(db_session, sample_test, student_user, teacher_user.id, None)

    with pytest.raises(HTTPException) as exc:
        assign_student(db_session, sample_test, student_user, teacher_user.id, None)

    assert exc.value.status_code == 409


def test_assign_student_requires_student_role(db_session, sample_test, teacher_user):
    non_student = teacher_user
    non_student.role = UserRole.PROCTOR

    with pytest.raises(HTTPException) as exc:
        assign_student(db_session, sample_test, non_student, teacher_user.id, None)

    assert exc.value.status_code == 400
