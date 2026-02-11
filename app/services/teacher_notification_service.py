from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AuthUser, Batch, ClassSession, FeeRecord, Student, StudentRiskProfile
from app.services.action_token_service import create_action_token
from app.services.comms_service import queue_teacher_telegram
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.frontend_routes import attendance_review_url, attendance_session_url


def _attendance_token(
    db: Session,
    session_id: int,
    batch_id: int,
    schedule_id: int | None,
    teacher_id: int,
    action_type: str,
    expires_at: datetime,
) -> str:
    ttl_minutes = int(max(1, (expires_at - datetime.utcnow()).total_seconds() // 60))
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


def _session_end_time(session: ClassSession) -> datetime:
    return session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)


def send_class_start_reminder(db: Session, session: ClassSession, schedule_id: int | None) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    for target in _teacher_targets(db):
        delete_minutes = _teacher_delete_minutes(db, target['teacher_id'])
        end_time = _session_end_time(session)
        delete_at = min(session.scheduled_start, datetime.utcnow() + timedelta(minutes=delete_minutes))
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            schedule_id,
            target['teacher_id'],
            action_type='attendance_open',
            expires_at=end_time + timedelta(minutes=10),
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


def send_attendance_open_alert(db: Session, session: ClassSession, schedule_id: int | None) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    for target in _teacher_targets(db):
        delete_minutes = _teacher_delete_minutes(db, target['teacher_id'])
        end_time = _session_end_time(session)
        delete_at = min(session.scheduled_start, datetime.utcnow() + timedelta(minutes=delete_minutes))
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            schedule_id,
            target['teacher_id'],
            action_type='attendance_open',
            expires_at=end_time + timedelta(minutes=10),
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


def send_attendance_closing_soon(db: Session, session: ClassSession) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    for target in _teacher_targets(db):
        delete_minutes = _teacher_delete_minutes(db, target['teacher_id'])
        end_time = _session_end_time(session)
        delete_at = min(session.scheduled_start, datetime.utcnow() + timedelta(minutes=delete_minutes))
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            None,
            target['teacher_id'],
            action_type='attendance_open',
            expires_at=end_time + timedelta(minutes=10),
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


def send_class_summary(db: Session, session: ClassSession) -> None:
    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        return
    counts = _summary_counts(db, session)
    end_time = _session_end_time(session)
    if end_time + timedelta(minutes=10) <= datetime.utcnow():
        return
    for target in _teacher_targets(db):
        token = _attendance_token(
            db,
            session.id,
            batch.id,
            None,
            target['teacher_id'],
            action_type='attendance_review',
            expires_at=end_time + timedelta(minutes=10),
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
