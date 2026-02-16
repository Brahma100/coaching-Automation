from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.communication.communication_event import CommunicationEvent, CommunicationEventType
from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AttendanceRecord, ClassSession, CommunicationLog, Homework, HomeworkSubmission, Student
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.comms_service import emit_communication_event
from app.services.student_digest_service import build_student_digest


logger = logging.getLogger(__name__)

MAX_STUDENT_MESSAGES_PER_DAY = 2


def _start_of_today(*, time_provider: TimeProvider = default_time_provider) -> datetime:
    today = time_provider.today()
    return datetime.combine(today, datetime.min.time())


def _daily_message_count(
    db: Session,
    student_id: int,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> int:
    start = _start_of_today(time_provider=time_provider)
    return (
        db.query(CommunicationLog)
        .filter(
            CommunicationLog.student_id == student_id,
            CommunicationLog.channel == 'telegram',
            CommunicationLog.created_at >= start,
        )
        .count()
    )


def _can_send_today(db: Session, student_id: int, *, time_provider: TimeProvider = default_time_provider) -> bool:
    return _daily_message_count(db, student_id, time_provider=time_provider) < MAX_STUDENT_MESSAGES_PER_DAY


def _already_sent(
    db: Session,
    *,
    student_id: int,
    notification_type: str,
    session_id: int | None = None,
    reference_id: int | None = None,
) -> bool:
    query = db.query(CommunicationLog).filter(
        CommunicationLog.student_id == student_id,
        CommunicationLog.channel == 'telegram',
        CommunicationLog.notification_type == notification_type,
    )
    if session_id is not None:
        query = query.filter(CommunicationLog.session_id == session_id)
    if reference_id is not None:
        query = query.filter(CommunicationLog.reference_id == reference_id)
    return query.first() is not None


def send_student_attendance_feedback(
    db: Session,
    session_id: int,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        return {'sent': 0, 'suppressed': 0}
    attendance_date = session.scheduled_start.date()
    student_ids = list_active_student_ids_for_batch(db, session.batch_id)
    if not student_ids:
        return {'sent': 0, 'suppressed': 0}
    records = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_date == attendance_date,
        AttendanceRecord.student_id.in_(student_ids),
    ).all()
    sent = 0
    suppressed = 0
    for rec in records:
        student = db.query(Student).filter(Student.id == rec.student_id).first()
        if not student or not student.telegram_chat_id:
            continue
        if _already_sent(db, student_id=student.id, notification_type='student_attendance', session_id=session.id):
            suppressed += 1
            continue
        if not _can_send_today(db, student.id, time_provider=time_provider):
            suppressed += 1
            continue
        message = (
            f"📘 {session.subject or 'Class'}\n"
            f"Attendance today: {rec.status}"
        )
        emit_communication_event(
            db,
            CommunicationEvent(
                event_type=CommunicationEventType.ATTENDANCE_SUBMITTED.value,
                tenant_id=settings.communication_tenant_id,
                actor_id=session.teacher_id,
                entity_type='class_session',
                entity_id=session.id,
                payload={'student_id': student.id, 'attendance_status': rec.status},
                channels=['telegram'],
            ),
            message=message,
            chat_id=student.telegram_chat_id,
            student_id=student.id,
            notification_type='student_attendance',
            session_id=session.id,
            reference_id=session.id,
            time_provider=time_provider,
        )
        sent += 1
    return {'sent': sent, 'suppressed': suppressed}


def send_homework_assigned(db: Session, homework: Homework, *, time_provider: TimeProvider = default_time_provider) -> dict:
    sent = 0
    suppressed = 0
    students = db.query(Student).filter(Student.enable_homework_reminders.is_(True)).all()
    for student in students:
        if not student.telegram_chat_id:
            continue
        if _already_sent(db, student_id=student.id, notification_type='homework_assigned', reference_id=homework.id):
            suppressed += 1
            continue
        if not _can_send_today(db, student.id, time_provider=time_provider):
            suppressed += 1
            continue
        message = (
            "📚 Homework assigned:\n"
            f"{homework.title}\n"
            f"Due: {homework.due_date}"
        )
        emit_communication_event(
            db,
            CommunicationEvent(
                event_type=CommunicationEventType.HOMEWORK_ASSIGNED.value,
                tenant_id=settings.communication_tenant_id,
                actor_id=None,
                entity_type='homework',
                entity_id=homework.id,
                payload={'student_id': student.id, 'title': homework.title},
                channels=['telegram'],
            ),
            message=message,
            chat_id=student.telegram_chat_id,
            student_id=student.id,
            notification_type='homework_assigned',
            reference_id=homework.id,
            time_provider=time_provider,
        )
        sent += 1
    return {'sent': sent, 'suppressed': suppressed}


def send_homework_due_tomorrow(db: Session, *, center_id: int, time_provider: TimeProvider = default_time_provider) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    tomorrow = time_provider.today() + timedelta(days=1)
    logger.warning('center_filter_missing service=student_automation query=homework_without_center_id')
    homeworks = db.query(Homework).filter(Homework.due_date == tomorrow).all()
    if not homeworks:
        return {'sent': 0, 'suppressed': 0}
    sent = 0
    suppressed = 0
    students = db.query(Student).filter(Student.enable_homework_reminders.is_(True), Student.center_id == center_id).all()
    for hw in homeworks:
        submitted_ids = {
            row.student_id
            for row in db.query(HomeworkSubmission.student_id).filter(HomeworkSubmission.homework_id == hw.id).all()
        }
        for student in students:
            if student.id in submitted_ids or not student.telegram_chat_id:
                continue
            if _already_sent(db, student_id=student.id, notification_type='homework_due_reminder', reference_id=hw.id):
                suppressed += 1
                continue
            if not _can_send_today(db, student.id, time_provider=time_provider):
                suppressed += 1
                continue
            message = (
                "⏰ Homework due tomorrow:\n"
                f"{hw.title}\n"
                f"Due: {hw.due_date}"
            )
            emit_communication_event(
                db,
                CommunicationEvent(
                    event_type=CommunicationEventType.HOMEWORK_ASSIGNED.value,
                    tenant_id=settings.communication_tenant_id,
                    actor_id=None,
                    entity_type='homework',
                    entity_id=hw.id,
                    payload={'student_id': student.id, 'title': hw.title, 'due_date': str(hw.due_date)},
                    channels=['telegram'],
                ),
                message=message,
                chat_id=student.telegram_chat_id,
                student_id=student.id,
                notification_type='homework_due_reminder',
                reference_id=hw.id,
                time_provider=time_provider,
            )
            sent += 1
    return {'sent': sent, 'suppressed': suppressed}


def send_daily_digest(db: Session, *, center_id: int, time_provider: TimeProvider = default_time_provider) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    sent = 0
    suppressed = 0
    students = db.query(Student).filter(Student.enable_daily_digest.is_(True), Student.center_id == center_id).all()
    for student in students:
        if not student.telegram_chat_id:
            continue
        if _already_sent(
            db,
            student_id=student.id,
            notification_type='student_daily_digest',
            reference_id=int(time_provider.today().strftime('%Y%m%d')),
        ):
            suppressed += 1
            continue
        if not _can_send_today(db, student.id, time_provider=time_provider):
            suppressed += 1
            continue
        digest = build_student_digest(db, student, center_id=int(student.center_id or 0))
        if not digest:
            suppressed += 1
            continue
        emit_communication_event(
            db,
            CommunicationEvent(
                event_type=CommunicationEventType.DAILY_BRIEF.value,
                tenant_id=settings.communication_tenant_id,
                actor_id=None,
                entity_type='student',
                entity_id=student.id,
                payload={'digest_date': int(time_provider.today().strftime('%Y%m%d'))},
                channels=['telegram'],
            ),
            message=digest,
            chat_id=student.telegram_chat_id,
            student_id=student.id,
            notification_type='student_daily_digest',
            reference_id=int(time_provider.today().strftime('%Y%m%d')),
            time_provider=time_provider,
        )
        sent += 1
    return {'sent': sent, 'suppressed': suppressed}


def send_weekly_motivation(db: Session, *, center_id: int, time_provider: TimeProvider = default_time_provider) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    sent = 0
    suppressed = 0
    cutoff = time_provider.today() - timedelta(days=7)
    students = db.query(Student).filter(Student.enable_motivation_messages.is_(True), Student.center_id == center_id).all()
    for student in students:
        if not student.telegram_chat_id:
            continue
        recent = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.attendance_date >= cutoff,
            )
            .order_by(AttendanceRecord.attendance_date.desc())
            .all()
        )
        if not recent:
            suppressed += 1
            continue
        all_present = all(row.status == 'Present' for row in recent)
        if not all_present:
            suppressed += 1
            continue
        already = (
            db.query(CommunicationLog)
            .filter(
                CommunicationLog.student_id == student.id,
                CommunicationLog.notification_type == 'student_motivation_weekly',
                CommunicationLog.created_at >= (time_provider.now().replace(tzinfo=None) - timedelta(days=7)),
            )
            .first()
        )
        if already:
            suppressed += 1
            continue
        if not _can_send_today(db, student.id, time_provider=time_provider):
            suppressed += 1
            continue
        message = "🔥 Great job!\nYou attended all classes this week."
        emit_communication_event(
            db,
            CommunicationEvent(
                event_type=CommunicationEventType.DAILY_BRIEF.value,
                tenant_id=settings.communication_tenant_id,
                actor_id=None,
                entity_type='student',
                entity_id=student.id,
                payload={'kind': 'weekly_motivation'},
                channels=['telegram'],
            ),
            message=message,
            chat_id=student.telegram_chat_id,
            student_id=student.id,
            notification_type='student_motivation_weekly',
            time_provider=time_provider,
        )
        sent += 1
    return {'sent': sent, 'suppressed': suppressed}


def send_risk_soft_warning(db: Session, student_id: int, *, time_provider: TimeProvider = default_time_provider) -> None:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or not student.telegram_chat_id:
        return
    if _already_sent(
        db,
        student_id=student.id,
        notification_type='risk_soft_warning',
        reference_id=int(time_provider.today().strftime('%Y%m%d')),
    ):
        return
    if not _can_send_today(db, student.id, time_provider=time_provider):
        return
    message = (
        "📘 Heads up!\n"
        "You’ve missed a few recent classes.\n"
        "Need help catching up? Check today’s notes."
    )
    emit_communication_event(
        db,
        CommunicationEvent(
            event_type=CommunicationEventType.ATTENDANCE_SUBMITTED.value,
            tenant_id=settings.communication_tenant_id,
            actor_id=None,
            entity_type='student',
            entity_id=student.id,
            payload={'kind': 'risk_soft_warning'},
            channels=['telegram'],
        ),
        message=message,
        chat_id=student.telegram_chat_id,
        student_id=student.id,
        notification_type='risk_soft_warning',
        reference_id=int(time_provider.today().strftime('%Y%m%d')),
        time_provider=time_provider,
    )
