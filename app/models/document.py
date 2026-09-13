# app/models/document.py

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.config import MAX_DOCUMENT_CONTENT_BYTES


class DocumentCreate(BaseModel):
    title: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    center_text: bool | None = None

    @field_validator("content")
    @classmethod
    def content_within_size_limit(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > MAX_DOCUMENT_CONTENT_BYTES:
            limit_mb = MAX_DOCUMENT_CONTENT_BYTES / (1024 * 1024)
            raise ValueError(f"Document content exceeds the {limit_mb:.0f}MB size limit.")
        return value


class DocumentSummary(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    center_text: bool
    created_at: datetime
    updated_at: datetime
