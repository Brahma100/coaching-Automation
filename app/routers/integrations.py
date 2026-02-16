from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.services.auth_service import validate_session_token
from app.services.integration_service import list_integrations, upsert_integration


router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


def _require_auth(request: Request) -> dict:
    token = request.cookies.get("auth_session")
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    role = str(session.get("role") or "").strip().lower()
    if role not in (Role.ADMIN.value, Role.TEACHER.value):
        raise HTTPException(status_code=403, detail="Unauthorized")
    return session


class IntegrationConnectPayload(BaseModel):
    config_json: dict = Field(default_factory=dict)


@router.get("")
def get_integrations(
    request: Request,
    session: dict = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    center_id = int(session.get("center_id") or 0)
    if center_id <= 0:
        raise HTTPException(status_code=400, detail="Center not found in session")
    return {"rows": list_integrations(db, center_id=center_id)}


@router.post("/{provider}/connect")
def connect_integration(
    provider: str,
    payload: IntegrationConnectPayload,
    request: Request,
    session: dict = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    center_id = int(session.get("center_id") or 0)
    if center_id <= 0:
        raise HTTPException(status_code=400, detail="Center not found in session")
    row = upsert_integration(
        db,
        center_id=center_id,
        provider=provider,
        status="connected",
        config_json=payload.config_json,
    )
    return {
        "ok": True,
        "provider": row.provider,
        "status": row.status,
        "connected_at": row.connected_at.isoformat() if row.connected_at else None,
    }


@router.post("/{provider}/disconnect")
def disconnect_integration(
    provider: str,
    request: Request,
    session: dict = Depends(_require_auth),
    db: Session = Depends(get_db),
):
    center_id = int(session.get("center_id") or 0)
    if center_id <= 0:
        raise HTTPException(status_code=400, detail="Center not found in session")
    row = upsert_integration(
        db,
        center_id=center_id,
        provider=provider,
        status="disconnected",
        config_json={},
    )
    return {"ok": True, "provider": row.provider, "status": row.status}

