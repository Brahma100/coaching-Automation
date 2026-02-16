from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import settings
from app.models import AuthUser, Role
from app.services.auth_service import validate_session_token

router = APIRouter(prefix='/api/teacher/profile', tags=['Teacher Profile'])


class TeacherProfileUpdate(BaseModel):
    notification_delete_minutes: int | None = Field(default=None, ge=1, le=240)
    enable_auto_delete_notes_on_expiry: bool | None = None
    ui_toast_duration_seconds: int | None = Field(default=None, ge=1, le=30)
    daily_work_start_time: time | None = None
    daily_work_end_time: time | None = None
    max_daily_hours: int | None = Field(default=None, ge=1, le=24)
    timezone: str | None = Field(default=None, min_length=2, max_length=60)


def _require_teacher(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.get('')
def get_profile(request: Request, _: dict = Depends(_require_teacher), db: Session = Depends(get_db)):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    auth_user = db.query(AuthUser).filter(AuthUser.id == session['user_id']).first()
    if not auth_user:
        raise HTTPException(status_code=404, detail='User not found')
    return {
        'id': auth_user.id,
        'phone': auth_user.phone,
        'role': auth_user.role,
        'telegram_linked': bool((auth_user.telegram_chat_id or '').strip()),
        'telegram_chat_id_masked': (
            f"****{str(auth_user.telegram_chat_id).strip()[-4:]}"
            if (auth_user.telegram_chat_id or '').strip()
            else ''
        ),
        'telegram_bot_username': str(settings.telegram_bot_username or '').strip().lstrip('@'),
        'notification_delete_minutes': auth_user.notification_delete_minutes or 15,
        'enable_auto_delete_notes_on_expiry': bool(auth_user.enable_auto_delete_notes_on_expiry),
        'ui_toast_duration_seconds': int(auth_user.ui_toast_duration_seconds or 5),
        'daily_work_start_time': auth_user.daily_work_start_time.strftime('%H:%M') if auth_user.daily_work_start_time else '07:00',
        'daily_work_end_time': auth_user.daily_work_end_time.strftime('%H:%M') if auth_user.daily_work_end_time else '20:00',
        'max_daily_hours': auth_user.max_daily_hours,
        'timezone': auth_user.timezone or auth_user.time_zone or 'Asia/Kolkata',
    }


@router.put('')
def update_profile(
    payload: TeacherProfileUpdate,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    auth_user = db.query(AuthUser).filter(AuthUser.id == session['user_id']).first()
    if not auth_user:
        raise HTTPException(status_code=404, detail='User not found')
    if payload.notification_delete_minutes is not None:
        auth_user.notification_delete_minutes = payload.notification_delete_minutes
    if payload.enable_auto_delete_notes_on_expiry is not None:
        auth_user.enable_auto_delete_notes_on_expiry = payload.enable_auto_delete_notes_on_expiry
    if payload.ui_toast_duration_seconds is not None:
        auth_user.ui_toast_duration_seconds = payload.ui_toast_duration_seconds
    if payload.daily_work_start_time is not None:
        auth_user.daily_work_start_time = payload.daily_work_start_time
    if payload.daily_work_end_time is not None:
        auth_user.daily_work_end_time = payload.daily_work_end_time
    if payload.max_daily_hours is not None:
        auth_user.max_daily_hours = payload.max_daily_hours
    if payload.timezone is not None:
        auth_user.timezone = payload.timezone.strip()
    db.commit()
    db.refresh(auth_user)
    return {
        'id': auth_user.id,
        'telegram_linked': bool((auth_user.telegram_chat_id or '').strip()),
        'telegram_chat_id_masked': (
            f"****{str(auth_user.telegram_chat_id).strip()[-4:]}"
            if (auth_user.telegram_chat_id or '').strip()
            else ''
        ),
        'telegram_bot_username': str(settings.telegram_bot_username or '').strip().lstrip('@'),
        'notification_delete_minutes': auth_user.notification_delete_minutes,
        'enable_auto_delete_notes_on_expiry': bool(auth_user.enable_auto_delete_notes_on_expiry),
        'ui_toast_duration_seconds': int(auth_user.ui_toast_duration_seconds or 5),
        'daily_work_start_time': auth_user.daily_work_start_time.strftime('%H:%M') if auth_user.daily_work_start_time else '07:00',
        'daily_work_end_time': auth_user.daily_work_end_time.strftime('%H:%M') if auth_user.daily_work_end_time else '20:00',
        'max_daily_hours': auth_user.max_daily_hours,
        'timezone': auth_user.timezone or auth_user.time_zone or 'Asia/Kolkata',
    }
