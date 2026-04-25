from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.test import Test
from app.models.user import User, UserRole
from app.schemas.test import TestCreateRequest, TestUpdateRequest


def create_test(db: Session, payload: TestCreateRequest, creator: User) -> Test:
    test = Test(
        name=payload.name,
        description=payload.description,
        external_link=str(payload.external_link),
        is_active=payload.is_active,
        max_attempts=payload.max_attempts,
        start_time=payload.start_time,
        end_time=payload.end_time,
        created_by=creator.id,
    )
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


def get_test_or_404(db: Session, test_id: int) -> Test:
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


def ensure_manage_permission(test: Test, current_user: User) -> None:
    if current_user.role == UserRole.ADMIN:
        return
    if current_user.role == UserRole.TEACHER and test.created_by == current_user.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted for this test")


def update_test(db: Session, test: Test, payload: TestUpdateRequest) -> Test:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "external_link" and value is not None:
            setattr(test, key, str(value))
        else:
            setattr(test, key, value)

    db.add(test)
    db.commit()
    db.refresh(test)
    return test
