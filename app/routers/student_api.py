from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.cache import cache, cache_key, cached_view
from app.db import get_db
from app.models import Student
from app.services import snapshot_service
from app.services.student_portal_service import (
    get_student_dashboard,
    list_student_attendance,
    list_student_fees,
    list_student_homework,
    require_student_session,
)


router = APIRouter(prefix='/api/student', tags=['Student API'])


class StudentPreferencesUpdate(BaseModel):
    enable_daily_digest: bool
    enable_homework_reminders: bool
    enable_motivation_messages: bool


def _resolve_token(request: Request) -> str | None:
    token = request.cookies.get('auth_session')
    if token:
        return token

    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        return authorization[7:].strip()
    return None


def _require_student(request: Request, db: Session = Depends(get_db)) -> dict:
    # Read-only by design: student-only guard for all /api/student endpoints.
    token = _resolve_token(request)
    try:
        return require_student_session(db, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc) or 'Forbidden') from exc


@router.get('/me')
def student_me(
    auth: dict = Depends(_require_student),
):
    student = auth['student']
    session = auth['session']
    return {
        'phone': session.get('phone'),
        'role': session.get('role'),
        'student': {
            'id': student.id,
            'name': student.name,
            'batch_id': student.batch_id,
            'enable_daily_digest': student.enable_daily_digest,
            'enable_homework_reminders': student.enable_homework_reminders,
            'enable_motivation_messages': student.enable_motivation_messages,
        },
    }


@router.get('/preferences')
def student_preferences(auth: dict = Depends(_require_student)):
    student = auth['student']
    return {
        'enable_daily_digest': student.enable_daily_digest,
        'enable_homework_reminders': student.enable_homework_reminders,
        'enable_motivation_messages': student.enable_motivation_messages,
    }


@router.put('/preferences')
def update_student_preferences(
    payload: StudentPreferencesUpdate,
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    student = auth['student']
    row = db.query(Student).filter(Student.id == student.id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Student not found')
    row.enable_daily_digest = payload.enable_daily_digest
    row.enable_homework_reminders = payload.enable_homework_reminders
    row.enable_motivation_messages = payload.enable_motivation_messages
    db.commit()
    db.refresh(row)
    cache.invalidate(cache_key('student_dashboard', row.id))
    return {
        'enable_daily_digest': row.enable_daily_digest,
        'enable_homework_reminders': row.enable_homework_reminders,
        'enable_motivation_messages': row.enable_motivation_messages,
    }


@router.get('/dashboard')
@cached_view(ttl=None, key_builder=lambda auth=None, **_: _student_dashboard_key(auth))
def student_dashboard_api(
    bypass_cache: bool = Query(default=False),
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    student = auth['student']
    today = datetime.utcnow().date()
    if not bypass_cache:
        snapshot = snapshot_service.get_student_dashboard_snapshot(db, student_id=student.id, day=today)
        if snapshot is not None:
            return snapshot
    payload = get_student_dashboard(db, student)
    try:
        snapshot_service.upsert_student_dashboard_snapshot(db, student_id=student.id, day=today, payload=payload)
    except Exception:
        pass
    return payload


def _student_dashboard_key(auth: dict | None) -> str:
    student = auth.get('student') if auth else None
    student_id = student.id if student else 0
    return cache_key('student_dashboard', student_id)


@router.get('/attendance')
def student_attendance_api(
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    return list_student_attendance(db, auth['student'])


@router.get('/homework')
def student_homework_api(
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    return list_student_homework(db, auth['student'])


@router.get('/fees')
def student_fees_api(
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    return list_student_fees(db, auth['student'])
