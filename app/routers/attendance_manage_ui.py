from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.attendance_guards import (
    available_batches_for_date as _core_available_batches_for_date,
    extract_session_token as _core_extract_session_token,
    require_teacher_or_admin as _core_require_teacher_or_admin,
)
from app.core.time_provider import default_time_provider
from app.db import get_db
from app.models import Batch, BatchSchedule, CalendarOverride, Role
from app.services.attendance_session_service import resolve_web_attendance_session


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(prefix='/ui/attendance', tags=['UI Attendance'])


def _extract_session_token(request: Request) -> str | None:
    # DEPRECATED: use app.core.attendance_guards.extract_session_token directly.
    return _core_extract_session_token(request)


def _require_teacher_or_admin(request: Request) -> dict:
    # DEPRECATED: use app.core.attendance_guards.require_teacher_or_admin directly.
    auth_user = getattr(request.state, 'auth_user', None)
    if auth_user:
        role = (auth_user.get('role') or '').lower()
        if role in (Role.TEACHER.value, Role.ADMIN.value):
            return auth_user
    return _core_require_teacher_or_admin(request, strict=False)


def _available_batches_for_date(db: Session, target_date: date) -> list[Batch]:
    # DEPRECATED: use app.core.attendance_guards.available_batches_for_date directly.
    return _core_available_batches_for_date(db, target_date)


@router.get('/manage')
def attendance_manage_page(
    request: Request,
    batch_id: int | None = Query(default=None),
    schedule_id: int | None = Query(default=None),
    attendance_date: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    auth_user = _require_teacher_or_admin(request)
    if not auth_user:
        return RedirectResponse(url='/ui/login', status_code=303)

    selected_date = attendance_date or default_time_provider.today().isoformat()
    try:
        target_date = date.fromisoformat(selected_date)
    except ValueError:
        target_date = default_time_provider.today()
        selected_date = target_date.isoformat()
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

    return templates.TemplateResponse(
        'attendance_manage.html',
        {
            'request': request,
            'batches': batches,
            'schedules': schedules,
            'selected_batch_id': selected_batch_id,
            'selected_schedule_id': schedule_id,
            'selected_date': selected_date,
            'error': error,
        },
    )


@router.post('/manage')
def attendance_manage_open(
    request: Request,
    batch_id: int = Form(...),
    schedule_id: int | None = Form(default=None),
    attendance_date: str = Form(...),
    db: Session = Depends(get_db),
):
    auth_user = _require_teacher_or_admin(request)
    if not auth_user:
        return RedirectResponse(url='/ui/login', status_code=303)

    try:
        target_date = date.fromisoformat(attendance_date)
    except ValueError:
        return RedirectResponse(url='/ui/attendance/manage?error=invalid-date', status_code=303)

    session, locked = resolve_web_attendance_session(
        db=db,
        batch_id=batch_id,
        schedule_id=schedule_id,
        target_date=target_date,
        teacher_id=int(auth_user.get('user_id') or 0),
    )
    if locked and auth_user.get('role') != Role.ADMIN.value:
        return RedirectResponse(url='/ui/attendance/manage?error=session-locked', status_code=303)

    return RedirectResponse(url=f'/ui/attendance/session/{session.id}', status_code=303)
