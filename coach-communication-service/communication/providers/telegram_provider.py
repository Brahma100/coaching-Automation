from __future__ import annotations

from typing import Any

import httpx

from communication.providers.base import BaseProvider


class TelegramProvider(BaseProvider):
    name = "telegram"

    async def send_message(self, config: dict[str, Any], recipient_id: str, content: str) -> dict[str, Any]:
        token = config.get("bot_token")
        if not token:
            return {"ok": False, "error": "Missing bot_token"}
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": recipient_id, "text": content}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
        body = response.json()
        return {"ok": bool(body.get("ok")), "provider_response": body}

    async def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        ok = bool(config.get("bot_token"))
        return ok, "bot_token is required" if not ok else "valid"

    async def health_check(self, config: dict[str, Any]) -> tuple[bool, str]:
        token = config.get("bot_token")
        if not token:
            return False, "Missing bot_token"
        url = f"https://api.telegram.org/bot{token}/getMe"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
        if response.status_code != 200:
            return False, f"status={response.status_code}"
        payload = response.json()
        return bool(payload.get("ok")), "healthy" if payload.get("ok") else "invalid token"
