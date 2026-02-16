from __future__ import annotations

from datetime import datetime
from typing import Any

from communication.core.state_store import InMemoryStore
from communication.core.template_engine import TemplateEngine
from communication.models import MessageQueueItem, MessageTemplate, NotificationRule


class MessageDispatcher:
    def __init__(self, store: InMemoryStore, template_engine: TemplateEngine) -> None:
        self.store = store
        self.template_engine = template_engine

    async def dispatch_event(
        self,
        tenant_id: str,
        event: str,
        user_id: str,
        payload: dict[str, Any],
    ) -> int:
        rules = [
            rule for rule in self.store.rules.values()
            if rule.tenant_id == tenant_id and rule.event == event and rule.enabled
        ]
        created = 0
        for rule in rules:
            template = self._resolve_template(tenant_id, rule)
            if not template:
                continue
            recipients = payload.get("recipients") or [str(user_id)]
            for recipient in recipients:
                content = self.template_engine.render(template.body, payload, rule.preferred_providers[0])
                queue_item = MessageQueueItem(
                    id=self.store.new_id(),
                    tenant_id=tenant_id,
                    event=event,
                    recipient_id=str(recipient),
                    preferred_providers=rule.preferred_providers,
                    content=content,
                    payload=payload,
                    critical=bool(payload.get("critical", False)),
                    next_attempt_at=datetime.utcnow(),
                )
                await self.store.add_queue_item(queue_item)
                created += 1
        if created == 0 and payload.get("message"):
            recipients = payload.get("recipients") or [str(user_id)]
            providers = payload.get("preferred_providers") or ["telegram", "whatsapp"]
            for recipient in recipients:
                queue_item = MessageQueueItem(
                    id=self.store.new_id(),
                    tenant_id=tenant_id,
                    event=event,
                    recipient_id=str(recipient),
                    preferred_providers=[str(p) for p in providers],
                    content=str(payload["message"]),
                    payload=payload,
                    critical=bool(payload.get("critical", False)),
                    next_attempt_at=datetime.utcnow(),
                )
                await self.store.add_queue_item(queue_item)
                created += 1
        return created

    def _resolve_template(self, tenant_id: str, rule: NotificationRule) -> MessageTemplate | None:
        candidates = [
            t for t in self.store.templates.values()
            if t.tenant_id == tenant_id and t.id == rule.template_id and t.active
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.version)
