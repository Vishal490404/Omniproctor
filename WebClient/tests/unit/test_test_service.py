import pytest
from fastapi import HTTPException

from app.models.user import UserRole
from app.schemas.test import TestUpdateRequest
from app.services.test_service import ensure_manage_permission, update_test


def test_ensure_manage_permission_allows_admin(sample_test, admin_user):
    ensure_manage_permission(sample_test, admin_user)


def test_ensure_manage_permission_allows_owner_teacher(sample_test, teacher_user):
    ensure_manage_permission(sample_test, teacher_user)


def test_ensure_manage_permission_rejects_other_teacher(db_session, sample_test):
    from app.core.security import get_password_hash
    from app.models.user import User

    other_teacher = User(
        full_name="Other Teacher",
        email="other.teacher@example.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.TEACHER,
        is_active=True,
    )
    db_session.add(other_teacher)
    db_session.commit()
    db_session.refresh(other_teacher)

    with pytest.raises(HTTPException) as exc:
        ensure_manage_permission(sample_test, other_teacher)

    assert exc.value.status_code == 403


def test_update_test_partial_update(db_session, sample_test):
    payload = TestUpdateRequest(name="Updated Name", is_active=False)

    updated = update_test(db_session, sample_test, payload)

    assert updated.name == "Updated Name"
    assert updated.is_active is False
