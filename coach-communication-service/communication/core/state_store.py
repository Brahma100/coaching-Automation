from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from communication.models import (
    MessageLog,
    MessageQueueItem,
    MessageStatus,
    MessageTemplate,
    NotificationRule,
    ProviderConfig,
)


class InMemoryStore:
    def __init__(self) -> None:
        self.provider_configs: dict[str, ProviderConfig] = {}
        self.templates: dict[str, MessageTemplate] = {}
        self.rules: dict[str, NotificationRule] = {}
        self.queue: dict[str, MessageQueueItem] = {}
        self.logs: dict[str, MessageLog] = {}
        self.metrics: dict[str, int] = {
            "sent": 0,
            "delivered": 0,
            "failed": 0,
            "retry_count": 0,
        }
        self.audit: list[dict[str, Any]] = []
        self.quiet_hours: dict[str, tuple[int, int]] = {}
        self._lock = asyncio.Lock()

    def new_id(self) -> str:
        return str(uuid4())

    async def add_queue_item(self, item: MessageQueueItem) -> None:
        async with self._lock:
            self.queue[item.id] = item

    async def upsert_provider(self, config: ProviderConfig) -> None:
        async with self._lock:
            self.provider_configs[config.id] = config

    async def upsert_template(self, template: MessageTemplate) -> None:
        async with self._lock:
            older = [
                t for t in self.templates.values()
                if t.tenant_id == template.tenant_id and t.name == template.name
            ]
            if older:
                template.version = max(t.version for t in older) + 1
            self.templates[template.id] = template

    async def upsert_rule(self, rule: NotificationRule) -> None:
        async with self._lock:
            self.rules[rule.id] = rule

    async def write_log(
        self,
        queue_id: str,
        tenant_id: str,
        provider: str,
        status: MessageStatus,
        response: dict[str, Any],
    ) -> MessageLog:
        log = MessageLog(
            id=self.new_id(),
            queue_id=queue_id,
            tenant_id=tenant_id,
            provider=provider,
            status=status,
            response=response,
        )
        async with self._lock:
            self.logs[log.id] = log
            if status == MessageStatus.sending:
                self.metrics["sent"] += 1
            elif status == MessageStatus.delivered:
                self.metrics["delivered"] += 1
            elif status == MessageStatus.failed:
                self.metrics["failed"] += 1
            elif status == MessageStatus.retrying:
                self.metrics["retry_count"] += 1
        return log

    async def add_audit(self, action: str, actor: str, details: dict[str, Any]) -> None:
        async with self._lock:
            self.audit.append(
                {
                    "id": self.new_id(),
                    "action": action,
                    "actor": actor,
                    "details": details,
                    "at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )
