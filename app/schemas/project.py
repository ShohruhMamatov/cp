from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.membership import Role
from app.schemas.document import DocumentOut


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    # Every field optional, so a PUT sending only `name` doesn't wipe the
    # description. Applied with model_dump(exclude_unset=True).
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class ProjectInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    total_size_bytes: int
    created_at: datetime
    updated_at: datetime


class ProjectFull(ProjectInfo):
    documents: list[DocumentOut] = []
    role: Role | None = None