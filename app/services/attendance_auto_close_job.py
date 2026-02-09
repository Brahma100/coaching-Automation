from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AttendanceRecord, AuthUser, ClassSession
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.comms_service import send_telegram_message
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.services.pending_action_service import create_pending_action
from app.services.post_class_pipeline import run_post_class_pipeline


logger = logging.getLogger(__name__)


def _session_end_with_grace(session: ClassSession, grace_minutes: int) -> datetime:
    return session.scheduled_start + timedelta(minutes=(session.duration_minutes or 60) + grace_minutes)


def _attendance_records_for_session(db: Session, session: ClassSession) -> list[AttendanceRecord]:
    attendance_date = session.scheduled_start.date()
    student_ids = list_active_student_ids_for_batch(db, session.batch_id)
    if not student_ids:
        return []
    return (
        db.query(AttendanceRecord)
        .filter(
            and_(
                AttendanceRecord.student_id.in_(student_ids),
                AttendanceRecord.attendance_date == attendance_date,
            )
        )
        .all()
    )


def _notify_teacher_missed_session(db: Session, session: ClassSession) -> None:
    if not session.teacher_id:
        return
    auth_user = db.query(AuthUser).filter(AuthUser.id == session.teacher_id).first()
    if not auth_user:
        return
    chat_id = resolve_teacher_chat_id(db, auth_user.phone)
    if not chat_id:
        return
    start_dt = session.scheduled_start
    end_dt = start_dt + timedelta(minutes=session.duration_minutes or 60)
    message = (
        f"Attendance not submitted for {session.subject} "
        f"({start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}). "
        'Session closed automatically.'
    )
    send_telegram_message(chat_id, message)


def auto_close_attendance_sessions(db: Session, grace_minutes: int | None = None) -> dict:
    grace = settings.attendance_auto_close_grace_minutes if grace_minutes is None else grace_minutes
    now = datetime.utcnow()
    candidates = (
        db.query(ClassSession)
        .filter(ClassSession.status.in_(['scheduled', 'open', 'submitted', 'running']))
        .order_by(ClassSession.scheduled_start.asc(), ClassSession.id.asc())
        .all()
    )

    closed_count = 0
    missed_count = 0
    inspected = 0

    for session in candidates:
        if now <= _session_end_with_grace(session, grace):
            continue
        inspected += 1
        records = _attendance_records_for_session(db, session)
        has_attendance = len(records) > 0

        if has_attendance and session.status in ('scheduled', 'open', 'running'):
            try:
                run_post_class_pipeline(
                    db=db,
                    batch_id=session.batch_id,
                    attendance_date=session.scheduled_start.date(),
                    records=records,
                    subject=session.subject or 'General',
                    teacher_id=session.teacher_id or 0,
                    scheduled_start=session.scheduled_start,
                    topic_planned=session.topic_planned or '',
                    topic_completed=session.topic_completed or '',
                )
            except Exception:
                logger.exception('auto_close_pipeline_failed session_id=%s', session.id)

        if has_attendance:
            session.status = 'closed'
            session.closed_at = now
            closed_count += 1
        else:
            session.status = 'missed'
            session.closed_at = now
            create_pending_action(
                db=db,
                action_type='manual',
                student_id=None,
                related_session_id=session.id,
                note=f'Attendance missed for session {session.id} ({session.scheduled_start.date()})',
            )
            _notify_teacher_missed_session(db, session)
            missed_count += 1

        db.commit()

    return {
        'inspected': inspected,
        'closed': closed_count,
        'missed': missed_count,
        'grace_minutes': grace,
    }
