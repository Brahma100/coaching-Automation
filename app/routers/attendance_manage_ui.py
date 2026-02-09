from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Batch, BatchSchedule, Role
from app.services.attendance_session_service import resolve_web_attendance_session
from app.services.auth_service import validate_session_token


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(prefix='/ui/attendance', tags=['UI Attendance'])


def _extract_session_token(request: Request) -> str | None:
    cookie_token = request.cookies.get('auth_session')
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get('Authorization', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return None


def _require_teacher_or_admin(request: Request) -> dict:
    auth_user = getattr(request.state, 'auth_user', None)
    if not auth_user:
        auth_user = validate_session_token(_extract_session_token(request))
    if not auth_user:
        return {}
    role = (auth_user.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        return {}
    return auth_user


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

    selected_date = attendance_date or date.today().isoformat()
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
