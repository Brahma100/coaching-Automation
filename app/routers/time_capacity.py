from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.services.auth_service import validate_session_token
from app.services.teacher_calendar_service import clear_teacher_calendar_cache
from app.services.time_capacity_service import (
    create_teacher_unavailability,
    delete_teacher_unavailability,
    get_batch_capacity,
    get_reschedule_options,
    get_teacher_availability,
    get_weekly_load,
)


router = APIRouter(prefix='/api/time', tags=['Time Capacity'])


class TimeBlockPayload(BaseModel):
    date: date
    start_time: time
    end_time: time
    reason: str = Field(default='', max_length=255)
    teacher_id: int | None = None


def _require_teacher_or_admin(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


def _resolve_teacher_id(session: dict, teacher_id: int | None) -> int:
    role = (session.get('role') or '').lower()
    session_teacher_id = int(session.get('user_id') or 0)
    if role == Role.ADMIN.value:
        return int(teacher_id or session_teacher_id)
    if teacher_id is not None and int(teacher_id) != session_teacher_id:
        raise HTTPException(status_code=403, detail='Admin role required to query another teacher')
    return session_teacher_id


@router.get('/availability')
def api_time_availability(
    request: Request,
    date_value: date = Query(..., alias='date'),
    teacher_id: int | None = Query(default=None),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    effective_teacher_id = int(teacher_id or 0) if role == Role.ADMIN.value else _resolve_teacher_id(session, teacher_id)
    payload = get_teacher_availability(
        db,
        effective_teacher_id,
        date_value,
        actor_user_id=int(session.get('user_id') or 0),
    )
    return {'data': payload}


@router.get('/batch-capacity')
def api_batch_capacity(
    request: Request,
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    payload = get_batch_capacity(
        db,
        actor_role=(session.get('role') or '').lower(),
        actor_user_id=int(session.get('user_id') or 0),
    )
    return {'data': payload}


@router.get('/reschedule-options')
def api_reschedule_options(
    request: Request,
    batch_id: int = Query(...),
    date_value: date = Query(..., alias='date'),
    teacher_id: int | None = Query(default=None),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    effective_teacher_id = int(teacher_id or 0) if role == Role.ADMIN.value else _resolve_teacher_id(session, teacher_id)
    try:
        payload = get_reschedule_options(
            db,
            teacher_id=effective_teacher_id,
            batch_id=batch_id,
            target_date=date_value,
            actor_user_id=int(session.get('user_id') or 0),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {'data': payload}


@router.get('/weekly-load')
def api_weekly_load(
    request: Request,
    week_start: date = Query(...),
    teacher_id: int | None = Query(default=None),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    effective_teacher_id = int(teacher_id or 0) if role == Role.ADMIN.value else _resolve_teacher_id(session, teacher_id)
    payload = get_weekly_load(
        db,
        effective_teacher_id,
        week_start,
        actor_user_id=int(session.get('user_id') or 0),
    )
    return {'data': payload}


@router.post('/block')
def api_create_block(
    payload: TimeBlockPayload,
    request: Request,
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    effective_teacher_id = _resolve_teacher_id(session, payload.teacher_id)
    try:
        row = create_teacher_unavailability(
            db,
            teacher_id=effective_teacher_id,
            target_date=payload.date,
            start_time_value=payload.start_time,
            end_time_value=payload.end_time,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clear_teacher_calendar_cache()
    return {
        'data': {
            'id': row.id,
            'teacher_id': row.teacher_id,
            'date': row.date.isoformat(),
            'start_time': row.start_time.strftime('%H:%M'),
            'end_time': row.end_time.strftime('%H:%M'),
            'reason': row.reason,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
    }


@router.delete('/block/{block_id}')
def api_delete_block(
    block_id: int,
    request: Request,
    teacher_id: int | None = Query(default=None),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    effective_teacher_id = _resolve_teacher_id(session, teacher_id)
    deleted = delete_teacher_unavailability(
        db,
        teacher_id=effective_teacher_id,
        block_id=block_id,
        admin=(role == Role.ADMIN.value),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail='Blocked slot not found')
    clear_teacher_calendar_cache()
    return {'data': {'ok': True, 'id': block_id}}
