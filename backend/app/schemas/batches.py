from pydantic import BaseModel, Field


class BatchCreate(BaseModel):
    project_id: str
    template_id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    people_ids: list[str] = Field(default_factory=list)
