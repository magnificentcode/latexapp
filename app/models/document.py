# app/models/document.py

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentCreate(BaseModel):
    title: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class DocumentSummary(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
