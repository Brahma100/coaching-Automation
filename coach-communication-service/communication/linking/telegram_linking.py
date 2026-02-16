from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


@dataclass(frozen=True)
class TelegramLinkClaims:
    jti: str
    tenant_id: str
    user_id: str
    phone: str
    purpose: str
    iat: int
    exp: int


class TelegramLinkCodec:
    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("token secret is required")
        self.secret = secret.encode("utf-8")

    def issue_token(
        self,
        *,
        tenant_id: str,
        user_id: str,
        phone: str,
        ttl_seconds: int = 600,
        purpose: str = "telegram_link",
    ) -> tuple[str, TelegramLinkClaims]:
        now = datetime.now(tz=timezone.utc)
        ttl = max(60, int(ttl_seconds))
        clean_phone = _normalize_phone(phone)
        if len(clean_phone) < 10:
            raise ValueError("phone must contain at least 10 digits")
        tenant = str(tenant_id or "").strip() or "default"
        user = str(user_id or "").strip()
        if not user:
            raise ValueError("user_id is required")
        exp = int((now + timedelta(seconds=ttl)).timestamp())
        exp_b36 = format(exp, "x")
        nonce = secrets.token_hex(3)
        signing_payload = f"{purpose}|{user}|{clean_phone}|{tenant}|{exp_b36}|{nonce}"
        signature = hmac.new(self.secret, signing_payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        token = f"v1.{user}.{exp_b36}.{clean_phone}.{tenant}.{nonce}.{signature}"
        claims = TelegramLinkClaims(
            jti=nonce,
            tenant_id=tenant,
            user_id=user,
            phone=clean_phone,
            purpose=str(purpose or "telegram_link"),
            iat=int(now.timestamp()),
            exp=exp,
        )
        return token, claims

    def decode_token(self, token: str, *, purpose: str = "telegram_link") -> TelegramLinkClaims:
        raw = str(token or "").strip()
        parts = raw.split(".")
        if len(parts) != 7 or parts[0] != "v1":
            raise ValueError("invalid_token_format")
        _, user, exp_b36, phone, tenant, nonce, provided_signature = parts
        try:
            exp = int(exp_b36, 16)
        except Exception as exc:
            raise ValueError("invalid_token_claims") from exc
        signing_payload = f"{purpose}|{user}|{_normalize_phone(phone)}|{tenant}|{exp_b36}|{nonce}"
        expected_signature = hmac.new(self.secret, signing_payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise ValueError("invalid_token_signature")
        claims = TelegramLinkClaims(
            jti=nonce,
            tenant_id=str(tenant or ""),
            user_id=str(user or ""),
            phone=_normalize_phone(str(phone or "")),
            purpose=str(purpose or "telegram_link"),
            iat=max(0, exp - 3600),
            exp=exp,
        )
        if not claims.jti or not claims.user_id or len(claims.phone) < 10:
            raise ValueError("invalid_token_claims")
        if claims.purpose != purpose:
            raise ValueError("invalid_token_purpose")
        if claims.exp <= int(datetime.now(tz=timezone.utc).timestamp()):
            raise ValueError("token_expired")
        return claims


def build_telegram_deep_link(bot_username: str, token: str) -> str:
    username = str(bot_username or "").strip().lstrip("@")
    if not username:
        raise ValueError("telegram bot username is required")
    if len(str(token or "")) > 58:
        raise ValueError("telegram deep-link token is too long")
    payload = f"link_{token}"
    return f"https://t.me/{username}?start={payload}"


def parse_link_start_update(update: dict[str, Any]) -> tuple[str, str] | None:
    msg = (update or {}).get("message") or (update or {}).get("edited_message") or {}
    text = str(msg.get("text") or "").strip()
    if not text:
        return None
    chunks = text.split(maxsplit=1)
    command = chunks[0].lower()
    if not command.startswith("/start"):
        return None
    if len(chunks) < 2:
        return None
    payload = chunks[1].strip()
    if not payload.startswith("link_"):
        return None
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id") or "").strip()
    token = payload.removeprefix("link_").strip()
    if not token or not chat_id:
        return None
    return token, chat_id
