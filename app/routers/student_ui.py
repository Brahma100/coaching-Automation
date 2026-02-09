from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services.student_portal_service import (
    get_student_dashboard,
    list_student_attendance,
    list_student_fees,
    list_student_homework,
    require_student_session,
)


templates = Jinja2Templates(directory='app/ui/templates')
router = APIRouter(prefix='/ui/student', tags=['Student UI'])


def _require_student(request: Request, db: Session = Depends(get_db)) -> dict:
    # Read-only by design: every student UI page enforces student-only access.
    token = request.cookies.get('auth_session')
    try:
        return require_student_session(db, token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc) or 'Forbidden') from exc


@router.get('/dashboard')
def student_dashboard_page(
    request: Request,
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    data = get_student_dashboard(db, auth['student'])
    return templates.TemplateResponse(
        'student_dashboard.html',
        {
            'request': request,
            'student': auth['student'],
            'data': data,
        },
    )


@router.get('/attendance')
def student_attendance_page(
    request: Request,
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    rows = list_student_attendance(db, auth['student'])
    return templates.TemplateResponse(
        'student_attendance.html',
        {
            'request': request,
            'student': auth['student'],
            'rows': rows,
        },
    )


@router.get('/homework')
def student_homework_page(
    request: Request,
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    rows = list_student_homework(db, auth['student'])
    summary = {
        'assigned': len(rows),
        'submitted': sum(1 for row in rows if row['submission_status'] == 'Submitted'),
    }
    return templates.TemplateResponse(
        'student_homework.html',
        {
            'request': request,
            'student': auth['student'],
            'rows': rows,
            'summary': summary,
        },
    )


@router.get('/fees')
def student_fees_page(
    request: Request,
    auth: dict = Depends(_require_student),
    db: Session = Depends(get_db),
):
    rows = list_student_fees(db, auth['student'])
    return templates.TemplateResponse(
        'student_fees.html',
        {
            'request': request,
            'student': auth['student'],
            'rows': rows,
            'upi_id': settings.default_upi_id,
        },
    )


@router.get('/tests')
def student_tests_page(
    request: Request,
    auth: dict = Depends(_require_student),
):
    # Read-only by design: no write actions; list-only page (empty until test data exists).
    return templates.TemplateResponse(
        'student_tests.html',
        {
            'request': request,
            'student': auth['student'],
            'rows': [],
        },
    )


@router.get('/announcements')
def student_announcements_page(
    request: Request,
    auth: dict = Depends(_require_student),
):
    # Read-only by design: no write actions; list-only page (empty until announcement data exists).
    return templates.TemplateResponse(
        'student_announcements.html',
        {
            'request': request,
            'student': auth['student'],
            'rows': [],
        },
    )
