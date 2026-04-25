from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator, model_validator


def _normalize_external_link(value: str | None):
    if value is None:
        return value

    if not isinstance(value, str):
        return value

    cleaned = value.strip()
    if cleaned and "://" not in cleaned:
        return f"https://{cleaned}"
    return cleaned


class TestCreateRequest(BaseModel):
    name: str
    description: str | None = None
    external_link: HttpUrl
    is_active: bool = True
    max_attempts: int = 1
    start_time: datetime
    end_time: datetime

    @field_validator("external_link", mode="before")
    @classmethod
    def normalize_external_link(cls, value):
        return _normalize_external_link(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        return self


class TestUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    external_link: HttpUrl | None = None
    is_active: bool | None = None
    max_attempts: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    @field_validator("external_link", mode="before")
    @classmethod
    def normalize_external_link(cls, value):
        return _normalize_external_link(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        if self.max_attempts is not None and self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        return self


class TestResponse(BaseModel):
    id: int
    name: str
    description: str | None
    external_link: str
    is_active: bool
    max_attempts: int
    start_time: datetime
    end_time: datetime
    created_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
