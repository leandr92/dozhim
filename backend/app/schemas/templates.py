from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    title_template: str = Field(min_length=1, max_length=255)
    description: str | None = None
    default_deadline_days: int = Field(default=7, ge=1, le=365)
    verification_policy: dict = Field(default_factory=dict)
    escalation_policy: dict = Field(default_factory=dict)
    calendar_policy: dict = Field(default_factory=dict)


class TemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    title_template: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    default_deadline_days: int | None = Field(default=None, ge=1, le=365)
    verification_policy: dict | None = None
    escalation_policy: dict | None = None
    calendar_policy: dict | None = None
    status: str | None = Field(default=None, max_length=64)
