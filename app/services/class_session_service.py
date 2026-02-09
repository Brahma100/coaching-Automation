from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Batch, ClassSession


def _scheduled_datetime_for_batch(batch: Batch, target_date: date) -> datetime:
    hour, minute = 7, 0
    try:
        hh, mm = batch.start_time.split(':', 1)
        hour, minute = int(hh), int(mm)
    except Exception:
        pass
    return datetime.combine(target_date, time(hour=hour, minute=minute))


def create_class_session(
    db: Session,
    batch_id: int,
    subject: str,
    scheduled_start: datetime,
    teacher_id: int,
    topic_planned: str = '',
):
    row = ClassSession(
        batch_id=batch_id,
        subject=subject,
        scheduled_start=scheduled_start,
        topic_planned=topic_planned,
        teacher_id=teacher_id,
        status='scheduled',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: int):
    return db.query(ClassSession).filter(ClassSession.id == session_id).first()


def list_batch_sessions(db: Session, batch_id: int, limit: int = 30):
    return db.query(ClassSession).filter(ClassSession.batch_id == batch_id).order_by(ClassSession.scheduled_start.desc()).limit(limit).all()


def start_class_session(db: Session, session_id: int):
    row = get_session(db, session_id)
    if not row:
        raise ValueError('Class session not found')
    row.status = 'running'
    row.actual_start = row.actual_start or datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def complete_class_session(db: Session, session_id: int, topic_completed: str = ''):
    row = get_session(db, session_id)
    if not row:
        raise ValueError('Class session not found')
    row.status = 'completed'
    row.actual_start = row.actual_start or datetime.utcnow()
    if topic_completed:
        row.topic_completed = topic_completed
    db.commit()
    db.refresh(row)
    return row


def get_or_create_session_for_attendance(
    db: Session,
    batch_id: int,
    attendance_date: date,
    subject: str,
    teacher_id: int,
    scheduled_start: datetime | None,
    topic_planned: str,
    topic_completed: str,
):
    existing = db.query(ClassSession).filter(
        ClassSession.batch_id == batch_id,
        func.date(ClassSession.scheduled_start) == attendance_date,
    ).first()

    if existing:
        existing.subject = subject or existing.subject
        existing.teacher_id = teacher_id or existing.teacher_id
        existing.topic_planned = topic_planned or existing.topic_planned
        existing.topic_completed = topic_completed or existing.topic_completed
        existing.status = 'completed'
        existing.actual_start = existing.actual_start or datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise ValueError('Batch not found')

    row = ClassSession(
        batch_id=batch_id,
        subject=subject or 'General',
        scheduled_start=scheduled_start or _scheduled_datetime_for_batch(batch, attendance_date),
        actual_start=datetime.utcnow(),
        topic_planned=topic_planned,
        topic_completed=topic_completed,
        teacher_id=teacher_id,
        status='completed',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
