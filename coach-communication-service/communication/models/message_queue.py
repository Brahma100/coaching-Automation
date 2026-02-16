from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from communication.models.message_log import MessageStatus


class MessageQueueItem(BaseModel):
    id: str
    tenant_id: str
    event: str
    recipient_id: str
    preferred_providers: list[str]
    current_provider_index: int = 0
    content: str
    payload: dict[str, Any] = Field(default_factory=dict)
    critical: bool = False
    status: MessageStatus = MessageStatus.pending
    retry_count: int = 0
    next_attempt_at: datetime = Field(default_factory=datetime.utcnow)
    max_retries: int = 4
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def active_provider(self) -> str:
        if not self.preferred_providers:
            return ""
        return self.preferred_providers[self.current_provider_index]
