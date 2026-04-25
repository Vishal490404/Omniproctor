from sqlalchemy.orm import Session

from app.models.test import Test
from app.models.user import User
from app.schemas.test import TestCreateRequest, TestUpdateRequest
from app.services.test_service import create_test, ensure_manage_permission, get_test_or_404, update_test


def create_test_controller(db: Session, payload: TestCreateRequest, current_user: User):
    return create_test(db, payload, current_user)


def get_test_controller(db: Session, test_id: int) -> Test:
    return get_test_or_404(db, test_id)


def update_test_controller(db: Session, test_id: int, payload: TestUpdateRequest, current_user: User):
    test = get_test_or_404(db, test_id)
    ensure_manage_permission(test, current_user)
    return update_test(db, test, payload)


def ensure_test_manage_permission_controller(db: Session, test_id: int, current_user: User) -> Test:
    test = get_test_or_404(db, test_id)
    ensure_manage_permission(test, current_user)
    return test
