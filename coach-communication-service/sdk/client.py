from __future__ import annotations

from typing import Any

import httpx


class CommunicationClient:
    def __init__(self, base_url: str, timeout: float = 10.0, api_role: str = "admin") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"x-role": api_role}

    def emit_event(self, event: str, tenant_id: str, payload: dict[str, Any], user_id: str = "sdk") -> dict[str, Any]:
        body = {
            "event": event,
            "tenant_id": tenant_id,
            "payload": payload,
            "user_id": user_id,
        }
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=self.headers) as client:
            res = client.post("/api/messages/events", json=body)
            res.raise_for_status()
            return res.json()

    async def emit_event_async(
        self,
        event: str,
        tenant_id: str,
        payload: dict[str, Any],
        user_id: str = "sdk",
    ) -> dict[str, Any]:
        body = {
            "event": event,
            "tenant_id": tenant_id,
            "payload": payload,
            "user_id": user_id,
        }
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, headers=self.headers) as client:
            res = await client.post("/api/messages/events", json=body)
            res.raise_for_status()
            return res.json()
