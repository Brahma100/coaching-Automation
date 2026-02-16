from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.time_provider import default_time_provider
from app.models import ClassSession, TeacherAutomationRule
from app.services.teacher_communication_settings_service import is_event_enabled_for_teacher


RULE_CACHE_TTL_SECONDS = 60
_RULE_CACHE: dict[int, dict[str, Any]] = {}

DEFAULT_RULES = {
    'notify_on_attendance': True,
    'class_start_reminder': True,
    'fee_due_alerts': True,
    'student_absence_escalation': True,
    'homework_reminders': True,
}


def _cache_get(teacher_id: int) -> dict[str, bool] | None:
    item = _RULE_CACHE.get(int(teacher_id))
    if not item:
        return None
    if item['expires_at'] < default_time_provider.now().replace(tzinfo=None):
        _RULE_CACHE.pop(int(teacher_id), None)
        return None
    return dict(item['rules'])


def _cache_set(teacher_id: int, rules: dict[str, bool]) -> None:
    _RULE_CACHE[int(teacher_id)] = {
        'rules': dict(rules),
        'expires_at': default_time_provider.now().replace(tzinfo=None) + timedelta(seconds=RULE_CACHE_TTL_SECONDS),
    }


def _serialize(row: TeacherAutomationRule | None) -> dict[str, bool]:
    if not row:
        return dict(DEFAULT_RULES)
    return {
        'notify_on_attendance': bool(row.notify_on_attendance),
        'class_start_reminder': bool(row.class_start_reminder),
        'fee_due_alerts': bool(row.fee_due_alerts),
        'student_absence_escalation': bool(row.student_absence_escalation),
        'homework_reminders': bool(row.homework_reminders),
    }


def get_or_create_rules(db: Session, teacher_id: int) -> TeacherAutomationRule:
    row = db.query(TeacherAutomationRule).filter(TeacherAutomationRule.teacher_id == int(teacher_id)).first()
    if row:
        return row
    row = TeacherAutomationRule(teacher_id=int(teacher_id))
    db.add(row)
    db.commit()
    db.refresh(row)
    _cache_set(int(teacher_id), _serialize(row))
    return row


def get_rules(db: Session, teacher_id: int) -> dict[str, bool]:
    cached = _cache_get(int(teacher_id))
    if cached is not None:
        return cached
    row = get_or_create_rules(db, int(teacher_id))
    rules = _serialize(row)
    _cache_set(int(teacher_id), rules)
    return rules


def update_rules(
    db: Session,
    teacher_id: int,
    *,
    notify_on_attendance: bool,
    class_start_reminder: bool,
    fee_due_alerts: bool,
    student_absence_escalation: bool,
    homework_reminders: bool,
) -> dict[str, bool]:
    row = get_or_create_rules(db, int(teacher_id))
    row.notify_on_attendance = bool(notify_on_attendance)
    row.class_start_reminder = bool(class_start_reminder)
    row.fee_due_alerts = bool(fee_due_alerts)
    row.student_absence_escalation = bool(student_absence_escalation)
    row.homework_reminders = bool(homework_reminders)
    row.updated_at = default_time_provider.now().replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    rules = _serialize(row)
    _cache_set(int(teacher_id), rules)
    return rules


def resolve_teacher_id_for_rule_check(db: Session, teacher_id: int | None = None, session_id: int | None = None) -> int | None:
    if teacher_id:
        return int(teacher_id)
    if session_id:
        session = db.query(ClassSession).filter(ClassSession.id == int(session_id)).first()
        if session and int(session.teacher_id or 0) > 0:
            return int(session.teacher_id)
    return None


def _rule_key_for_message(event_type: str | None, notification_type: str | None) -> str | None:
    event = (event_type or '').upper()
    note = (notification_type or '').lower()

    if event in {'ATTENDANCE_SUBMITTED'} or note in {'attendance_submitted', 'student_attendance'}:
        return 'notify_on_attendance'
    if event in {'CLASS_STARTED'} or note in {'class_start', 'attendance_open', 'attendance_closing'}:
        return 'class_start_reminder'
    if event in {'FEE_DUE'} or note in {'fee_due', 'fee_due_alert', 'fee_due_reminder'}:
        return 'fee_due_alerts'
    if note in {'inbox_escalation'} or event in {'STUDENT_ADDED'}:
        return 'student_absence_escalation'
    if event in {'HOMEWORK_ASSIGNED'} or note in {'homework_assigned', 'homework_due_reminder'}:
        return 'homework_reminders'
    return None


def _event_type_for_dispatch(event_type: str | None, notification_type: str | None) -> str | None:
    event = (event_type or '').upper().strip()
    if event:
        return event
    note = (notification_type or '').lower().strip()
    if note in {'class_start', 'attendance_open', 'attendance_closing'}:
        return 'CLASS_STARTED'
    if note in {'attendance_submitted', 'student_attendance'}:
        return 'ATTENDANCE_SUBMITTED'
    if note in {'fee_due', 'fee_due_alert', 'fee_due_reminder'}:
        return 'FEE_DUE'
    if note in {'homework_assigned', 'homework_due_reminder'}:
        return 'HOMEWORK_ASSIGNED'
    if note in {'inbox_escalation'}:
        return 'STUDENT_ADDED'
    if note in {'batch_rescheduled'}:
        return 'BATCH_RESCHEDULED'
    if note in {'daily_brief'}:
        return 'DAILY_BRIEF'
    return None


def should_dispatch_for_teacher(
    db: Session,
    *,
    teacher_id: int | None = None,
    session_id: int | None = None,
    event_type: str | None = None,
    notification_type: str | None = None,
) -> tuple[bool, str]:
    resolved_teacher_id = resolve_teacher_id_for_rule_check(db, teacher_id=teacher_id, session_id=session_id)
    if not resolved_teacher_id:
        return True, 'no_teacher_context'

    effective_event_type = _event_type_for_dispatch(event_type, notification_type)
    if effective_event_type and not is_event_enabled_for_teacher(
        db,
        teacher_id=int(resolved_teacher_id),
        event_type=effective_event_type,
    ):
        return False, 'event_disabled'

    key = _rule_key_for_message(event_type, notification_type)
    if not key:
        return True, 'no_matching_rule'

    rules = get_rules(db, int(resolved_teacher_id))
    enabled = bool(rules.get(key, True))
    return enabled, key
