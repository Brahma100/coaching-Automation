from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.communication.client_factory import get_communication_client
from app.config import settings
from app.db import get_db
from app.models import AuthUser
from app.services.auth_service import validate_session_token
from app.services.center_scope_service import get_current_center_id
from app.services.telegram_linking_service import process_link_update, resolve_bot_username

router = APIRouter(prefix="/api/telegram/link", tags=["Telegram Linking"])


class LinkStartRequest(BaseModel):
    ttl_seconds: int = Field(default=600, ge=60, le=3600)


def _require_auth(request: Request) -> dict:
    session = validate_session_token(request.cookies.get("auth_session"))
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return session


def _mask_chat_id(chat_id: str) -> str:
    clean = str(chat_id or "").strip()
    if len(clean) <= 4:
        return "****"
    return f"****{clean[-4:]}"


@router.get("/status")
def telegram_link_status(request: Request, auth: dict = Depends(_require_auth), db: Session = Depends(get_db)):
    user = db.query(AuthUser).filter(AuthUser.id == int(auth["user_id"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    chat_id = str(user.telegram_chat_id or "").strip()
    return {
        "linked": bool(chat_id),
        "chat_id_masked": _mask_chat_id(chat_id) if chat_id else "",
        "bot_username": resolve_bot_username(),
    }


@router.post("/start")
def telegram_link_start(
    payload: LinkStartRequest,
    auth: dict = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    user = db.query(AuthUser).filter(AuthUser.id == int(auth["user_id"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    bot_username = resolve_bot_username()
    if not bot_username:
        raise HTTPException(
            status_code=400,
            detail="Telegram bot username is not configured and could not be auto-resolved from bot token.",
        )
    client = get_communication_client()
    try:
        result = client.create_telegram_link_token(
            tenant_id=settings.communication_tenant_id,
            user_id=str(user.id),
            phone=str(user.phone),
            bot_username=bot_username,
            ttl_seconds=int(payload.ttl_seconds or 600),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not start Telegram link flow: {exc}") from exc
    deep_link = str(result.get("deep_link") or "").strip()
    if not deep_link:
        raise HTTPException(status_code=502, detail="Could not generate Telegram deep link")
    return {
        "ok": True,
        "deep_link": deep_link,
        "expires_at": result.get("expires_at"),
        "bot_username": bot_username,
    }


@router.post("/webhook")
async def telegram_link_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected_secret = str(settings.telegram_webhook_secret or "").strip()
    if expected_secret and expected_secret != str(x_telegram_bot_api_secret_token or "").strip():
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        body = await request.json()
    except Exception:
        body = {}
    update = body.get("update") if isinstance(body, dict) and isinstance(body.get("update"), dict) else body
    return process_link_update(db, update, center_id=int(get_current_center_id() or 0))
