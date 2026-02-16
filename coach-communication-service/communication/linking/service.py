from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from communication.linking.telegram_linking import (
    TelegramLinkCodec,
    build_telegram_deep_link,
    parse_link_start_update,
)


def _secret() -> str:
    return os.getenv("COMMUNICATION_LINK_TOKEN_SECRET", "change-me-link-secret")


def _default_ttl_seconds() -> int:
    raw = os.getenv("COMMUNICATION_LINK_TOKEN_TTL_SECONDS", "600")
    try:
        return max(60, int(raw))
    except ValueError:
        return 600


def create_link_session(
    *,
    tenant_id: str,
    user_id: str,
    phone: str,
    bot_username: str,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    codec = TelegramLinkCodec(_secret())
    token, claims = codec.issue_token(
        tenant_id=tenant_id,
        user_id=user_id,
        phone=phone,
        ttl_seconds=(ttl_seconds if ttl_seconds is not None else _default_ttl_seconds()),
    )
    return {
        "token": token,
        "deep_link": build_telegram_deep_link(bot_username, token),
        "phone": claims.phone,
        "tenant_id": claims.tenant_id,
        "user_id": claims.user_id,
        "issued_at": datetime.fromtimestamp(claims.iat, tz=timezone.utc).isoformat(),
        "expires_at": datetime.fromtimestamp(claims.exp, tz=timezone.utc).isoformat(),
    }


def consume_link_update(update: dict[str, Any], *, expected_tenant_id: str | None = None) -> dict[str, Any]:
    parsed = parse_link_start_update(update)
    if not parsed:
        return {"matched": False, "reason": "not_link_start"}
    token, chat_id = parsed
    codec = TelegramLinkCodec(_secret())
    try:
        claims = codec.decode_token(token, purpose="telegram_link")
    except ValueError as exc:
        return {"matched": False, "reason": str(exc)}
    if expected_tenant_id and claims.tenant_id != expected_tenant_id:
        return {"matched": False, "reason": "tenant_mismatch"}
    return {
        "matched": True,
        "chat_id": chat_id,
        "phone": claims.phone,
        "tenant_id": claims.tenant_id,
        "user_id": claims.user_id,
        "jti": claims.jti,
        "issued_at": datetime.fromtimestamp(claims.iat, tz=timezone.utc).isoformat(),
        "expires_at": datetime.fromtimestamp(claims.exp, tz=timezone.utc).isoformat(),
    }
