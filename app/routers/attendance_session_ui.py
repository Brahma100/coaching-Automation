from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.schemas import AttendanceItem
from app.services.action_token_service import verify_and_consume_token, verify_token
from app.services.attendance_session_service import load_attendance_session_sheet, submit_attendance_for_session
from app.services.auth_service import validate_session_token


logger = logging.getLogger(__name__)
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


def _authorize(
    db: Session,
    request: Request,
    session_id: int,
    token: str | None,
    consume_token: bool,
) -> dict:
    if token:
        try:
            payload = (
                verify_and_consume_token(db, token, expected_action_type='attendance-session')
                if consume_token
                else verify_token(db, token, expected_action_type='attendance-session')
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        token_session_id = int(payload.get('session_id') or 0)
        if token_session_id != session_id:
            raise HTTPException(status_code=403, detail='Token does not match session')
        return {
            'role': Role.TEACHER.value,
            'teacher_id': int(payload.get('teacher_id') or 0),
            'token_used': True,
        }

    session_token = _extract_session_token(request)
    auth_user = validate_session_token(session_token)
    if not auth_user:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (auth_user.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return {
        'role': role,
        'teacher_id': int(auth_user.get('user_id') or 0),
        'token_used': False,
    }


@router.get('/session/{session_id}')
def attendance_session_page(
    session_id: int,
    request: Request,
    token: str | None = Query(default=None),
    saved: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    access = _authorize(db, request, session_id, token=token, consume_token=False)
    sheet = load_attendance_session_sheet(db, session_id)
    can_edit = (not sheet['locked']) or access['role'] == Role.ADMIN.value
    return templates.TemplateResponse(
        'attendance_session.html',
        {
            'request': request,
            'sheet': sheet,
            'rows': sheet['rows'],
            'session_row': sheet['session'],
            'attendance_date': sheet['attendance_date'],
            'can_edit': can_edit,
            'saved': saved,
            'error': error,
            'token': token or '',
            'token_used': access['token_used'],
        },
    )


@router.post('/session/{session_id}')
def attendance_session_submit(
    session_id: int,
    request: Request,
    token: str = Form(default=''),
    student_id: list[int] | None = Form(default=None),
    status: list[str] | None = Form(default=None),
    comment: list[str] | None = Form(default=None),
    db: Session = Depends(get_db),
):
    token_value = token.strip() or None
    access = _authorize(db, request, session_id, token=token_value, consume_token=bool(token_value))

    student_ids = student_id or []
    statuses = status or []
    comments = comment or []
    if not student_ids:
        if token_value:
            raise HTTPException(status_code=400, detail='No students found for this session')
        return RedirectResponse(url=f'/ui/attendance/session/{session_id}?error=no-students', status_code=303)
    if len(statuses) != len(student_ids):
        if token_value:
            raise HTTPException(status_code=400, detail='Invalid attendance payload')
        return RedirectResponse(url=f'/ui/attendance/session/{session_id}?error=invalid-payload', status_code=303)
    if len(comments) < len(student_ids):
        comments = comments + ([''] * (len(student_ids) - len(comments)))

    try:
        records = [AttendanceItem(student_id=sid, status=st, comment=cm).model_dump() for sid, st, cm in zip(student_ids, statuses, comments)]
        submit_attendance_for_session(
            db=db,
            session_id=session_id,
            records=records,
            actor_role=access['role'],
            teacher_id=access['teacher_id'],
        )
    except PermissionError as exc:
        if token_value:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return RedirectResponse(url=f'/ui/attendance/session/{session_id}?error=session-locked', status_code=303)
    except ValueError as exc:
        if token_value:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        msg = str(exc)
        if 'Attendance window closed' in msg:
            return RedirectResponse(url=f'/ui/attendance/session/{session_id}?error=session-closed', status_code=303)
        return RedirectResponse(url=f'/ui/attendance/session/{session_id}?error=submit-failed', status_code=303)
    except Exception as exc:
        logger.exception('attendance_session_submit_failed', extra={'session_id': session_id, 'records_count': len(student_ids)})
        if token_value:
            raise HTTPException(status_code=500, detail='Failed to submit attendance') from exc
        return RedirectResponse(url=f'/ui/attendance/session/{session_id}?error=submit-failed', status_code=303)

    if token_value:
        sheet = load_attendance_session_sheet(db, session_id)
        return templates.TemplateResponse(
            'attendance_session.html',
            {
                'request': request,
                'sheet': sheet,
                'rows': sheet['rows'],
                'session_row': sheet['session'],
                'attendance_date': sheet['attendance_date'],
                'can_edit': False,
                'saved': '1',
                'error': None,
                'token': '',
                'token_used': True,
            },
        )
    return RedirectResponse(url=f'/ui/attendance/session/{session_id}?saved=1', status_code=303)
