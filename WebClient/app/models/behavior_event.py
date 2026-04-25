import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BehaviorEventType(str, enum.Enum):
    TAB_SWITCH = "TAB_SWITCH"
    WINDOW_SWITCH = "WINDOW_SWITCH"
    KEYBOARD_PRESS = "KEYBOARD_PRESS"
    COPY = "COPY"
    PASTE = "PASTE"


class BehaviorEvent(Base, TimestampMixin):
    __tablename__ = "behavior_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[BehaviorEventType] = mapped_column(Enum(BehaviorEventType), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)

    attempt = relationship("TestAttempt", back_populates="events")
    test = relationship("Test")
    student = relationship("User", back_populates="behavior_events", foreign_keys=[student_id])