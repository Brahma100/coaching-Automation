from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cache import cache, cache_key
from app.config import settings
from app.models import CenterIntegration
from app.services.center_scope_service import get_current_center_id


logger = logging.getLogger(__name__)
INTEGRATION_STATUS_TTL_SECONDS = 60


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


def _normalized_provider(provider: str) -> str:
    return str(provider or "").strip().lower()


def _status_cache_key(center_id: int, provider: str) -> str:
    return cache_key("integration_status", f"{int(center_id)}:{_normalized_provider(provider)}")


def _clear_center_integration_cache(center_id: int) -> None:
    cache.invalidate_prefix(cache_key("integration_status", f"{int(center_id)}:"))


def _legacy_connected(provider: str) -> bool:
    p = _normalized_provider(provider)
    if p == "telegram":
        return bool(settings.enable_telegram_notifications and (settings.telegram_bot_token or "").strip())
    return False


def _resolve_center_id(center_id: int | None = None) -> int:
    if int(center_id or 0) > 0:
        return int(center_id)
    current = int(get_current_center_id() or 0)
    return current if current > 0 else 1


def get_integration(db: Session, *, center_id: int, provider: str) -> CenterIntegration | None:
    p = _normalized_provider(provider)
    if not p:
        return None
    return (
        db.query(CenterIntegration)
        .filter(CenterIntegration.center_id == int(center_id), CenterIntegration.provider == p)
        .first()
    )


def is_connected(db: Session, center_id: int, provider: str) -> bool:
    p = _normalized_provider(provider)
    if not p:
        return False
    key = _status_cache_key(int(center_id), p)
    cached = cache.get_cached(key)
    if cached is not None:
        return bool(cached)

    row = get_integration(db, center_id=int(center_id), provider=p)
    connected = bool(row and row.status == "connected")
    if not connected:
        connected = _legacy_connected(p)
    cache.set_cached(key, connected, ttl=INTEGRATION_STATUS_TTL_SECONDS)
    return connected


def require_integration(
    db: Session,
    provider: str,
    *,
    center_id: int | None = None,
) -> dict[str, Any]:
    resolved_center_id = _resolve_center_id(center_id)
    p = _normalized_provider(provider)
    connected = is_connected(db, resolved_center_id, p)
    if connected:
        return {"integration_required": False, "provider": p, "center_id": resolved_center_id}
    return {
        "integration_required": True,
        "provider": p,
        "center_id": resolved_center_id,
        "message": f"Connect {p.title()} to enable this feature",
    }


def list_integrations(db: Session, *, center_id: int) -> list[dict[str, Any]]:
    providers = ("telegram", "whatsapp")
    rows = (
        db.query(CenterIntegration)
        .filter(CenterIntegration.center_id == int(center_id))
        .order_by(CenterIntegration.provider.asc(), CenterIntegration.id.asc())
        .all()
    )
    by_provider = {str(row.provider or "").strip().lower(): row for row in rows}
    payload = []
    for provider in providers:
        row = by_provider.get(provider)
        payload.append(
            {
                "provider": provider,
                "status": (row.status if row else ("connected" if _legacy_connected(provider) else "disconnected")),
                "connected": is_connected(db, int(center_id), provider),
                "connected_at": row.connected_at.isoformat() if row and row.connected_at else None,
                "has_config": bool(row and (row.config_json or "").strip()),
            }
        )
    return payload


def upsert_integration(
    db: Session,
    *,
    center_id: int,
    provider: str,
    status: str = "connected",
    config_json: dict[str, Any] | None = None,
) -> CenterIntegration:
    p = _normalized_provider(provider)
    row = get_integration(db, center_id=int(center_id), provider=p)
    if row is None:
        row = CenterIntegration(
            center_id=int(center_id),
            provider=p,
            status=str(status or "connected").strip().lower(),
            config_json=_encrypt_config(config_json or {}),
            connected_at=datetime.utcnow() if str(status or "").strip().lower() == "connected" else None,
        )
        db.add(row)
    else:
        row.status = str(status or row.status).strip().lower()
        row.config_json = _encrypt_config(config_json or _decrypt_config(row.config_json or ""))
        row.connected_at = datetime.utcnow() if row.status == "connected" else None
        row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    _clear_center_integration_cache(int(center_id))
    return row

