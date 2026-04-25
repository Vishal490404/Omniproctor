from fastapi import APIRouter

from app.api.deps import AdminTeacherProctor, DBSession
from app.controllers.user_controller import list_students_controller
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/students", response_model=list[UserResponse])
def list_students(_: AdminTeacherProctor, db: DBSession):
    return list_students_controller(db)
