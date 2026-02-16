from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider, ensure_aware
from app.models import AuthUser, Batch, ClassSession, FeeRecord, Student, StudentBatchMap, StudentRiskProfile
from app.services.action_token_service import create_action_token
from app.services.comms_service import queue_teacher_telegram
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.services.student_notification_service import notify_student
from app.frontend_routes import attendance_review_url, attendance_session_url


APP_ZONE = ZoneInfo(settings.app_timezone or 'Asia/Kolkata')


def _attendance_token(
    db: Session,
    session_id: int,
    batch_id: int,
    schedule_id: int | None,
    teacher_id: int,
    action_type: str,
    expires_at: datetime,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> str:
    ttl_minutes = int(max(1, (ensure_aware(expires_at) - time_provider.now()).total_seconds() // 60))
    token = create_action_token(
        db=db,
        action_type=action_type,
        payload={
            'session_id': session_id,
            'batch_id': batch_id,
            'schedule_id': schedule_id,
            'teacher_id': teacher_id,
            'role': 'teacher',
        },
        ttl_minutes=ttl_minutes,
    )
    return token['token']


def _teacher_delete_minutes(db: Session, teacher_id: int) -> int:
    row = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    if not row or not row.notification_delete_minutes:
        return 15
    return max(1, min(int(row.notification_delete_minutes), 240))


def _summary_counts(db: Session, session: ClassSession) -> dict:
    attendance_date = session.scheduled_start.date()
    students = db.query(Student).filter(Student.batch_id == session.batch_id).all()
    student_ids = [s.id for s in students]
    if not student_ids:
        return {'absent': 0, 'late': 0, 'fee_dues': 0}

    from app.models import AttendanceRecord
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.student_id.in_(student_ids),
        AttendanceRecord.attendance_date == attendance_date,
    ).all()
    by_student = {r.student_id: r for r in records}
    absent = sum(1 for s in students if by_student.get(s.id) and by_student[s.id].status == 'Absent')
    late = sum(1 for s in students if by_student.get(s.id) and by_student[s.id].status == 'Late')

    fee_due = db.query(FeeRecord).filter(
        FeeRecord.student_id.in_(student_ids),
        FeeRecord.is_paid.is_(False),
    ).count()
    return {'absent': absent, 'late': late, 'fee_dues': fee_due}


def _teacher_targets(db: Session) -> list[dict]:
    from app.models import AllowedUser, AllowedUserStatus, Role
    teachers = (
        db.query(AllowedUser)
        .filter(AllowedUser.role == Role.TEACHER.value, AllowedUser.status == AllowedUserStatus.ACTIVE.value)
        .all()
    )
    targets = []
    for teacher in teachers:
        auth_user = db.query(AuthUser).filter(AuthUser.phone == teacher.phone).first()
        if not auth_user:
            continue
        chat_id = resolve_teacher_chat_id(db, teacher.phone)
        if not chat_id:
            continue
        targets.append({'teacher_id': auth_user.id, 'chat_id': chat_id, 'phone': teacher.phone})
    return targets


def _as_app_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=APP_ZONE)
    return dt.astimezone(APP_ZONE)


def _session_end_time(session: ClassSession) -> datetime:
    return _as_app_aware(session.scheduled_start) + timedelta(minutes=session.duration_minutes or 60)


def send_class_start_reminder(
    db: Session,
    session: ClassSession,
    schedule_id: int | None,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    for target in _teacher_targets(db):
        delete_minutes = _teacher_delete_minutes(db, target['teacher_id'])
        end_time = _session_end_time(session)
        delete_at = min(
            _as_app_aware(session.scheduled_start),
            time_provider.now() + timedelta(minutes=delete_minutes),
        )
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            schedule_id,
            target['teacher_id'],
            action_type='attendance_open',
            expires_at=end_time + timedelta(minutes=10),
            time_provider=time_provider,
        )
        link = attendance_session_url(session.id, token)
        message = (
            f"{batch.name}\n"
            f"Class starts at {session.scheduled_start.strftime('%I:%M %p')}\n"
            "👉 Open Attendance\n"
            f"{link}"
        )
        queue_teacher_telegram(
            db,
            teacher_id=target['teacher_id'],
            chat_id=target['chat_id'],
            message=message,
            batch_id=batch.id,
            delete_at=delete_at,
            notification_type='class_start',
            session_id=session.id,
        )


def send_attendance_open_alert(
    db: Session,
    session: ClassSession,
    schedule_id: int | None,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    for target in _teacher_targets(db):
        delete_minutes = _teacher_delete_minutes(db, target['teacher_id'])
        end_time = _session_end_time(session)
        delete_at = min(
            _as_app_aware(session.scheduled_start),
            time_provider.now() + timedelta(minutes=delete_minutes),
        )
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            schedule_id,
            target['teacher_id'],
            action_type='attendance_open',
            expires_at=end_time + timedelta(minutes=10),
            time_provider=time_provider,
        )
        link = attendance_session_url(session.id, token)
        message = (
            f"{batch.name} — Attendance open\n"
            f"Today @ {session.scheduled_start.strftime('%H:%M')}\n"
            "👉 Mark Attendance\n"
            f"{link}"
        )
        queue_teacher_telegram(
            db,
            teacher_id=target['teacher_id'],
            chat_id=target['chat_id'],
            message=message,
            batch_id=batch.id,
            delete_at=delete_at,
            notification_type='attendance_open',
            session_id=session.id,
        )


def send_attendance_closing_soon(
    db: Session,
    session: ClassSession,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    for target in _teacher_targets(db):
        delete_minutes = _teacher_delete_minutes(db, target['teacher_id'])
        end_time = _session_end_time(session)
        delete_at = min(
            _as_app_aware(session.scheduled_start),
            time_provider.now() + timedelta(minutes=delete_minutes),
        )
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            None,
            target['teacher_id'],
            action_type='attendance_open',
            expires_at=end_time + timedelta(minutes=10),
            time_provider=time_provider,
        )
        link = attendance_session_url(session.id, token)
        message = (
            f"{batch.name} — Attendance closing soon\n"
            f"Today @ {session.scheduled_start.strftime('%H:%M')}\n"
            "👉 Submit Attendance\n"
            f"{link}"
        )
        queue_teacher_telegram(
            db,
            teacher_id=target['teacher_id'],
            chat_id=target['chat_id'],
            message=message,
            batch_id=batch.id,
            delete_at=delete_at,
            notification_type='attendance_closing',
            session_id=session.id,
        )


def send_class_summary(
    db: Session,
    session: ClassSession,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return {'sent': False, 'targets': [], 'reason': 'batch_not_found'}
    counts = _summary_counts(db, session)
    end_time = _session_end_time(session)
    if end_time + timedelta(minutes=10) <= time_provider.now():
        return {'sent': False, 'targets': [], 'reason': 'session_expired'}
    targets = _teacher_targets(db)
    if session.teacher_id:
        auth_user = db.query(AuthUser).filter(AuthUser.id == int(session.teacher_id)).first()
        if auth_user:
            chat_id = resolve_teacher_chat_id(db, auth_user.phone)
            targets = [{'teacher_id': int(auth_user.id), 'chat_id': chat_id, 'phone': auth_user.phone}] if chat_id else []
        else:
            targets = []

    delivered_targets = []
    for target in targets:
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            None,
            target['teacher_id'],
            action_type='attendance_review',
            expires_at=end_time + timedelta(minutes=10),
            time_provider=time_provider,
        )
        link = attendance_review_url(session.id, token)
        message = (
            f"{batch.name} — Attendance Submitted\n"
            f"{session.scheduled_start.strftime('%I:%M %p')}–{end_time.strftime('%I:%M %p')}\n"
            "👉 Review / Edit Attendance\n"
            f"{link}"
        )
        queue_teacher_telegram(
            db,
            teacher_id=target['teacher_id'],
            chat_id=target['chat_id'],
            message=message,
            batch_id=batch.id,
            critical=True,
            delete_at=end_time + timedelta(minutes=10),
            notification_type='attendance_submitted',
            session_id=session.id,
        )
        delivered_targets.append(
            {
                'teacher_id': int(target['teacher_id']),
                'chat_id': str(target['chat_id']),
                'notification_type': 'attendance_submitted',
                'session_id': int(session.id),
            }
        )
    return {'sent': bool(delivered_targets), 'targets': delivered_targets, 'reason': 'ok' if delivered_targets else 'no_targets'}


def send_batch_rescheduled_alert(
    db: Session,
    *,
    actor_teacher_id: int,
    batch_id: int,
    override_date,
    new_start_time: str | None,
    new_duration_minutes: int | None,
    cancelled: bool,
    reason: str = '',
) -> None:
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        return

    date_text = override_date.strftime('%d-%m-%Y') if hasattr(override_date, 'strftime') else str(override_date)
    student_message = (
        "Batch Schedule Update\n"
        f"{batch.name}\n"
        f"Date: {date_text}\n"
    )
    if cancelled:
        message = student_message + "Status: Cancelled"
    else:
        time_text = new_start_time or '--:--'
        duration_text = int(new_duration_minutes or 60)
        message = student_message + f"Time: {time_text}\nDuration: {duration_text} mins"
    if reason:
        message += f"\nReason: {reason.strip()}"

    students = (
        db.query(StudentBatchMap, Student)
        .join(Student, Student.id == StudentBatchMap.student_id)
        .filter(
            StudentBatchMap.batch_id == int(batch.id),
            StudentBatchMap.active.is_(True),
        )
        .all()
    )
    for _, student in students:
        notify_student(
            db,
            student=student,
            message=message,
            notification_type='student_batch_rescheduled',
            critical=True,
        )

    actor = db.query(AuthUser).filter(AuthUser.id == actor_teacher_id).first()
    if not actor:
        return
    chat_id = resolve_teacher_chat_id(db, actor.phone or '')
    if not chat_id:
        return

    queue_teacher_telegram(
        db,
        teacher_id=actor_teacher_id,
        chat_id=chat_id,
        message=message,
        batch_id=batch.id,
        critical=True,
        notification_type='batch_rescheduled',
        session_id=None,
    )
