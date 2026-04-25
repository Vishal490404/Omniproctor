import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class TestAttempt(Base, TimestampMixin):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("test_assignments.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus), default=AttemptStatus.IN_PROGRESS, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    test = relationship("Test", back_populates="attempts")
    student = relationship("User", back_populates="attempts", foreign_keys=[student_id])
    assignment = relationship("TestAssignment", back_populates="attempts")
    events = relationship("BehaviorEvent", back_populates="attempt", cascade="all, delete-orphan")