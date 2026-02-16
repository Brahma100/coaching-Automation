from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.communication.communication_event import CommunicationEvent, CommunicationEventType
from app.config import settings
from app.frontend_routes import session_summary_url
from app.models import AllowedUser, AllowedUserStatus, AttendanceRecord, AuthUser, Batch, ClassSession, FeeRecord, Student
from app.services.action_token_service import create_action_token
from app.services.batch_membership_service import list_active_student_ids_for_batch
from app.services.comms_service import emit_communication_event
from app.services.daily_teacher_brief_service import resolve_teacher_chat_id
from app.services.rule_config_service import get_effective_rule_config
from app.services.student_automation_engine import send_student_attendance_feedback
from app.services.inbox_automation import create_absentee_actions, create_fee_actions, create_review_actions
from app.metrics import timed_service
from app.core.time_provider import TimeProvider, default_time_provider


logger = logging.getLogger(__name__)


def _session_end_time(session: ClassSession) -> datetime:
    return session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)


def _teacher_targets_for_session(db: Session, session: ClassSession) -> list[dict]:
    if session.teacher_id:
        auth_user = db.query(AuthUser).filter(AuthUser.id == session.teacher_id).first()
        if not auth_user:
            return []
        chat_id = resolve_teacher_chat_id(db, auth_user.phone)
        if not chat_id:
            return []
        return [{'teacher_id': auth_user.id, 'chat_id': chat_id, 'phone': auth_user.phone}]

    teachers = (
        db.query(AllowedUser)
        .filter(AllowedUser.role == 'teacher', AllowedUser.status == AllowedUserStatus.ACTIVE.value)
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


def _teacher_ids_for_session(db: Session, session: ClassSession) -> list[int]:
    if session.teacher_id:
        return [session.teacher_id]
    teachers = (
        db.query(AllowedUser)
        .filter(AllowedUser.role == 'teacher', AllowedUser.status == AllowedUserStatus.ACTIVE.value)
        .all()
    )
    ids = []
    for teacher in teachers:
        auth_user = db.query(AuthUser).filter(AuthUser.phone == teacher.phone).first()
        if auth_user:
            ids.append(auth_user.id)
    return ids


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


def _rule_attendance_completeness(student_ids: list[int], records: list[AttendanceRecord]) -> dict:
    marked_ids = {row.student_id for row in records}
    unmarked = [sid for sid in student_ids if sid not in marked_ids]
    return {'unmarked_students': unmarked}


def _rule_absence_detection(records: list[AttendanceRecord]) -> dict:
    absent = [row.student_id for row in records if row.status == 'Absent']
    late = [row.student_id for row in records if row.status == 'Late']
    return {'absent_students': absent, 'late_students': late}


def _rule_fee_context(db: Session, present_ids: list[int]) -> dict:
    if not present_ids:
        return {'fee_due_students': [], 'fee_due_total': 0.0}
    fee_rows = db.query(FeeRecord).filter(
        FeeRecord.student_id.in_(present_ids),
        FeeRecord.is_paid.is_(False),
    ).all()
    fee_due_by_student = {}
    for fee in fee_rows:
        due = max(0.0, float(fee.amount) - float(fee.paid_amount))
        if due <= 0:
            continue
        fee_due_by_student.setdefault(fee.student_id, 0.0)
        fee_due_by_student[fee.student_id] += due
    return {
        'fee_due_students': sorted(fee_due_by_student.keys()),
        'fee_due_total': round(sum(fee_due_by_student.values()), 2),
    }


def _rule_risk_indicators(db: Session, student_ids: list[int]) -> list[dict]:
    flags = []
    for student_id in student_ids:
        rows = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.student_id == student_id)
            .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.id.desc())
            .limit(5)
            .all()
        )
        if not rows:
            continue
        recent_statuses = [row.status for row in rows]
        absent_count = sum(1 for status in recent_statuses if status == 'Absent')
        if absent_count >= 2:
            flags.append({'student_id': student_id, 'type': 'frequent_absence', 'count': absent_count})
        if len(recent_statuses) >= 3 and all(status in ('Absent', 'Late') for status in recent_statuses[:3]):
            flags.append({'student_id': student_id, 'type': 'low_attendance_streak'})
    return flags


