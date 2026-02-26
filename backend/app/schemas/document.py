from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class DocumentCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=500)
    document_type: str


class DocumentResponse(BaseSchema):
    id: UUID
    deal_id: UUID
    title: str
    document_type: str
    file_size: int
    uploaded_by: UUID
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseSchema):
    document_id: UUID
    upload_url: str
    file_key: str


class DocumentDownloadResponse(BaseSchema):
    download_url: str
