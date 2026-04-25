from fastapi import APIRouter

from app.api.deps import DBSession, StudentOnly
from app.controllers.dashboard_controller import my_assigned_tests_controller
from app.schemas.dashboard import StudentAssignedTestResponse

router = APIRouter()


@router.get("/me/tests", response_model=list[StudentAssignedTestResponse])
def my_assigned_tests(db: DBSession, current_user: StudentOnly):
    return my_assigned_tests_controller(db, current_user.id)
