from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import settings
from app.models import Role
from app.services.auth_service import validate_session_token
from app.services.teacher_communication_settings_service import (
    DEFAULT_ENABLED_EVENTS,
    get_or_create_teacher_communication_settings,
    provider_health,
    send_test_message,
    serialize_teacher_communication_settings,
    update_teacher_communication_settings,
)


router = APIRouter(prefix="/api/teacher/communication-settings", tags=["Teacher Communication Settings"])


def _require_teacher(request: Request) -> dict:
    token = request.cookies.get("auth_session")
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    role = (session.get("role") or "").lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail="Unauthorized")
    return session


class TeacherCommunicationSettingsUpdate(BaseModel):
    provider: str = Field(default="telegram")
    provider_config_json: dict = Field(default_factory=dict)
    enabled_events: list[str] = Field(default_factory=lambda: list(DEFAULT_ENABLED_EVENTS))
    quiet_hours: dict = Field(default_factory=lambda: {"start": "22:00", "end": "06:00"})
    delete_timer_minutes: int = Field(default=15, ge=1, le=240)


class TestMessagePayload(BaseModel):
    message: str = Field(default="Test message from Communication settings")


@router.get("")
def get_communication_settings(
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get("auth_session"))
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    row = get_or_create_teacher_communication_settings(db, int(session["user_id"]))
    data = serialize_teacher_communication_settings(row)
    data["available_providers"] = ["telegram", "whatsapp"]
    data["available_events"] = list(DEFAULT_ENABLED_EVENTS)
    mode = (settings.communication_mode or 'embedded').strip().lower()
    data["communication_mode"] = mode
    data["communication_service_url"] = settings.communication_service_url
    data["external_dashboard_url"] = settings.communication_service_url if mode == 'remote' else ''
    return data


@router.put("")
def put_communication_settings(
    payload: TeacherCommunicationSettingsUpdate,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get("auth_session"))
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    row = update_teacher_communication_settings(
        db,
        int(session["user_id"]),
        provider=payload.provider,
        provider_config_json=payload.provider_config_json,
        enabled_events=payload.enabled_events,
        quiet_hours=payload.quiet_hours,
        delete_timer_minutes=payload.delete_timer_minutes,
    )
    data = serialize_teacher_communication_settings(row)
    data["available_providers"] = ["telegram", "whatsapp"]
    data["available_events"] = list(DEFAULT_ENABLED_EVENTS)
    mode = (settings.communication_mode or 'embedded').strip().lower()
    data["communication_mode"] = mode
    data["communication_service_url"] = settings.communication_service_url
    data["external_dashboard_url"] = settings.communication_service_url if mode == 'remote' else ''
    return data


@router.get("/health")
def get_connection_health(
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get("auth_session"))
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    row = get_or_create_teacher_communication_settings(db, int(session["user_id"]))
    serialized = serialize_teacher_communication_settings(row)
    return serialized["connection_status"]


@router.post("/test-message")
def post_test_message(
    payload: TestMessagePayload,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get("auth_session"))
    if not session:
        raise HTTPException(status_code=403, detail="Unauthorized")
    row = get_or_create_teacher_communication_settings(db, int(session["user_id"]))
    serialized = serialize_teacher_communication_settings(row)
    result = send_test_message(
        serialized["provider"],
        serialized["provider_config_json"],
        payload.message,
    )
    health = provider_health(serialized["provider"], serialized["provider_config_json"])
    return {"result": result, "connection_status": health}
