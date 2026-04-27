from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AssignmentPatch(BaseModel):
    revision: int
    deadline_at: datetime | None = None
    status: str | None = None
    progress_completion: int | None = Field(default=None, ge=0, le=100)
    progress_note: str | None = None
    next_commitment_date: date | None = None


class AssignmentActionRequest(BaseModel):
    action: str
    revision: int
    payload: dict[str, Any] = Field(default_factory=dict)


class AssignmentCreate(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    target_object_external_key: str = Field(min_length=1, max_length=255)
    target_object_name: str | None = Field(default=None, max_length=255)
    deadline_at: datetime | None = None


class AssignmentRevert(BaseModel):
    revision: int = Field(ge=1)
