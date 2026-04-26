from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.test_attempt import AttemptStatus


class AttemptEndRequest(BaseModel):
    reason: str | None = None


class TestAttemptResponse(BaseModel):
    id: int
    test_id: int
    student_id: int
    status: AttemptStatus
    started_at: datetime
    ended_at: datetime | None
    ended_reason: str | None

    model_config = ConfigDict(from_attributes=True)


class AttemptSummaryResponse(BaseModel):
    test_id: int
    student_id: int
    max_attempts: int
    attempts_used: int
    attempts_remaining: int
    can_attempt: bool


class AttemptWithSummaryResponse(BaseModel):
    attempt: TestAttemptResponse
    summary: AttemptSummaryResponse
    # Capability token issued at attempt-start. The WebClient forwards
    # this to the kiosk via the launch URL; the kiosk uses it for ALL
    # subsequent calls (telemetry, warning poll, End Session) so its
    # auth lifetime is tied to the exam window rather than the
    # student's WebClient JWT.
    #
    # Optional because the End Session response reuses this schema and
    # has no use for a fresh token at that point.
    kiosk_token: str | None = None
