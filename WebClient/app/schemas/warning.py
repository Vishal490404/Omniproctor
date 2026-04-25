"""Pydantic models for the teacher → student proctor warning channel."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.behavior_event import ALLOWED_SEVERITIES

MAX_MESSAGE_LENGTH = 1000


class ProctorWarningCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    severity: str = "warn"

    @field_validator("severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        normalized = (value or "warn").lower().strip()
        return normalized if normalized in ALLOWED_SEVERITIES else "warn"


class ProctorWarningResponse(BaseModel):
    id: int
    attempt_id: int
    sender_id: int | None
    sender_name: str | None = None
    message: str
    severity: str
    created_at: datetime
    delivered_at: datetime | None
    acknowledged_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ProctorWarningAckRequest(BaseModel):
    delivered_at: datetime | None = None
