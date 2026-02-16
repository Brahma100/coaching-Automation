from __future__ import annotations

from typing import Any

import httpx

from communication.providers.base import BaseProvider


class WhatsAppProvider(BaseProvider):
    name = "whatsapp"

    async def send_message(self, config: dict[str, Any], recipient_id: str, content: str) -> dict[str, Any]:
        phone_number_id = config.get("phone_number_id")
        access_token = config.get("access_token")
        if not phone_number_id or not access_token:
            return {"ok": False, "error": "Missing phone_number_id/access_token"}

        url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "type": "text",
            "text": {"body": content},
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload, headers=headers)
        body = response.json()
        return {"ok": response.status_code < 300, "provider_response": body}

    async def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        required = ["phone_number_id", "access_token", "webhook_verify_token"]
        missing = [key for key in required if not config.get(key)]
        if missing:
            return False, f"Missing fields: {', '.join(missing)}"
        return True, "valid"

    async def health_check(self, config: dict[str, Any]) -> tuple[bool, str]:
        phone_number_id = config.get("phone_number_id")
        access_token = config.get("access_token")
        if not phone_number_id or not access_token:
            return False, "Missing phone_number_id/access_token"
        url = f"https://graph.facebook.com/v21.0/{phone_number_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
        return response.status_code < 300, f"status={response.status_code}"
