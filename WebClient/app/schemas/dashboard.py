from datetime import datetime

from pydantic import BaseModel


class StudentAssignedTestResponse(BaseModel):
    id: int
    name: str
    description: str | None
    external_link: str
    is_active: bool
    max_attempts: int
    start_time: datetime
    end_time: datetime
    attempts_used: int
    attempts_remaining: int
    can_attempt: bool
