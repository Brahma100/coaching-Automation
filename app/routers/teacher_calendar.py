from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CalendarOverride, Role
from app.services.auth_service import validate_session_token
from app.services.teacher_calendar_service import (
    clear_teacher_calendar_cache,
    get_calendar_session_detail,
    get_calendar_holidays,
    get_teacher_calendar,
    get_teacher_calendar_analytics,
    sync_calendar_holidays,
    validate_calendar_conflicts,
)


router = APIRouter(prefix='/api/calendar', tags=['Teacher Calendar'])


class CalendarOverridePayload(BaseModel):
    batch_id: int
    override_date: date
    new_start_time: str | None = None
    new_duration_minutes: int | None = Field(default=None, ge=1, le=300)
    cancelled: bool = False
    reason: str = ''


class ScheduleConflictPayload(BaseModel):
    teacher_id: int
    date: date
    start_time: str
    duration_minutes: int = Field(ge=1, le=300)
    room_id: int | None = None


def _require_teacher_or_admin(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


@router.get('')
def list_calendar(
    request: Request,
    start: date = Query(...),
    end: date = Query(...),
    view: str = Query(default='week'),
    teacher_id: int | None = Query(default=None),
    bypass_cache: bool = Query(default=False),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    effective_teacher_id = int(session.get('user_id') or 0)

    if role == Role.ADMIN.value:
        effective_teacher_id = int(teacher_id or 0)
    elif teacher_id is not None and int(teacher_id) != effective_teacher_id:
        raise HTTPException(status_code=403, detail='Admin role required to query other teacher calendars')

    try:
        payload = get_teacher_calendar(
            db,
            teacher_id=effective_teacher_id,
            start_date=start,
            end_date=end,
            view=view,
            actor_role=role,
            actor_user_id=int(session.get('user_id') or 0),
            bypass_cache=bypass_cache,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        'start': start.isoformat(),
        'end': end.isoformat(),
        'view': view,
        'teacher_id': effective_teacher_id,
        **payload,
    }


@router.post('/override')
def create_override(
    payload: CalendarOverridePayload,
    request: Request,
    _: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    row = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.batch_id == payload.batch_id,
            CalendarOverride.override_date == payload.override_date,
        )
        .order_by(CalendarOverride.id.desc())
        .first()
    )
    if row:
        row.new_start_time = payload.new_start_time
        row.new_duration_minutes = payload.new_duration_minutes
        row.cancelled = payload.cancelled
        row.reason = (payload.reason or '').strip()
        row.institute_id = row.institute_id or 0
    else:
        row = CalendarOverride(
            institute_id=0,
            batch_id=payload.batch_id,
            override_date=payload.override_date,
            new_start_time=payload.new_start_time,
            new_duration_minutes=payload.new_duration_minutes,
            cancelled=payload.cancelled,
            reason=(payload.reason or '').strip(),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    clear_teacher_calendar_cache()
    return {
        'id': row.id,
        'institute_id': row.institute_id,
        'batch_id': row.batch_id,
        'override_date': row.override_date.isoformat(),
        'new_start_time': row.new_start_time,
        'new_duration_minutes': row.new_duration_minutes,
        'cancelled': row.cancelled,
        'reason': row.reason,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


@router.put('/override/{override_id}')
def update_override(
    override_id: int,
    payload: CalendarOverridePayload,
    request: Request,
    _: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    row = db.query(CalendarOverride).filter(CalendarOverride.id == override_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Calendar override not found')

    row.batch_id = payload.batch_id
    row.institute_id = row.institute_id or 0
    row.override_date = payload.override_date
    row.new_start_time = payload.new_start_time
    row.new_duration_minutes = payload.new_duration_minutes
    row.cancelled = payload.cancelled
    row.reason = (payload.reason or '').strip()
    db.commit()
    db.refresh(row)
    clear_teacher_calendar_cache()
    return {
        'id': row.id,
        'institute_id': row.institute_id,
        'batch_id': row.batch_id,
        'override_date': row.override_date.isoformat(),
        'new_start_time': row.new_start_time,
        'new_duration_minutes': row.new_duration_minutes,
        'cancelled': row.cancelled,
        'reason': row.reason,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


@router.delete('/override/{override_id}')
def delete_override(
    override_id: int,
    request: Request,
    _: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    row = db.query(CalendarOverride).filter(CalendarOverride.id == override_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Calendar override not found')
    db.delete(row)
    db.commit()
    clear_teacher_calendar_cache()
    return {'ok': True}


@router.post('/conflicts/validate')
def validate_conflicts(
    payload: ScheduleConflictPayload,
    request: Request,
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    user_id = int(session.get('user_id') or 0)
    if role != Role.ADMIN.value and payload.teacher_id != user_id:
        raise HTTPException(status_code=403, detail='Cannot validate conflicts for another teacher')

    try:
        target_date = payload.date
        return validate_calendar_conflicts(
            db,
            teacher_id=payload.teacher_id,
            target_date=target_date,
            start_time=payload.start_time,
            duration_minutes=payload.duration_minutes,
            room_id=payload.room_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/session/{session_id}')
def get_calendar_session(
    session_id: int,
    request: Request,
    _: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    payload = get_calendar_session_detail(db, session_id)
    if not payload:
        raise HTTPException(status_code=404, detail='Class session not found')
    return payload


@router.get('/analytics')
def get_calendar_analytics(
    request: Request,
    start: date = Query(...),
    end: date = Query(...),
    teacher_id: int | None = Query(default=None),
    bypass_cache: bool = Query(default=False),
    session: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    role = (session.get('role') or '').lower()
    effective_teacher_id = int(session.get('user_id') or 0)

    if role == Role.ADMIN.value:
        effective_teacher_id = int(teacher_id or 0)
    elif teacher_id is not None and int(teacher_id) != effective_teacher_id:
        raise HTTPException(status_code=403, detail='Admin role required to query other teacher analytics')

    try:
        payload = get_teacher_calendar_analytics(
            db,
            teacher_id=effective_teacher_id,
            start_date=start,
            end_date=end,
            actor_role=role,
            actor_user_id=int(session.get('user_id') or 0),
            bypass_cache=bypass_cache,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        'teacher_id': effective_teacher_id,
        **payload,
    }


@router.post('/holidays/sync')
def sync_holidays(
    request: Request,
    start_year: int | None = Query(default=None, ge=2000, le=2100),
    years: int = Query(default=5, ge=1, le=10),
    country_code: str = Query(default='IN', min_length=2, max_length=2),
    _: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    try:
        payload = sync_calendar_holidays(
            db,
            country_code=country_code,
            start_year=start_year,
            years=years,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return payload


@router.get('/holidays')
def list_holidays(
    request: Request,
    start: date = Query(...),
    end: date = Query(...),
    country_code: str = Query(default='IN', min_length=2, max_length=2),
    _: dict = Depends(_require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(status_code=400, detail='end must be greater than or equal to start')
    payload = get_calendar_holidays(
        db,
        start_date=start,
        end_date=end,
        country_code=country_code,
    )
    return {
        'start': start.isoformat(),
        'end': end.isoformat(),
        'country_code': country_code.upper(),
        'holidays': payload,
    }
