from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.behavior_event import BehaviorEventType


class BehaviorEventCreateRequest(BaseModel):
    event_type: BehaviorEventType
    payload: dict | None = None
    severity: str = "info"
    event_time: datetime | None = None


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
