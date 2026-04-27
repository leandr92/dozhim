from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
    severity: str | None = None


def severity_from_status(status_code: int) -> str:
    if status_code >= 500:
        return "error"
    if status_code in (400, 404, 409, 422):
        return "warning"
    return "info"
