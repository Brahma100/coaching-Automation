from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.router_guard import assert_center_match, assert_teacher_batch_scope, require_auth_user, require_role
from app.db import get_db
from app.models import Student
from app.services.comms_service import queue_notification
from app.services.integration_service import require_integration


router = APIRouter(prefix='/communications', tags=['Communications'])


@router.post('/notify/student/{student_id}')
def notify_student(student_id: int, message: str, request: Request, channel: str = 'telegram', db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {'ok': False, 'detail': 'Student not found'}
    assert_center_match(user, int(student.center_id or 0))
    assert_teacher_batch_scope(db, user, int(student.batch_id or 0))
    if str(channel or '').strip().lower() == 'telegram':
        integration_gate = require_integration(db, 'telegram', center_id=student.center_id)
        if integration_gate.get('integration_required'):
            return {
                'ok': False,
                'integration_required': True,
                'provider': 'telegram',
                'message': integration_gate.get('message') or 'Connect Telegram to enable notifications',
            }
    queue_notification(db, student, channel, message)
    return {'ok': True, 'student_id': student_id, 'channel': channel}


@router.post('/reminders/{student_id}/approve')
def approve_reminder(student_id: int, message: str, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {'ok': False, 'detail': 'Student not found'}
    assert_center_match(user, int(student.center_id or 0))
    assert_teacher_batch_scope(db, user, int(student.batch_id or 0))
    integration_gate = require_integration(db, 'telegram', center_id=student.center_id)
    if integration_gate.get('integration_required'):
        return {
            'ok': False,
            'integration_required': True,
            'provider': 'telegram',
            'message': integration_gate.get('message') or 'Connect Telegram to enable notifications',
        }
    queue_notification(db, student, 'telegram', f"Approved reminder: {message}")
    return {'ok': True, 'action': 'approved'}


@router.post('/reminders/{student_id}/resend')
def resend_reminder(student_id: int, message: str, request: Request, db: Session = Depends(get_db)):
    user = require_auth_user(request)
    require_role(user, {'admin', 'teacher'})
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {'ok': False, 'detail': 'Student not found'}
    assert_center_match(user, int(student.center_id or 0))
    assert_teacher_batch_scope(db, user, int(student.batch_id or 0))
    integration_gate = require_integration(db, 'telegram', center_id=student.center_id)
    if integration_gate.get('integration_required'):
        return {
            'ok': False,
            'integration_required': True,
            'provider': 'telegram',
            'message': integration_gate.get('message') or 'Connect Telegram to enable notifications',
        }
    queue_notification(db, student, 'telegram', f"Re-sent reminder: {message}")
    return {'ok': True, 'action': 'resent'}
