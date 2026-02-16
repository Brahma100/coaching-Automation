from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.cache import cache
from app.core.attendance_guards import (
    available_batches_for_date as _core_available_batches_for_date,
    extract_session_token as _core_extract_session_token,
    require_teacher_or_admin as _core_require_teacher_or_admin,
)
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.domain.services.attendance_service import submit_attendance as domain_submit_attendance
from app.models import Batch, BatchSchedule, CalendarOverride, Role
from app.schemas import AttendanceItem
from app.services.action_token_service import consume_token, verify_token
from app.services.attendance_session_service import (
    load_attendance_session_sheet,
    resolve_web_attendance_session,
)
from app.services.auth_service import validate_session_token
from app.services.operational_brain_service import clear_operational_brain_cache
from app.services.rate_limit_service import SafeRateLimitError, check_rate_limit


router = APIRouter(prefix='/api/attendance', tags=['Attendance Session API'])


class AttendanceManageOpenRequest(BaseModel):
    batch_id: int
    schedule_id: int | None = None
    attendance_date: date


class AttendanceSessionSubmitRequest(BaseModel):
    token: str | None = None
    records: list[AttendanceItem] = Field(default_factory=list)


def _extract_session_token(request: Request) -> str | None:
    # DEPRECATED: use app.core.attendance_guards.extract_session_token directly.
    return _core_extract_session_token(request)


def _require_teacher_or_admin(request: Request) -> dict:
    # DEPRECATED: use app.core.attendance_guards.require_teacher_or_admin directly.
    return _core_require_teacher_or_admin(request, strict=True)


def _available_batches_for_date(db: Session, target_date: date) -> list[Batch]:
    # DEPRECATED: use app.core.attendance_guards.available_batches_for_date directly.
    return _core_available_batches_for_date(db, target_date)


@router.get('/manage/options')
def attendance_manage_options(
    request: Request,
    batch_id: int | None = Query(default=None),
    attendance_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _require_teacher_or_admin(request)
    target_date = attendance_date or default_time_provider.today()
    target_weekday = int(target_date.weekday())
    batches = _available_batches_for_date(db, target_date)
    selected_batch_id = (
        batch_id
        if batch_id and any(int(row.id) == int(batch_id) for row in batches)
        else (batches[0].id if batches else None)
    )
    schedules = []
    if selected_batch_id:
        schedules = (
            db.query(BatchSchedule)
            .filter(
                BatchSchedule.batch_id == selected_batch_id,
                BatchSchedule.weekday == target_weekday,
            )
            .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
            .all()
        )

        override = (
            db.query(CalendarOverride)
            .filter(
                CalendarOverride.batch_id == selected_batch_id,
                CalendarOverride.override_date == target_date,
            )
            .order_by(CalendarOverride.id.desc())
            .first()
        )
        if override:
            if override.cancelled:
                schedules = []
            elif override.new_start_time:
                base_duration = int(schedules[0].duration_minutes) if schedules else 60
                duration = int(override.new_duration_minutes or base_duration)
                schedules = [
                    BatchSchedule(
                        id=-int(override.id),
                        batch_id=int(selected_batch_id),
                        weekday=target_weekday,
                        start_time=override.new_start_time,
                        duration_minutes=duration,
                    )
                ]
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
        'attendance_date': target_date.isoformat(),
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
    actor_user_id = 0
    auth_user = None
    session_token = _extract_session_token(request)
    if session_token:
        auth_user = validate_session_token(session_token)
    request_role = (auth_user or {}).get('role')
    request_center_id = int((auth_user or {}).get('center_id') or 0)
    if token:
        payload = None
        for candidate in ('attendance_open', 'attendance_review', 'attendance-session'):
            try:
                payload = verify_token(
                    db,
                    token,
                    expected_action_type=candidate,
                    request_role=request_role,
                    request_center_id=request_center_id,
                    request_ip=(request.client.host if request.client else ''),
                    request_user_agent=request.headers.get('user-agent', ''),
                )
                token_type = candidate
                break
            except ValueError:
                continue
        if not payload:
            raise HTTPException(status_code=400, detail='Invalid token')
        if int(payload.get('session_id') or 0) != session_id:
            raise HTTPException(status_code=403, detail='Token does not match session')
        role = Role.TEACHER.value
        actor_user_id = int(payload.get('teacher_id') or 0)
    else:
        auth_user = _require_teacher_or_admin(request)
        role = (auth_user.get('role') or '').lower()
        actor_user_id = int(auth_user.get('user_id') or 0)

    sheet = load_attendance_session_sheet(
        db,
        session_id,
        actor_role=role,
        actor_user_id=actor_user_id,
    )
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
    auth_user = None
    session_token = _extract_session_token(request)
    if session_token:
        auth_user = validate_session_token(session_token)
    request_role = (auth_user or {}).get('role')
    request_center_id = int((auth_user or {}).get('center_id') or 0)
    if payload.token:
        token_payload = None
        token_type = None
        for candidate in ('attendance_open', 'attendance_review', 'attendance-session'):
            try:
                token_payload = verify_token(
                    db,
                    payload.token,
                    expected_action_type=candidate,
                    request_role=request_role,
                    request_center_id=request_center_id,
                    request_ip=(request.client.host if request.client else ''),
                    request_user_agent=request.headers.get('user-agent', ''),
                )
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

    effective_center_id = int((auth_user or {}).get('center_id') or request_center_id or 0) or 1
    try:
        check_rate_limit(
            db,
            center_id=effective_center_id,
            scope_type='user',
            scope_key=str(teacher_id or 0),
            action_name='attendance_submit_session',
            max_requests=10,
            window_seconds=60,
        )
    except SafeRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    try:
        result = domain_submit_attendance(
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
    if payload.token:
        consume_token(db, payload.token)
    cache.invalidate_prefix('today_view')
    cache.invalidate_prefix('inbox')
    cache.invalidate_prefix('admin_ops')
    cache.invalidate_prefix('student_dashboard')
    clear_operational_brain_cache()
    return result
