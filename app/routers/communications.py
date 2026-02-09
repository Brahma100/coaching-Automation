from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Student
from app.services.comms_service import queue_notification


router = APIRouter(prefix='/communications', tags=['Communications'])


@router.post('/notify/student/{student_id}')
def notify_student(student_id: int, message: str, channel: str = 'telegram', db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    queue_notification(db, student, channel, message)
    return {'ok': True, 'student_id': student_id, 'channel': channel}


@router.post('/reminders/{student_id}/approve')
def approve_reminder(student_id: int, message: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    queue_notification(db, student, 'telegram', f"Approved reminder: {message}")
    return {'ok': True, 'action': 'approved'}


@router.post('/reminders/{student_id}/resend')
def resend_reminder(student_id: int, message: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    queue_notification(db, student, 'telegram', f"Re-sent reminder: {message}")
    return {'ok': True, 'action': 'resent'}
