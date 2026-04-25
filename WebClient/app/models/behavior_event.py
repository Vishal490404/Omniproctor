import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BehaviorEventType(str, enum.Enum):
    # Legacy values kept for backward-compatibility with existing rows.
    TAB_SWITCH = "TAB_SWITCH"
    WINDOW_SWITCH = "WINDOW_SWITCH"
    KEYBOARD_PRESS = "KEYBOARD_PRESS"
    COPY = "COPY"
    PASTE = "PASTE"

    # Proctoring telemetry emitted by the kiosk Browser. Each new value MUST
    # also be added to ``ensure_schema_compatibility`` in ``app/main.py`` so
    # existing Postgres databases can ``ALTER TYPE ... ADD VALUE IF NOT
    # EXISTS`` without a full migration.
    FOCUS_LOSS = "FOCUS_LOSS"
    FOCUS_REGAIN = "FOCUS_REGAIN"
    MONITOR_COUNT_CHANGE = "MONITOR_COUNT_CHANGE"
    KEYSTROKE = "KEYSTROKE"
    BLOCKED_HOTKEY = "BLOCKED_HOTKEY"
    CLIPBOARD_COPY = "CLIPBOARD_COPY"
    CLIPBOARD_PASTE = "CLIPBOARD_PASTE"
    VM_DETECTED = "VM_DETECTED"
    SUSPICIOUS_PROCESS = "SUSPICIOUS_PROCESS"
    NETWORK_BLOCKED = "NETWORK_BLOCKED"
    FULLSCREEN_EXIT = "FULLSCREEN_EXIT"
    RENDERER_CRASH = "RENDERER_CRASH"
    WARNING_DELIVERED = "WARNING_DELIVERED"


# Severity levels accepted by ``BehaviorEvent.severity``. The string column
# stays free-form for forward compatibility, but the kiosk + WebClient agree
# on these constants.
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_CRITICAL = "critical"
ALLOWED_SEVERITIES = {SEVERITY_INFO, SEVERITY_WARN, SEVERITY_CRITICAL}


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