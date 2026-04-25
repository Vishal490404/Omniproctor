from sqlalchemy.orm import Session

from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import login_user, register_user


def register_controller(db: Session, payload: RegisterRequest):
    return register_user(db, payload)


def login_controller(db: Session, payload: LoginRequest):
    return login_user(db, payload)
