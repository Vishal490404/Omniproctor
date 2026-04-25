from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.behavior_event import ALLOWED_SEVERITIES, BehaviorEventType


class BehaviorEventCreateRequest(BaseModel):
    event_type: BehaviorEventType
    payload: dict | None = None
    severity: str = "info"
    event_time: datetime | None = None

    @field_validator("severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        if not value:
            return "info"
        normalized = value.lower().strip()
        if normalized not in ALLOWED_SEVERITIES:
            return "info"
        return normalized


class BehaviorEventResponse(BaseModel):
    id: int
    attempt_id: int
    test_id: int
    student_id: int
    event_type: BehaviorEventType
    payload: dict | None
    severity: str
    event_time: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Batch ingest (used by the kiosk BatchPoster).
# ---------------------------------------------------------------------------
MAX_BATCH_SIZE = 200


class BehaviorEventBatchRequest(BaseModel):
    events: list[BehaviorEventCreateRequest] = Field(default_factory=list)

    @field_validator("events")
    @classmethod
    def _cap_events(cls, value: list[BehaviorEventCreateRequest]) -> list[BehaviorEventCreateRequest]:
        if len(value) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch may not exceed {MAX_BATCH_SIZE} events")
        return value


class BehaviorEventBatchResponse(BaseModel):
    accepted: int
    rejected: int
    latest_warning_id: int | None = None
