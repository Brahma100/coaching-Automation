from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.services.attendance_service import get_attendance_for_batch_today, submit_attendance
from app.services.class_session_resolver import is_session_locked, resolve_or_create_class_session
from app.services.class_session_service import get_session
from app.services.teacher_notification_service import send_class_summary
from app.services import snapshot_service


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


def load_attendance_session_sheet(
    db: Session,
    session_id: int,
    *,
    actor_role: str = 'admin',
    actor_user_id: int = 0,
) -> dict:
    session = get_session(db, session_id)
    if not session:
        raise ValueError('Class session not found')

    attendance_date = session.scheduled_start.date()
    rows = get_attendance_for_batch_today(
        db,
        session.batch_id,
        attendance_date,
        actor_role=actor_role,
        actor_user_id=actor_user_id,
    )
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
    allow_edit_submitted: bool = False,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    session = get_session(db, session_id)
    if not session:
        raise ValueError('Class session not found')
    if session.status in ('closed', 'missed'):
        raise ValueError('Attendance window closed for this class.')
    if is_session_locked(session) and actor_role != 'admin' and not allow_edit_submitted:
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
        actor_role=actor_role,
        actor_user_id=teacher_id,
    )
    refreshed = get_session(db, session_id)
    summary_notification_debug = {'sent': False, 'targets': [], 'reason': 'session_not_refreshed'}
    if refreshed:
        try:
            # Always send teacher-facing attendance-submitted summary on explicit submit.
            summary_notification_debug = send_class_summary(db, refreshed, time_provider=time_provider)
        except Exception:
            summary_notification_debug = {'sent': False, 'targets': [], 'reason': 'send_error'}

    # CQRS-lite snapshots: best-effort refresh (never break the write path).
    try:
        actor_teacher_id = int((refreshed.teacher_id if refreshed else None) or teacher_id or 0)
        snapshot_service.refresh_teacher_today_snapshot(db, teacher_id=actor_teacher_id)
        snapshot_service.refresh_admin_ops_snapshot(db)
        student_ids = {int(item.get('student_id') or 0) for item in records}
        for student_id in student_ids:
            if student_id > 0:
                snapshot_service.refresh_student_dashboard_snapshot(db, student_id=student_id)
    except Exception:
        pass
    return {
        **result,
        'notification_debug': {
            'attendance_submitted': summary_notification_debug,
        },
    }
