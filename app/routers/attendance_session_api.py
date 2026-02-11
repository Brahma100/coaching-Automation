from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.cache import cache
from app.db import get_db
from app.models import Batch, BatchSchedule, Role
from app.schemas import AttendanceItem
from app.services.action_token_service import verify_and_consume_token, verify_token
from app.services.attendance_session_service import (
    load_attendance_session_sheet,
    resolve_web_attendance_session,
    submit_attendance_for_session,
)
from app.services.auth_service import validate_session_token


router = APIRouter(prefix='/api/attendance', tags=['Attendance Session API'])


class AttendanceManageOpenRequest(BaseModel):
    batch_id: int
    schedule_id: int | None = None
    attendance_date: date


class AttendanceSessionSubmitRequest(BaseModel):
    token: str | None = None
    records: list[AttendanceItem] = Field(default_factory=list)


def _extract_session_token(request: Request) -> str | None:
    cookie_token = request.cookies.get('auth_session')
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get('Authorization', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return None


def _require_teacher_or_admin(request: Request) -> dict:
    auth_user = validate_session_token(_extract_session_token(request))
    if not auth_user:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (auth_user.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return auth_user


@router.get('/manage/options')
def attendance_manage_options(
    request: Request,
    batch_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _require_teacher_or_admin(request)
    batches = db.query(Batch).filter(Batch.active.is_(True)).order_by(Batch.name.asc()).all()
    selected_batch_id = batch_id or (batches[0].id if batches else None)
    schedules = []
    if selected_batch_id:
        schedules = (
            db.query(BatchSchedule)
            .filter(BatchSchedule.batch_id == selected_batch_id)
            .order_by(BatchSchedule.weekday.asc(), BatchSchedule.start_time.asc())
            .all()
        )
    return {
        'batches': [
            {
                'id': row.id,
                'name': row.name,
                'subject': row.subject,
                'academic_level': row.academic_level,
            }
            for row in batches
        ],
        'selected_batch_id': selected_batch_id,
        'schedules': [
            {
                'id': row.id,
                'batch_id': row.batch_id,
                'weekday': row.weekday,
                'start_time': row.start_time,
                'duration_minutes': row.duration_minutes,
            }
            for row in schedules
        ],
    }


@router.post('/manage/open')
def attendance_manage_open_api(
    payload: AttendanceManageOpenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    auth_user = _require_teacher_or_admin(request)
    session, locked = resolve_web_attendance_session(
        db=db,
        batch_id=payload.batch_id,
        schedule_id=payload.schedule_id,
        target_date=payload.attendance_date,
        teacher_id=int(auth_user.get('user_id') or 0),
    )
    if locked and auth_user.get('role') != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail='Session already submitted and locked')
    return {'session_id': session.id, 'locked': locked}


@router.get('/session/{session_id}')
def attendance_session_get_api(
    session_id: int,
    request: Request,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    role = None
    token_type = None
    if token:
        payload = None
        for candidate in ('attendance_open', 'attendance_review', 'attendance-session'):
            try:
                payload = verify_token(db, token, expected_action_type=candidate)
                token_type = candidate
                break
            except ValueError:
                continue
        if not payload:
            raise HTTPException(status_code=400, detail='Invalid token')
        if int(payload.get('session_id') or 0) != session_id:
            raise HTTPException(status_code=403, detail='Token does not match session')
        role = Role.TEACHER.value
    else:
        auth_user = _require_teacher_or_admin(request)
        role = (auth_user.get('role') or '').lower()

    sheet = load_attendance_session_sheet(db, session_id)
    can_edit = (not sheet['locked']) or role == Role.ADMIN.value
    if token_type in ('attendance_open', 'attendance_review'):
        can_edit = sheet['session'].status not in ('closed', 'missed')
    return {
        'session': {
            'id': sheet['session'].id,
            'batch_id': sheet['session'].batch_id,
            'subject': sheet['session'].subject,
            'scheduled_start': sheet['session'].scheduled_start.isoformat(),
            'status': sheet['session'].status,
        },
        'attendance_date': sheet['attendance_date'].isoformat(),
        'rows': sheet['rows'],
        'locked': sheet['locked'],
        'can_edit': can_edit,
    }


@router.post('/session/{session_id}/submit')
def attendance_session_submit_api(
    session_id: int,
    payload: AttendanceSessionSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    role = Role.TEACHER.value
    teacher_id = 0
    allow_edit_submitted = False
    if payload.token:
        token_payload = None
        token_type = None
        for candidate in ('attendance_open', 'attendance_review', 'attendance-session'):
            try:
                token_payload = verify_token(db, payload.token, expected_action_type=candidate)
                token_type = candidate
                break
            except ValueError:
                continue
        if not token_payload:
            raise HTTPException(status_code=400, detail='Invalid token')
        if int(token_payload.get('session_id') or 0) != session_id:
            raise HTTPException(status_code=403, detail='Token does not match session')
        teacher_id = int(token_payload.get('teacher_id') or 0)
        if token_type in ('attendance_open', 'attendance_review'):
            allow_edit_submitted = True
    else:
        auth_user = _require_teacher_or_admin(request)
        role = (auth_user.get('role') or '').lower()
        teacher_id = int(auth_user.get('user_id') or 0)

    try:
        result = submit_attendance_for_session(
            db=db,
            session_id=session_id,
            records=[row.model_dump() for row in payload.records],
            actor_role=role,
            teacher_id=teacher_id,
            allow_edit_submitted=allow_edit_submitted,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cache.invalidate_prefix('today_view')
    cache.invalidate_prefix('inbox')
    cache.invalidate('admin_ops')
    cache.invalidate_prefix('student_dashboard')
    return result
