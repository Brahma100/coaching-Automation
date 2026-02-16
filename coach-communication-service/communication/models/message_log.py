from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageStatus(str, Enum):
    pending = "pending"
    sending = "sending"
    delivered = "delivered"
    failed = "failed"
    retrying = "retrying"


class MessageLog(BaseModel):
    id: str
    tenant_id: str
    queue_id: str
    provider: str
    status: MessageStatus
    response: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
