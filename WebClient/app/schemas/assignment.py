from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssignmentCreateRequest(BaseModel):
    note: str | None = None


class AssignmentResponse(BaseModel):
    id: int
    test_id: int
    student_id: int
    added_by: int
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignedStudentResponse(BaseModel):
    assignment_id: int
    student_id: int
    full_name: str
    email: str
    note: str | None
    assigned_at: datetime
    attempts_used: int = 0
    attempts_remaining: int = 0
    max_attempts: int = 1
    can_attempt: bool = True


class AssignmentBulkByEmailRequest(BaseModel):
    emails: list[str]
    note: str | None = None


class AssignmentBulkItemResponse(BaseModel):
    email: str
    status: str
    message: str
    assignment_id: int | None = None
    student_id: int | None = None


class AssignmentBulkResponse(BaseModel):
    test_id: int
    summary: dict[str, int]
    results: list[AssignmentBulkItemResponse]
