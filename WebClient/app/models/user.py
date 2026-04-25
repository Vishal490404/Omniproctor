import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PROCTOR = "proctor"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_tests = relationship(
        "Test", back_populates="creator", foreign_keys="Test.created_by", cascade="all, delete-orphan"
    )
    assignments = relationship(
        "TestAssignment", back_populates="student", foreign_keys="TestAssignment.student_id", cascade="all, delete-orphan"
    )
    attempts = relationship(
        "TestAttempt", back_populates="student", foreign_keys="TestAttempt.student_id", cascade="all, delete-orphan"
    )
    behavior_events = relationship(
        "BehaviorEvent", back_populates="student", foreign_keys="BehaviorEvent.student_id", cascade="all, delete-orphan"
    )
