from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def list_students_controller(db: Session):
    return db.query(User).filter(User.role == UserRole.STUDENT).order_by(User.id.desc()).all()
