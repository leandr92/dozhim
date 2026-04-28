from pydantic import BaseModel, Field, model_validator


class EscalationPolicy(BaseModel):
    reminder_cadence_hours: int = Field(default=24, ge=1, le=168)
    max_text_touches: int = Field(default=3, ge=1, le=20)
    notify_manager: bool = False


class CalendarPolicy(BaseModel):
    timezone: str = Field(default="Europe/Moscow", min_length=3, max_length=64)
    workday_start_local: str = Field(default="10:00", min_length=4, max_length=5)
    workday_end_local: str = Field(default="18:00", min_length=4, max_length=5)
    quiet_days: list[str] = Field(default_factory=lambda: ["saturday", "sunday"])

    @model_validator(mode="after")
    def validate_time_bounds(self) -> "CalendarPolicy":
        if self.workday_start_local >= self.workday_end_local:
            raise ValueError("workday_start_local must be earlier than workday_end_local")
        return self


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    title_template: str = Field(min_length=1, max_length=255)
    description: str | None = None
    default_deadline_days: int = Field(default=7, ge=1, le=365)
    verification_policy: dict = Field(default_factory=dict)
    escalation_policy: EscalationPolicy = Field(default_factory=EscalationPolicy)
    calendar_policy: CalendarPolicy = Field(default_factory=CalendarPolicy)


class TemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    title_template: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    default_deadline_days: int | None = Field(default=None, ge=1, le=365)
    verification_policy: dict | None = None
    escalation_policy: EscalationPolicy | None = None
    calendar_policy: CalendarPolicy | None = None
    status: str | None = Field(default=None, max_length=64)
