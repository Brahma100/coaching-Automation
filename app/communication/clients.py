from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class BaseCommunicationClient:
    def emit_event(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
            logger.warning("communication_emit_called_in_running_loop", extra={"event": event})
            return {"queued": False, "error": "running_event_loop"}
        except RuntimeError:
            return asyncio.run(self.emit_event_async(event, payload))

    async def emit_event_async(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def create_telegram_link_token(
        self,
        *,
        tenant_id: str,
        user_id: str,
        phone: str,
        bot_username: str,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
            logger.warning("telegram_link_token_called_in_running_loop")
            return {"ok": False, "error": "running_event_loop"}
        except RuntimeError:
            return asyncio.run(
                self.create_telegram_link_token_async(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    phone=phone,
                    bot_username=bot_username,
                    ttl_seconds=ttl_seconds,
                )
            )

    async def create_telegram_link_token_async(
        self,
        *,
        tenant_id: str,
        user_id: str,
        phone: str,
        bot_username: str,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def consume_telegram_link_update(self, *, update: dict[str, Any], expected_tenant_id: str) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
            logger.warning("telegram_link_consume_called_in_running_loop")
            return {"matched": False, "reason": "running_event_loop"}
        except RuntimeError:
            return asyncio.run(
                self.consume_telegram_link_update_async(
                    update=update,
                    expected_tenant_id=expected_tenant_id,
                )
            )

    async def consume_telegram_link_update_async(
        self,
        *,
        update: dict[str, Any],
        expected_tenant_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError


class EmbeddedCommunicationClient(BaseCommunicationClient):
    async def emit_event_async(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = str(payload.get("tenant_id") or settings.communication_tenant_id)
        user_id = str(payload.get("user_id") or "system")
        data_payload = dict(payload.get("payload") or payload)

        service_repo = Path(__file__).resolve().parents[2] / "coach-communication-service"
        if service_repo.exists() and str(service_repo) not in sys.path:
            sys.path.append(str(service_repo))

        # Import lazily so this app can still boot even if communication service
        # package is not installed in environments using remote mode.
        from communication.app_state import get_context  # type: ignore
        from communication.core.message_dispatcher import MessageDispatcher  # type: ignore

        ctx = get_context()
        dispatcher = ctx.dispatcher
        if not isinstance(dispatcher, MessageDispatcher):
            return {"queued": False, "error": "invalid_dispatcher", "mode": "embedded"}

        created = await dispatcher.dispatch_event(
            tenant_id=tenant_id,
            event=event,
            user_id=user_id,
            payload=data_payload,
        )
        return {"queued": created > 0, "created": created, "mode": "embedded"}

    async def create_telegram_link_token_async(
        self,
        *,
        tenant_id: str,
        user_id: str,
        phone: str,
        bot_username: str,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        service_repo = Path(__file__).resolve().parents[2] / "coach-communication-service"
        if service_repo.exists() and str(service_repo) not in sys.path:
            sys.path.append(str(service_repo))
        from communication.linking import create_link_session  # type: ignore

        return create_link_session(
            tenant_id=tenant_id,
            user_id=user_id,
            phone=phone,
            bot_username=bot_username,
            ttl_seconds=ttl_seconds,
        )

    async def consume_telegram_link_update_async(
        self,
        *,
        update: dict[str, Any],
        expected_tenant_id: str,
    ) -> dict[str, Any]:
        service_repo = Path(__file__).resolve().parents[2] / "coach-communication-service"
        if service_repo.exists() and str(service_repo) not in sys.path:
            sys.path.append(str(service_repo))
        from communication.linking import consume_link_update  # type: ignore

        return consume_link_update(update, expected_tenant_id=expected_tenant_id)


class RemoteCommunicationClient(BaseCommunicationClient):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def emit_event_async(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "event": event,
            "tenant_id": str(payload.get("tenant_id") or settings.communication_tenant_id),
            "user_id": str(payload.get("user_id") or "system"),
            "payload": dict(payload.get("payload") or payload),
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10) as client:
            response = await client.post("/events/emit", json=body)
            if response.status_code == 404:
                response = await client.post("/api/messages/events", json=body)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return {**data, "mode": "remote"}
            return {"queued": True, "mode": "remote"}

    async def create_telegram_link_token_async(
        self,
        *,
        tenant_id: str,
        user_id: str,
        phone: str,
        bot_username: str,
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        body = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "phone": phone,
            "bot_username": bot_username,
            "ttl_seconds": ttl_seconds,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10, headers={"x-role": "admin"}) as client:
            response = await client.post("/api/telegram/link-token", json=body)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return {"ok": False, "error": "invalid_response"}

    async def consume_telegram_link_update_async(
        self,
        *,
        update: dict[str, Any],
        expected_tenant_id: str,
    ) -> dict[str, Any]:
        body = {"update": update, "expected_tenant_id": expected_tenant_id}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=10) as client:
            response = await client.post("/api/telegram/consume-link-update", json=body)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return {"matched": False, "reason": "invalid_response"}
