from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.behavior_event import ALLOWED_SEVERITIES, BehaviorEventType


class BehaviorEventCreateRequest(BaseModel):
    event_type: BehaviorEventType
    payload: dict | None = None
    severity: str = "info"
    event_time: datetime | None = None

    @field_validator("event_type", mode="before")
    @classmethod
    def _normalize_event_type(cls, value):
        """Accept event_type strings in any case ("focus_loss" / "Focus_Loss"
        / "FOCUS_LOSS") - upper-case before enum coercion so the kiosk and
        server don't have to agree on case."""
        if isinstance(value, str):
            return value.strip().upper()
        return value

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
    # 1-based sequence among this student's attempts at this test (ordered
    # by started_at). attempt_id is the global test_attempts PK and is
    # not user-meaningful - the UI displays attempt_number. Defaults to 1
    # so older code paths that haven't been updated still produce a sane
    # value.
    attempt_number: int = 1
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
    """Raw batch envelope.

    We deliberately accept ``events`` as a list of arbitrary dicts and let
    the endpoint validate per-item with try/except. If we typed this as
    ``list[BehaviorEventCreateRequest]``, Pydantic would reject the entire
    batch when a single event has an unknown ``event_type`` (e.g. a future
    kiosk version sends a new enum value before the server is upgraded),
    losing up to 199 perfectly valid events with it.
    """

    events: list[dict] = Field(default_factory=list)


class BehaviorEventBatchResponse(BaseModel):
    accepted: int
    rejected: int
    latest_warning_id: int | None = None
