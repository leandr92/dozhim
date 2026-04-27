from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    telegram_user_id: str | None = Field(default=None, max_length=255)
    phone: str = Field(min_length=1, max_length=64)
    role: str = Field(default="executor", max_length=64)
    manager_person_id: str | None = None


class PersonPatch(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    telegram_user_id: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=64)
    role: str | None = Field(default=None, max_length=64)
    manager_person_id: str | None = None
    is_active: bool | None = None
