from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import default_time_provider
from app.models import TeacherCommunicationSettings


DEFAULT_ENABLED_EVENTS = [
    "CLASS_STARTED",
    "ATTENDANCE_SUBMITTED",
    "FEE_DUE",
    "HOMEWORK_ASSIGNED",
    "STUDENT_ADDED",
    "BATCH_RESCHEDULED",
    "DAILY_BRIEF",
]

_ENABLED_EVENTS_CACHE_TTL_SECONDS = 60
_ENABLED_EVENTS_CACHE: dict[int, dict[str, Any]] = {}


def _state_secret() -> bytes:
    return hashlib.sha256((settings.auth_secret or "change-me").encode("utf-8")).digest()


def _encrypt_config(payload: dict[str, Any]) -> str:
    plain = json.dumps(payload or {}, separators=(",", ":")).encode("utf-8")
    if not plain:
        return ""
    nonce = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", _state_secret(), nonce, 120000, dklen=len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, key))
    return base64.urlsafe_b64encode(nonce + cipher).decode("ascii")


def _decrypt_config(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception:
        return {}


def get_provider_config_for_teacher(db: Session, teacher_id: int) -> dict[str, Any]:
    row = get_or_create_teacher_communication_settings(db, int(teacher_id))
    return _decrypt_config(row.provider_config_json or '')
    if len(raw) < 17:
        return {}
    nonce = raw[:16]
    cipher = raw[16:]
    key = hashlib.pbkdf2_hmac("sha256", _state_secret(), nonce, 120000, dklen=len(cipher))
    plain = bytes(a ^ b for a, b in zip(cipher, key))
    try:
        parsed = json.loads(plain.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _safe_json_loads(raw: str, fallback):
    try:
        parsed = json.loads(raw or "")
        return parsed
    except Exception:
        return fallback


def _enabled_events_cache_get(teacher_id: int) -> list[str] | None:
    item = _ENABLED_EVENTS_CACHE.get(int(teacher_id))
    if not item:
        return None
    if item["expires_at"] < default_time_provider.now().replace(tzinfo=None):
        _ENABLED_EVENTS_CACHE.pop(int(teacher_id), None)
        return None
    return list(item["events"])


def _enabled_events_cache_set(teacher_id: int, events: list[str]) -> None:
    _ENABLED_EVENTS_CACHE[int(teacher_id)] = {
        "events": list(events),
        "expires_at": default_time_provider.now().replace(tzinfo=None) + timedelta(seconds=_ENABLED_EVENTS_CACHE_TTL_SECONDS),
    }


def get_or_create_teacher_communication_settings(db: Session, teacher_id: int) -> TeacherCommunicationSettings:
    row = db.query(TeacherCommunicationSettings).filter(TeacherCommunicationSettings.teacher_id == teacher_id).first()
    if row:
        return row
    row = TeacherCommunicationSettings(
        teacher_id=teacher_id,
        provider="telegram",
        provider_config_json=_encrypt_config({}),
        enabled_events=json.dumps(DEFAULT_ENABLED_EVENTS),
        quiet_hours=json.dumps({"start": "22:00", "end": "06:00"}),
        delete_timer_minutes=15,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _enabled_events_cache_set(int(teacher_id), list(DEFAULT_ENABLED_EVENTS))
    return row


def serialize_teacher_communication_settings(row: TeacherCommunicationSettings) -> dict[str, Any]:
    enabled_events = _safe_json_loads(row.enabled_events, DEFAULT_ENABLED_EVENTS)
    if not isinstance(enabled_events, list):
        enabled_events = DEFAULT_ENABLED_EVENTS
    quiet_hours = _safe_json_loads(row.quiet_hours, {"start": "22:00", "end": "06:00"})
    if not isinstance(quiet_hours, dict):
        quiet_hours = {"start": "22:00", "end": "06:00"}

    decrypted_cfg = _decrypt_config(row.provider_config_json)
    health = provider_health(row.provider, decrypted_cfg)
    return {
        "teacher_id": row.teacher_id,
        "provider": row.provider,
        "provider_config_json": decrypted_cfg,
        "enabled_events": enabled_events,
        "quiet_hours": quiet_hours,
        "delete_timer_minutes": row.delete_timer_minutes,
        "connection_status": health,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def update_teacher_communication_settings(
    db: Session,
    teacher_id: int,
    *,
    provider: str,
    provider_config_json: dict[str, Any],
    enabled_events: list[str],
    quiet_hours: dict[str, str],
    delete_timer_minutes: int,
) -> TeacherCommunicationSettings:
    row = get_or_create_teacher_communication_settings(db, teacher_id)
    row.provider = (provider or "telegram").strip().lower()
    row.provider_config_json = _encrypt_config(provider_config_json or {})
    normalized_events = enabled_events or DEFAULT_ENABLED_EVENTS
    row.enabled_events = json.dumps(normalized_events)
    row.quiet_hours = json.dumps(quiet_hours or {"start": "22:00", "end": "06:00"})
    row.delete_timer_minutes = max(1, min(int(delete_timer_minutes or 15), 240))
    row.updated_at = default_time_provider.now().replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    _enabled_events_cache_set(int(teacher_id), list(normalized_events))
    return row


def is_event_enabled_for_teacher(
    db: Session,
    *,
    teacher_id: int | None,
    event_type: str | None,
) -> bool:
    if not teacher_id or not event_type:
        return True
    normalized_event = str(event_type or "").strip().upper()
    if not normalized_event:
        return True

    cached = _enabled_events_cache_get(int(teacher_id))
    if cached is not None:
        return normalized_event in {str(item).strip().upper() for item in cached}

    row = get_or_create_teacher_communication_settings(db, int(teacher_id))
    events = _safe_json_loads(row.enabled_events, DEFAULT_ENABLED_EVENTS)
    if not isinstance(events, list):
        events = list(DEFAULT_ENABLED_EVENTS)
    normalized_events = [str(item).strip().upper() for item in events if str(item).strip()]
    _enabled_events_cache_set(int(teacher_id), normalized_events)
    return normalized_event in set(normalized_events)


def provider_health(provider: str, provider_config: dict[str, Any]) -> dict[str, Any]:
    provider = (provider or "").strip().lower()
    if provider == "telegram":
        token = (provider_config or {}).get("bot_token") or settings.telegram_bot_token
        if not token:
            return {"healthy": False, "status": "missing_config", "message": "Bot token missing"}
        try:
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = httpx.get(url, timeout=8)
            if response.status_code == 200 and response.json().get("ok"):
                return {"healthy": True, "status": "connected", "message": "Telegram connected"}
            return {"healthy": False, "status": "error", "message": f"Telegram status {response.status_code}"}
        except Exception:
            return {"healthy": False, "status": "error", "message": "Telegram health check failed"}

    if provider == "whatsapp":
        phone_number_id = (provider_config or {}).get("phone_number_id")
        access_token = (provider_config or {}).get("access_token")
        if not phone_number_id or not access_token:
            return {"healthy": False, "status": "missing_config", "message": "phone_number_id/access_token missing"}
        try:
            response = httpx.get(
                f"https://graph.facebook.com/v21.0/{phone_number_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=8,
            )
            if response.status_code < 300:
                return {"healthy": True, "status": "connected", "message": "WhatsApp connected"}
            return {"healthy": False, "status": "error", "message": f"WhatsApp status {response.status_code}"}
        except Exception:
            return {"healthy": False, "status": "error", "message": "WhatsApp health check failed"}

    return {"healthy": False, "status": "unsupported", "message": f"Unsupported provider '{provider}'"}


def send_test_message(provider: str, provider_config: dict[str, Any], message: str) -> dict[str, Any]:
    provider = (provider or "").strip().lower()
    text = (message or "Test message from Coaching Communication settings").strip()
    if provider == "telegram":
        token = (provider_config or {}).get("bot_token") or settings.telegram_bot_token
        chat_id = (provider_config or {}).get("chat_id") or settings.auth_otp_fallback_chat_id
        if not token or not chat_id:
            return {"ok": False, "detail": "bot_token/chat_id missing"}
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {"ok": response.status_code == 200 and bool(body.get("ok")), "status_code": response.status_code, "body": body}

    if provider == "whatsapp":
        phone_number_id = (provider_config or {}).get("phone_number_id")
        access_token = (provider_config or {}).get("access_token")
        to = (provider_config or {}).get("to")
        if not phone_number_id or not access_token or not to:
            return {"ok": False, "detail": "phone_number_id/access_token/to missing"}
        response = httpx.post(
            f"https://graph.facebook.com/v21.0/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
            timeout=10,
        )
        body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        return {"ok": response.status_code < 300, "status_code": response.status_code, "body": body}

    return {"ok": False, "detail": f"Unsupported provider '{provider}'"}
