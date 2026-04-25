from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TestAssignment(Base, TimestampMixin):
    __tablename__ = "test_assignments"
    __table_args__ = (
        UniqueConstraint("test_id", "student_id", name="uq_test_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    test = relationship("Test", back_populates="assignments")
    student = relationship("User", back_populates="assignments", foreign_keys=[student_id])
    attempts = relationship("TestAttempt", back_populates="assignment", cascade="all, delete-orphan")
