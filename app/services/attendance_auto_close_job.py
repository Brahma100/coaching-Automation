from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider
from app.domain.communication_gateway import send_event as gateway_send_event
from app.models import AttendanceRecord, AuthUser, ClassSession
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.services.pending_action_service import create_pending_action
from app.services.automation_failure_service import log_automation_failure
from app.services.post_class_pipeline import run_post_class_pipeline
from app.services.post_class_automation_engine import run_post_class_automation
from app.services import snapshot_service


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
    gateway_send_event(
        'attendance.session_missed',
        {
            'db': db,
            'tenant_id': settings.communication_tenant_id,
            'user_id': str(auth_user.id),
            'event_payload': {'session_id': int(session.id), 'teacher_id': int(auth_user.id)},
            'message': message,
            'channels': ['telegram'],
            'critical': True,
            'entity_type': 'class_session',
            'entity_id': int(session.id),
            'teacher_id': int(auth_user.id),
            'session_id': int(session.id),
            'notification_type': 'attendance_missed',
            'center_id': int(session.center_id or 1),
        },
        [{'chat_id': chat_id, 'user_id': str(auth_user.id)}],
    )


def auto_close_attendance_sessions(
    db: Session,
    grace_minutes: int | None = None,
    *,
    center_id: int,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    grace = settings.attendance_auto_close_grace_minutes if grace_minutes is None else grace_minutes
    now = time_provider.now().replace(tzinfo=None)
    candidates = (
        db.query(ClassSession)
        .filter(ClassSession.status.in_(['scheduled', 'open', 'submitted', 'running']), ClassSession.center_id == center_id)
        .order_by(ClassSession.scheduled_start.asc(), ClassSession.id.asc())
        .all()
    )

    closed_count = 0
    missed_count = 0
    inspected = 0

    for session in candidates:
        locked_session = (
            db.query(ClassSession)
            .filter(ClassSession.id == int(session.id), ClassSession.center_id == center_id)
            .with_for_update()
            .first()
        )
        if not locked_session:
            continue
        logger.info('attendance_locked', extra={'session_id': int(locked_session.id)})
        if now <= _session_end_with_grace(locked_session, grace):
            continue
        inspected += 1
        records = _attendance_records_for_session(db, locked_session)
        has_attendance = len(records) > 0

        should_run_post_class = bool(has_attendance and locked_session.post_class_processed_at is None)
        if should_run_post_class:
            post_class_failed = False
            try:
                run_post_class_pipeline(
                    db=db,
                    batch_id=locked_session.batch_id,
                    attendance_date=locked_session.scheduled_start.date(),
                    records=records,
                    subject=locked_session.subject or 'General',
                    teacher_id=locked_session.teacher_id or 0,
                    scheduled_start=locked_session.scheduled_start,
                    topic_planned=locked_session.topic_planned or '',
                    topic_completed=locked_session.topic_completed or '',
                )
            except Exception as exc:
                post_class_failed = True
                locked_session.post_class_error = True
                logger.error(
                    'automation_failure',
                    extra={
                        'job': 'auto_close_post_class_pipeline',
                        'center_id': int(locked_session.center_id or 1),
                        'entity_id': int(locked_session.id),
                        'error': str(exc),
                    },
                )
                log_automation_failure(
                    db,
                    job_name='auto_close_post_class_pipeline',
                    entity_type='class_session',
                    entity_id=int(locked_session.id),
                    error_message=str(exc),
                    center_id=int(locked_session.center_id or 1),
                )
            try:
                run_post_class_automation(
                    db,
                    session_id=locked_session.id,
                    trigger_source='auto_close',
                    time_provider=time_provider,
                )
            except Exception as exc:
                post_class_failed = True
                locked_session.post_class_error = True
                logger.error(
                    'automation_failure',
                    extra={
                        'job': 'auto_close_post_class_automation',
                        'center_id': int(locked_session.center_id or 1),
                        'entity_id': int(locked_session.id),
                        'error': str(exc),
                    },
                )
                log_automation_failure(
                    db,
                    job_name='auto_close_post_class_automation',
                    entity_type='class_session',
                    entity_id=int(locked_session.id),
                    error_message=str(exc),
                    center_id=int(locked_session.center_id or 1),
                )
            if not post_class_failed:
                locked_session.post_class_processed_at = now

        if has_attendance and locked_session.status == 'open':
            locked_session.status = 'closed'
            locked_session.closed_at = now
            closed_count += 1
        elif (not has_attendance) and locked_session.status == 'open':
            locked_session.status = 'missed'
            locked_session.closed_at = now
            create_pending_action(
                db=db,
                action_type='attendance_missed',
                student_id=None,
                related_session_id=locked_session.id,
                teacher_id=locked_session.teacher_id or None,
                session_id=locked_session.id,
                due_at=now,
                note=f'Attendance missed for session {locked_session.id} ({locked_session.scheduled_start.date()})',
            )
            _notify_teacher_missed_session(db, locked_session)
            missed_count += 1

        db.commit()
        # CQRS-lite snapshots: best-effort refresh (never break the scheduler job).
        try:
            if locked_session.teacher_id:
                snapshot_service.refresh_teacher_today_snapshot(db, teacher_id=int(locked_session.teacher_id))
            snapshot_service.refresh_admin_ops_snapshot(db)
            if has_attendance:
                for rec in records:
                    snapshot_service.refresh_student_dashboard_snapshot(db, student_id=int(rec.student_id))
        except Exception:
            pass

    return {
        'inspected': inspected,
        'closed': closed_count,
        'missed': missed_count,
        'grace_minutes': grace,
    }
