from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.deps import AdminOrTeacher, AdminTeacherProctor, CurrentUser, DBSession
from app.models.assignment import TestAssignment
from app.controllers.test_controller import create_test_controller, get_test_controller, update_test_controller
from app.models.test import Test
from app.models.user import UserRole
from app.schemas.test import TestCreateRequest, TestResponse, TestUpdateRequest

router = APIRouter()


@router.post("", response_model=TestResponse)
def create_test_endpoint(payload: TestCreateRequest, db: DBSession, current_user: AdminOrTeacher):
    return create_test_controller(db, payload, current_user)


@router.get("", response_model=list[TestResponse])
def list_tests(
    db: DBSession,
    current_user: CurrentUser,
    include_inactive: bool = Query(default=True),
):
    query = db.query(Test)

    if current_user.role == UserRole.TEACHER:
        query = query.filter(Test.created_by == current_user.id)
    elif current_user.role == UserRole.STUDENT:
        query = query.join(TestAssignment, TestAssignment.test_id == Test.id).filter(
            TestAssignment.student_id == current_user.id,
            Test.is_active.is_(True),
        )

    if not include_inactive:
        query = query.filter(Test.is_active.is_(True))

    results = query.order_by(Test.id.desc()).all()

    if current_user.role != UserRole.STUDENT:
        return results

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    filtered = []
    for item in results:
        start = item.start_time.astimezone(timezone.utc).replace(tzinfo=None) if item.start_time.tzinfo else item.start_time
        end = item.end_time.astimezone(timezone.utc).replace(tzinfo=None) if item.end_time.tzinfo else item.end_time
        if start <= now <= end:
            filtered.append(item)
    return filtered


@router.get("/{test_id}", response_model=TestResponse)
def get_test(test_id: int, db: DBSession, _: AdminTeacherProctor):
    return get_test_controller(db, test_id)


@router.patch("/{test_id}", response_model=TestResponse)
def update_test_endpoint(
    test_id: int,
    payload: TestUpdateRequest,
    db: DBSession,
    current_user: AdminOrTeacher,
):
    return update_test_controller(db, test_id, payload, current_user)
