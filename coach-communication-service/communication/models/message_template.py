from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MessageTemplate(BaseModel):
    id: str
    tenant_id: str
    name: str
    event: str
    provider: str
    body: str
    version: int = 1
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MessageTemplateUpsert(BaseModel):
    tenant_id: str
    name: str
    event: str
    provider: str
    body: str
    active: bool = True
