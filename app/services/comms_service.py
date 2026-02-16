import json
import logging
from datetime import datetime
import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.communication.communication_event import CommunicationEvent
from app.config import settings
from app.domain.communication_gateway import send_event as gateway_send_event
from app.core.quiet_hours import is_quiet_now as _core_is_quiet_now
from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AuthUser, CommunicationLog, Student
from app.services.rule_config_service import get_effective_rule_config
from app.services.teacher_automation_rules_service import should_dispatch_for_teacher
from app.services.telegram_actions import build_inline_actions_for_student


logger = logging.getLogger(__name__)


def _parse_hhmm(value: str):
    hour, minute = value.split(':', 1)
    return int(hour), int(minute)


def _is_quiet_now_for_batch(
    db: Session,
    batch_id: int | None,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    # DEPRECATED: use app.core.quiet_hours.is_quiet_now directly.
    cfg = get_effective_rule_config(db, batch_id=batch_id)
    now = time_provider.local_now(settings.app_timezone).time()
    return _core_is_quiet_now(cfg, now)


def _should_suppress_non_critical(db: Session, student: Student | None = None, student_id: int | None = None) -> bool:
    batch_id = None
    if student is not None:
        batch_id = student.batch_id
    elif student_id is not None:
        row = db.query(Student).filter(Student.id == student_id).first()
        batch_id = row.batch_id if row else None
    try:
        return _is_quiet_now_for_batch(db, batch_id=batch_id)
    except Exception:
        logger.exception('quiet_hours_eval_failed', extra={'batch_id': batch_id})
        return False


def _legacy_gateway_send(chat_id: str, message: str, reply_markup: dict | None = None) -> bool:
    if not settings.enable_telegram_notifications or not chat_id:
        return False
    results = gateway_send_event(
        'legacy.telegram.message',
        {
            'tenant_id': settings.communication_tenant_id,
            'user_id': 'legacy',
            'event_payload': {'channel': 'telegram'},
            'message': message,
            'channels': ['telegram'],
            'reply_markup': reply_markup or {},
            'critical': False,
            'entity_type': 'legacy',
            'entity_id': 0,
            'notification_type': 'legacy_message',
        },
        [{'chat_id': chat_id, 'user_id': 'legacy'}],
    )
    return bool(results and results[0].get('ok'))


def _legacy_gateway_send_with_id(chat_id: str, message: str, reply_markup: dict | None = None) -> tuple[bool, int | None]:
    return _legacy_gateway_send(chat_id, message, reply_markup=reply_markup), None


# Backward-compatible aliases for older test patches and legacy imports.
send_telegram_message = _legacy_gateway_send
send_telegram_message_with_id = _legacy_gateway_send_with_id


def delete_telegram_message(chat_id: str, message_id: int) -> bool:
    if not settings.enable_telegram_notifications:
        return False
    if not settings.telegram_bot_token or not chat_id or not message_id:
        return False
    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/deleteMessage"
    payload = {'chat_id': chat_id, 'message_id': int(message_id)}
    try:
        response = httpx.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            return True
        if response.status_code in (400, 404):
            logger.info('telegram_delete_already_gone', extra={'chat_id': chat_id, 'message_id': message_id})
            return True
        return False
    except httpx.HTTPError:
        logger.exception('telegram_delete_failed', extra={'chat_id': chat_id, 'message_id': message_id})
        return False


def _is_duplicate_notification(
    db: Session,
    channel: str,
    message: str,
    student_id: int | None,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    recent = db.query(CommunicationLog).filter(
        CommunicationLog.channel == channel,
        CommunicationLog.message == message,
        CommunicationLog.student_id == student_id,
        or_(
            CommunicationLog.delivery_status.in_(['sent', 'duplicate_suppressed']),
            CommunicationLog.status == 'sent',
        ),
    ).order_by(CommunicationLog.created_at.desc()).first()
    if not recent:
        return False
    return (time_provider.now().replace(tzinfo=None) - recent.created_at).total_seconds() <= 900


def _is_duplicate_teacher_event(
    db: Session,
    teacher_id: int,
    notification_type: str | None,
    session_id: int | None,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    if not notification_type or not session_id:
        return False
    recent = db.query(CommunicationLog).filter(
        CommunicationLog.teacher_id == teacher_id,
        CommunicationLog.notification_type == notification_type,
        CommunicationLog.session_id == session_id,
        or_(
            CommunicationLog.delivery_status.in_(['sent', 'duplicate_suppressed']),
            CommunicationLog.status == 'sent',
        ),
    ).order_by(CommunicationLog.created_at.desc()).first()
    if not recent:
        return False
    return (time_provider.now().replace(tzinfo=None) - recent.created_at).total_seconds() <= 3600


def _record_comm_log(db: Session, log: CommunicationLog, *, context: dict) -> None:
    try:
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception('notification_log_write_failed', extra=context)


def emit_communication_event(
    db: Session,
    event: CommunicationEvent,
    *,
    message: str,
    chat_id: str,
    student_id: int | None = None,
    teacher_id: int | None = None,
    notification_type: str | None = None,
    session_id: int | None = None,
    reference_id: int | None = None,
    batch_id: int | None = None,
    delete_at: datetime | None = None,
    reply_markup: dict | None = None,
    critical: bool = False,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    if not chat_id:
        return {'ok': False, 'status': 'skipped', 'reason': 'missing_chat_id'}
    if 'telegram' not in event.channels:
        logger.info('communication_event_unsupported_channel', extra={'channels': event.channels, 'event_type': event.event_type})
        return {'ok': False, 'status': 'skipped', 'reason': 'unsupported_channel'}

    allowed, matched_rule = should_dispatch_for_teacher(
        db,
        teacher_id=teacher_id or event.actor_id,
        session_id=session_id,
        event_type=event.event_type,
        notification_type=notification_type,
    )
    if not allowed:
        logger.info(
            'automation_rule_suppressed_dispatch',
            extra={'teacher_id': teacher_id or event.actor_id, 'rule': matched_rule, 'event_type': event.event_type},
        )
        return {'ok': False, 'status': 'suppressed', 'reason': 'automation_rule'}

    if teacher_id:
        if not critical and batch_id and _is_quiet_now_for_batch(db, batch_id=batch_id, time_provider=time_provider):
            logger.info('teacher_notification_suppressed_quiet_hours', extra={'teacher_id': teacher_id, 'batch_id': batch_id})
            return {'ok': False, 'status': 'suppressed', 'reason': 'quiet_hours'}
        if _is_duplicate_teacher_event(db, teacher_id, notification_type, session_id, time_provider=time_provider):
            logger.info('teacher_notification_suppressed_duplicate', extra={'teacher_id': teacher_id, 'event_type': notification_type})
            return {'ok': True, 'status': 'duplicate_suppressed'}
    else:
        if not critical and _should_suppress_non_critical(db, student_id=student_id):
            logger.info('notification_suppressed_quiet_hours', extra={'channel': 'telegram', 'student_id': student_id})
            return {'ok': False, 'status': 'suppressed', 'reason': 'quiet_hours'}
        if _is_duplicate_notification(db, 'telegram', message, student_id, time_provider=time_provider):
            logger.info('duplicate_notification_suppressed', extra={'channel': 'telegram', 'student_id': student_id})
            return {'ok': True, 'status': 'duplicate_suppressed'}

    results = gateway_send_event(
        event.event_type,
        {
            'db': db,
            'tenant_id': event.tenant_id,
            'user_id': str(event.actor_id) if event.actor_id is not None else 'system',
            'event_payload': event.payload,
            'message': message,
            'channels': event.channels,
            'priority': event.priority,
            'entity_type': event.entity_type,
            'entity_id': event.entity_id,
            'reply_markup': reply_markup or {},
            'critical': critical,
            'student_id': student_id,
            'teacher_id': teacher_id,
            'session_id': session_id,
            'notification_type': notification_type or '',
            'reference_id': reference_id,
            'delete_at': delete_at,
        },
        [{'chat_id': chat_id, 'user_id': str(event.actor_id) if event.actor_id is not None else 'system'}],
    )
    primary = results[0] if results else {'ok': False, 'status': 'failed'}
    status = 'sent' if primary.get('ok') else 'failed'

    if not primary.get('log_id'):
        log = CommunicationLog(
            student_id=student_id,
            teacher_id=teacher_id,
            session_id=session_id,
            channel='telegram',
            message=message,
            status=status,
            created_at=time_provider.now().replace(tzinfo=None),
            telegram_chat_id=chat_id,
            telegram_message_id=None,
            delete_at=delete_at,
            notification_type=notification_type or '',
            event_type=event.event_type,
            reference_id=reference_id,
            delivery_attempts=1,
            last_attempt_at=time_provider.now().replace(tzinfo=None),
            delivery_status=status,
        )
        _record_comm_log(
            db,
            log,
            context={
                'channel': 'telegram',
                'student_id': student_id,
                'teacher_id': teacher_id,
                'event_type': event.event_type,
            },
        )
    return primary


def _teacher_delete_minutes(db: Session, teacher_id: int) -> int:
    if not teacher_id:
        return 15
    row = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    if not row or not row.notification_delete_minutes:
        return 15
    return max(1, min(int(row.notification_delete_minutes), 240))


def _teacher_ephemeral_throttle(
    db: Session,
    teacher_id: int,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    now = time_provider.now().replace(tzinfo=None)
    count = db.query(CommunicationLog).filter(
        CommunicationLog.teacher_id == teacher_id,
        CommunicationLog.channel == 'telegram',
        CommunicationLog.delete_at.is_not(None),
        CommunicationLog.delete_at > now,
        CommunicationLog.status.not_in(['deleted', 'delete_failed']),
    ).count()
    return count >= 2


def _trim_oldest_teacher_ephemeral(db: Session, teacher_id: int) -> None:
    row = (
        db.query(CommunicationLog)
        .filter(
            CommunicationLog.teacher_id == teacher_id,
            CommunicationLog.channel == 'telegram',
            CommunicationLog.delete_at.is_not(None),
            CommunicationLog.status.not_in(['deleted', 'delete_failed']),
        )
        .order_by(CommunicationLog.delete_at.asc(), CommunicationLog.id.asc())
        .first()
    )
    if not row:
        return
    if not row.telegram_chat_id or not row.telegram_message_id:
        row.status = 'delete_failed'
        db.commit()
        return
    ok = delete_telegram_message(row.telegram_chat_id, row.telegram_message_id)
    if ok:
        row.status = 'deleted'
        row.delete_at = None
    else:
        row.status = 'delete_failed'
    db.commit()


def queue_teacher_telegram(
    db: Session,
    *,
    teacher_id: int,
    chat_id: str,
    message: str,
    batch_id: int | None = None,
    reply_markup: dict | None = None,
    critical: bool = False,
    delete_at: datetime | None = None,
    notification_type: str | None = None,
    session_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    allowed, matched_rule = should_dispatch_for_teacher(
        db,
        teacher_id=teacher_id,
        session_id=session_id,
        event_type=None,
        notification_type=notification_type,
    )
    if not allowed:
        logger.info(
            'automation_rule_suppressed_dispatch',
            extra={'teacher_id': teacher_id, 'rule': matched_rule, 'notification_type': notification_type},
        )
        return {'ok': False, 'status': 'suppressed', 'reason': 'automation_rule'}

    if not critical and batch_id and _is_quiet_now_for_batch(db, batch_id=batch_id, time_provider=time_provider):
        logger.info('teacher_notification_suppressed_quiet_hours', extra={'teacher_id': teacher_id, 'batch_id': batch_id})
        return {'ok': False, 'status': 'suppressed', 'reason': 'quiet_hours'}

    if _is_duplicate_teacher_event(db, teacher_id, notification_type, session_id, time_provider=time_provider):
        logger.info('teacher_notification_suppressed_duplicate', extra={'teacher_id': teacher_id, 'event_type': notification_type})
        return {'ok': True, 'status': 'duplicate_suppressed'}

    if delete_at and not critical and notification_type != 'attendance_submitted':
        if _teacher_ephemeral_throttle(db, teacher_id, time_provider=time_provider):
            if notification_type in ('class_start', 'attendance_open', 'attendance_closing'):
                _trim_oldest_teacher_ephemeral(db, teacher_id)
            if _teacher_ephemeral_throttle(db, teacher_id, time_provider=time_provider):
                logger.info('teacher_notification_throttled', extra={'teacher_id': teacher_id, 'event_type': notification_type})
                return {'ok': False, 'status': 'suppressed', 'reason': 'throttled'}

    if not notification_type:
        notification_type = 'unknown'
    # TODO: remove legacy paths later after all callers use domain gateway directly.
    results = gateway_send_event(
        notification_type or 'teacher_notification',
        {
            'db': db,
            'tenant_id': settings.communication_tenant_id,
            'user_id': str(teacher_id),
            'event_payload': {},
            'message': message,
            'channels': ['telegram'],
            'reply_markup': reply_markup or {},
            'critical': critical,
            'priority': None,
            'entity_type': 'teacher',
            'entity_id': teacher_id,
            'teacher_id': teacher_id,
            'session_id': session_id,
            'notification_type': notification_type,
            'reference_id': session_id,
            'delete_at': delete_at,
        },
        [{'chat_id': chat_id, 'user_id': str(teacher_id)}],
    )
    primary = results[0] if results else {'ok': False, 'status': 'failed'}
    ok = bool(primary.get('ok'))
    message_id = primary.get('message_id')
    status = 'sent' if ok else 'failed'
    if not primary.get('log_id'):
        log = CommunicationLog(
            teacher_id=teacher_id,
            session_id=session_id,
            channel='telegram',
            message=message,
            status=status,
            telegram_message_id=message_id,
            delete_at=delete_at,
            notification_type=notification_type,
            event_type=notification_type,
            reference_id=session_id,
            telegram_chat_id=chat_id,
            created_at=time_provider.now().replace(tzinfo=None),
            delivery_attempts=1,
            last_attempt_at=time_provider.now().replace(tzinfo=None),
            delivery_status=status,
        )
        _record_comm_log(db, log, context={'channel': 'telegram', 'teacher_id': teacher_id})
    return primary


def queue_telegram_by_chat_id(
    db: Session,
    chat_id: str,
    message: str,
    student_id: int | None = None,
    reply_markup: dict | None = None,
    critical: bool = False,
    notification_type: str | None = None,
    session_id: int | None = None,
    reference_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    allowed, matched_rule = should_dispatch_for_teacher(
        db,
        teacher_id=None,
        session_id=session_id,
        event_type=None,
        notification_type=notification_type,
    )
    if not allowed:
        logger.info(
            'automation_rule_suppressed_dispatch',
            extra={'session_id': session_id, 'rule': matched_rule, 'notification_type': notification_type},
        )
        return {'ok': False, 'status': 'suppressed', 'reason': 'automation_rule'}

    if not critical and _should_suppress_non_critical(db, student_id=student_id):
        logger.info('notification_suppressed_quiet_hours', extra={'channel': 'telegram', 'student_id': student_id})
        return {'ok': False, 'status': 'suppressed', 'reason': 'quiet_hours'}

    if _is_duplicate_notification(db, 'telegram', message, student_id, time_provider=time_provider):
        logger.info('duplicate_notification_suppressed', extra={'channel': 'telegram', 'student_id': student_id})
        return {'ok': True, 'status': 'duplicate_suppressed'}

    # TODO: remove legacy paths later after all callers use domain gateway directly.
    results = gateway_send_event(
        notification_type or 'student_notification',
        {
            'db': db,
            'tenant_id': settings.communication_tenant_id,
            'event_payload': {},
            'message': message,
            'channels': ['telegram'],
            'reply_markup': reply_markup or {},
            'critical': critical,
            'priority': None,
            'entity_type': 'student',
            'entity_id': student_id,
            'student_id': student_id,
            'session_id': session_id,
            'notification_type': notification_type or '',
            'reference_id': reference_id,
        },
        [{'chat_id': chat_id, 'user_id': str(student_id or 'system')}],
    )
    primary = results[0] if results else {'ok': False, 'status': 'failed'}
    status = 'sent' if primary.get('ok') else 'failed'
    if not primary.get('log_id'):
        log = CommunicationLog(
            student_id=student_id,
            channel='telegram',
            message=message,
            status=status,
            created_at=time_provider.now().replace(tzinfo=None),
            telegram_chat_id=chat_id,
            notification_type=notification_type or '',
            session_id=session_id,
            reference_id=reference_id,
            delivery_attempts=1,
            last_attempt_at=time_provider.now().replace(tzinfo=None),
            delivery_status=status,
        )
        _record_comm_log(db, log, context={'channel': 'telegram', 'student_id': student_id})
    return primary


def queue_notification(
    db: Session,
    student: Student | None,
    channel: str,
    message: str,
    critical: bool = False,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    if not critical and _should_suppress_non_critical(db, student=student):
        logger.info('notification_suppressed_quiet_hours', extra={'channel': channel, 'student_id': student.id if student else None})
        return {'ok': False, 'status': 'suppressed', 'reason': 'quiet_hours'}

    if _is_duplicate_notification(db, channel, message, student.id if student else None, time_provider=time_provider):
        logger.info('duplicate_notification_suppressed', extra={'channel': channel, 'student_id': student.id if student else None})
        return {'ok': True, 'status': 'duplicate_suppressed'}

    status = 'queued'
    if channel == 'telegram' and student and student.telegram_chat_id:
        # TODO: remove legacy paths later after all callers use domain gateway directly.
        results = gateway_send_event(
            'student.notification.queued',
            {
                'db': db,
                'tenant_id': settings.communication_tenant_id,
                'user_id': str(student.id),
                'event_payload': {'channel': 'telegram', 'student_id': student.id},
                'message': message,
                'channels': ['telegram', 'whatsapp'],
                'reply_markup': {},
                'critical': critical,
                'priority': None,
                'entity_type': 'student',
                'entity_id': student.id,
                'student_id': student.id,
            },
            [{'chat_id': student.telegram_chat_id, 'user_id': str(student.id)}],
        )
        status = 'sent' if results and results[0].get('ok') else 'failed'
        if results and results[0].get('log_id'):
            return results[0]

    log = CommunicationLog(
        student_id=student.id if student else None,
        channel=channel,
        message=message,
        status=status,
        created_at=time_provider.now().replace(tzinfo=None),
        telegram_chat_id=student.telegram_chat_id if student and channel == 'telegram' else None,
        delivery_attempts=1,
        last_attempt_at=time_provider.now().replace(tzinfo=None),
        delivery_status=status,
    )
    _record_comm_log(db, log, context={'channel': channel, 'student_id': student.id if student else None})
    return {'ok': status == 'sent', 'status': status}


def notify_attendance_status(db: Session, student: Student, status: str, attendance_date: str, comment: str = '') -> None:
    base = f"Attendance update for {student.name} on {attendance_date}: {status}."
    if comment:
        base += f" Note: {comment}"
    queue_notification(db, student, 'telegram', base)


def send_fee_reminder(db: Session, student: Student, amount_due: float, upi_link: str) -> None:
    message = f"Fee reminder: Rs {amount_due:.2f} is pending. Pay here: {upi_link}"
    buttons = build_inline_actions_for_student(db, student_id=student.id)
    queue_telegram_by_chat_id(db, student.telegram_chat_id, message, student_id=student.id, reply_markup=buttons)


def send_daily_brief(db: Session, student: Student, brief: str) -> None:
    queue_notification(db, student, 'telegram', brief)


def send_critical_alert(db: Session, student: Student | None, message: str) -> None:
    queue_notification(db, student, 'telegram', message, critical=True)


def delete_due_telegram_messages(
    db: Session,
    *,
    center_id: int,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    center_id = int(center_id or 0)
    if center_id <= 0:
        raise ValueError('center_id is required')
    now = time_provider.now().replace(tzinfo=None)
    student_ids = [int(sid) for (sid,) in db.query(Student.id).filter(Student.center_id == center_id).all()] or [-1]
    teacher_ids = [int(tid) for (tid,) in db.query(AuthUser.id).filter(AuthUser.center_id == center_id).all()] or [-1]
    rows = (
        db.query(CommunicationLog)
        .filter(
            CommunicationLog.channel == 'telegram',
            CommunicationLog.delete_at.is_not(None),
            CommunicationLog.delete_at <= now,
            CommunicationLog.telegram_message_id.is_not(None),
            CommunicationLog.status.not_in(['deleted', 'delete_failed']),
            or_(
                CommunicationLog.student_id.in_(student_ids),
                CommunicationLog.teacher_id.in_(teacher_ids),
            ),
        )
        .order_by(CommunicationLog.delete_at.asc(), CommunicationLog.id.asc())
        .all()
    )
    deleted = 0
    inspected = 0
    for row in rows:
        inspected += 1
        if not row.telegram_chat_id:
            row.status = 'delete_failed'
            db.commit()
            continue
        ok = delete_telegram_message(row.telegram_chat_id, row.telegram_message_id)
        if ok:
            row.status = 'deleted'
            deleted += 1
            row.delete_at = None
        else:
            row.status = 'delete_failed'
        db.commit()
    return {'inspected': inspected, 'deleted': deleted}
