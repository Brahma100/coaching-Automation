from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.student_portal_service import (
    get_student_dashboard,
    list_student_attendance,
    list_student_fees,
    list_student_homework,
    require_student_session,
)


router = APIRouter(prefix='/api/student', tags=['Student API'])


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
        },
    }


@router.get('/dashboard')
def student_dashboard_api(
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    return get_student_dashboard(db, auth['student'])


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
