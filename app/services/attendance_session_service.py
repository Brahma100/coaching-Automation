from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.services.attendance_service import get_attendance_for_batch_today, submit_attendance
from app.services.class_session_resolver import is_session_locked, resolve_or_create_class_session
from app.services.class_session_service import get_session


def resolve_web_attendance_session(
    db: Session,
    batch_id: int,
    schedule_id: int | None,
    target_date,
    teacher_id: int = 0,
):
    return resolve_or_create_class_session(
        db=db,
        batch_id=batch_id,
        schedule_id=schedule_id,
        target_date=target_date,
        source='web',
        teacher_id=teacher_id,
    )


def load_attendance_session_sheet(db: Session, session_id: int) -> dict:
    session = get_session(db, session_id)
    if not session:
        raise ValueError('Class session not found')

    attendance_date = session.scheduled_start.date()
    rows = get_attendance_for_batch_today(db, session.batch_id, attendance_date)
    return {
        'session': session,
        'attendance_date': attendance_date,
        'rows': rows,
        'locked': is_session_locked(session),
    }


def submit_attendance_for_session(
    db: Session,
    session_id: int,
    records: list[dict],
    actor_role: str,
    teacher_id: int = 0,
) -> dict:
    session = get_session(db, session_id)
    if not session:
        raise ValueError('Class session not found')
    if session.status in ('closed', 'missed'):
        raise ValueError('Attendance window closed for this class.')
    if is_session_locked(session) and actor_role != 'admin':
        raise PermissionError('Session already submitted and locked')

    result = submit_attendance(
        db=db,
        batch_id=session.batch_id,
        attendance_date=session.scheduled_start.date(),
        records=records,
        subject=session.subject or 'General',
        teacher_id=session.teacher_id or teacher_id or 0,
        scheduled_start=session.scheduled_start,
        topic_planned=session.topic_planned or '',
        topic_completed=session.topic_completed or '',
        class_session_id=session_id,
    )
    refreshed = get_session(db, session_id)
    if refreshed:
        refreshed.status = 'submitted'
        refreshed.actual_start = refreshed.actual_start or datetime.utcnow()
        db.commit()
    return result
