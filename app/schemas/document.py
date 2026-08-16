from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: int
    created_at: datetime