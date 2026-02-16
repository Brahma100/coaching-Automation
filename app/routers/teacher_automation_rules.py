from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Role
from app.services.auth_service import validate_session_token
from app.services.teacher_automation_rules_service import get_rules, update_rules


router = APIRouter(prefix='/api/teacher/automation-rules', tags=['Teacher Automation Rules'])


def _require_teacher(request: Request) -> dict:
    token = request.cookies.get('auth_session')
    session = validate_session_token(token)
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    role = (session.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        raise HTTPException(status_code=403, detail='Unauthorized')
    return session


class TeacherAutomationRulesUpdate(BaseModel):
    notify_on_attendance: bool = True
    class_start_reminder: bool = True
    fee_due_alerts: bool = True
    student_absence_escalation: bool = True
    homework_reminders: bool = True


@router.get('')
def get_teacher_automation_rules(
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    return get_rules(db, int(session['user_id']))


@router.put('')
def put_teacher_automation_rules(
    payload: TeacherAutomationRulesUpdate,
    request: Request,
    _: dict = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    session = validate_session_token(request.cookies.get('auth_session'))
    if not session:
        raise HTTPException(status_code=403, detail='Unauthorized')
    return update_rules(
        db,
        int(session['user_id']),
        notify_on_attendance=payload.notify_on_attendance,
        class_start_reminder=payload.class_start_reminder,
        fee_due_alerts=payload.fee_due_alerts,
        student_absence_escalation=payload.student_absence_escalation,
        homework_reminders=payload.homework_reminders,
    )

