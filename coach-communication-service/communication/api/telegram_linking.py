from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from communication.api.auth import require_admin_role
from communication.linking import consume_link_update, create_link_session

router = APIRouter(prefix="/telegram", tags=["telegram-linking"])


class LinkSessionRequest(BaseModel):
    tenant_id: str = "default"
    user_id: str
    phone: str
    bot_username: str
    ttl_seconds: int = Field(default=600, ge=60, le=3600)


class ConsumeLinkUpdateRequest(BaseModel):
    update: dict[str, Any]
    expected_tenant_id: str | None = None


@router.post("/link-token", dependencies=[Depends(require_admin_role)])
async def issue_link_session(payload: LinkSessionRequest):
    return create_link_session(
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        phone=payload.phone,
        bot_username=payload.bot_username,
        ttl_seconds=payload.ttl_seconds,
    )


@router.post("/consume-link-update")
async def consume_telegram_update(payload: ConsumeLinkUpdateRequest):
    return consume_link_update(payload.update, expected_tenant_id=payload.expected_tenant_id)