@timed_service('post_class_automation')
def run_post_class_automation(
    db: Session,
    session_id: int,
    trigger_source: str,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        logger.info('post_class_automation_missing_session', extra={'session_id': session_id})
        return {
            'session_id': session_id,
            'rules_triggered': [],
            'notifications_sent': [],
            'notifications_suppressed': ['post_class_summary'],
            'flags_created': [],
        }

    batch = db.query(Batch).filter(Batch.id == session.batch_id).first()
    if not batch:
        logger.info('post_class_automation_missing_batch', extra={'session_id': session_id, 'batch_id': session.batch_id})
        return {
            'session_id': session_id,
            'rules_triggered': [],
            'notifications_sent': [],
            'notifications_suppressed': ['post_class_summary'],
            'flags_created': [],
        }

    rules = get_effective_rule_config(db, batch_id=session.batch_id)
    attendance_records = _attendance_records_for_session(db, session)
    student_ids = list_active_student_ids_for_batch(db, session.batch_id)
    students_by_id = {row.id: row for row in db.query(Student).filter(Student.id.in_(student_ids)).all()} if student_ids else {}

    completeness = _rule_attendance_completeness(student_ids, attendance_records)
    absences = _rule_absence_detection(attendance_records)
    present_ids = [row.student_id for row in attendance_records if row.status == 'Present']
    fee_context = _rule_fee_context(db, present_ids)
    risk_flags = _rule_risk_indicators(db, student_ids)

    rules_triggered = []
    if completeness['unmarked_students']:
        rules_triggered.append('attendance_incomplete')
    if absences['absent_students'] or absences['late_students']:
        rules_triggered.append('attendance_absences')
    if fee_context['fee_due_students']:
        rules_triggered.append('fee_dues_present')
    if risk_flags:
        rules_triggered.append('risk_indicators')

    issues_detected = len(rules_triggered) > 0

    notifications_sent = []
    notifications_suppressed = []
    flags_created = list(risk_flags)

    if issues_detected:
        end_time = _session_end_time(session)
        token = create_action_token(
            db=db,
            action_type='session_summary',
            payload={
                'session_id': session.id,
                'batch_id': session.batch_id,
                'teacher_id': session.teacher_id,
                'role': 'teacher',
            },
            ttl_minutes=int(max(1, ((end_time + timedelta(hours=24)) - time_provider.now().replace(tzinfo=None)).total_seconds() // 60)),
        )['token']
        link = session_summary_url(session.id, token)
        absentees_count = len(absences['absent_students']) + len(absences['late_students'])
        fee_total = fee_context['fee_due_total']
        message = (
            f"📘 {batch.name} — Class Completed\n"
            f"⚠ {absentees_count} absentees | ₹ {fee_total:.2f} fee dues\n"
            "👉 Review Class Summary\n"
            f"{link}"
        )
        delete_at = end_time + timedelta(hours=24)
        for target in _teacher_targets_for_session(db, session):
            emit_communication_event(
                db,
                CommunicationEvent(
                    event_type=CommunicationEventType.ATTENDANCE_SUBMITTED.value,
                    tenant_id=settings.communication_tenant_id,
                    actor_id=target['teacher_id'],
                    entity_type='class_session',
                    entity_id=session.id,
                    payload={
                        'batch_id': batch.id,
                        'batch_name': batch.name,
                        'absentees_count': absentees_count,
                        'fee_due_total': fee_total,
                        'trigger_source': trigger_source,
                    },
                    channels=['telegram'],
                ),
                message=message,
                chat_id=target['chat_id'],
                teacher_id=target['teacher_id'],
                batch_id=batch.id,
                delete_at=delete_at,
                notification_type='post_class_summary',
                session_id=session.id,
                reference_id=session.id,
                time_provider=time_provider,
            )
        notifications_sent.append('post_class_summary')
    else:
        notifications_suppressed.append('post_class_summary')

    teacher_ids = _teacher_ids_for_session(db, session)
    if teacher_ids:
        try:
            create_review_actions(db, session=session, teacher_ids=teacher_ids)
        except Exception:
            logger.exception('post_class_review_action_failed', extra={'session_id': session.id})
        if absences['absent_students'] or absences['late_students']:
            absent_ids = absences['absent_students'] + absences['late_students']
            try:
                create_absentee_actions(db, session=session, teacher_ids=teacher_ids, absent_student_ids=absent_ids)
            except Exception:
                logger.exception('post_class_absentee_action_failed', extra={'session_id': session.id})
        if fee_context['fee_due_students']:
            try:
                create_fee_actions(db, session=session, teacher_ids=teacher_ids, student_ids=fee_context['fee_due_students'])
            except Exception:
                logger.exception('post_class_fee_action_failed', extra={'session_id': session.id})

    if attendance_records:
        try:
            result = send_student_attendance_feedback(db, session_id=session.id)
            if result.get('sent', 0) > 0:
                notifications_sent.append('student_attendance')
        except Exception:
            logger.exception('post_class_student_attendance_failed', extra={'session_id': session.id})

    result = {
        'session_id': session.id,
        'trigger_source': trigger_source,
        'rules_triggered': rules_triggered,
        'notifications_sent': notifications_sent,
        'notifications_suppressed': notifications_suppressed,
        'flags_created': flags_created,
    }
    logger.info('post_class_automation_complete', extra=result)
    return result
