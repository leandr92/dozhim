from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool
    correlation_id: str
    severity: str


class JobAccepted(BaseModel):
    job_id: str
    status: str = "queued"
