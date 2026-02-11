import json
import logging
from datetime import datetime
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthUser, CommunicationLog, Student
from app.services.rule_config_service import get_effective_rule_config
from app.services.telegram_actions import build_inline_actions_for_student


logger = logging.getLogger(__name__)


def _parse_hhmm(value: str):
    hour, minute = value.split(':', 1)
    return int(hour), int(minute)


def _is_quiet_now_for_batch(db: Session, batch_id: int | None) -> bool:
    cfg = get_effective_rule_config(db, batch_id=batch_id)
    start_h, start_m = _parse_hhmm(cfg.get('quiet_hours_start', '22:00'))
    end_h, end_m = _parse_hhmm(cfg.get('quiet_hours_end', '06:00'))
    now = datetime.now().time()
    start_t = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_t = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    # Quiet window may wrap midnight.
    if start_t <= end_t:
        return start_t <= now < end_t
    return now >= start_t or now < end_t


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


def send_telegram_message(chat_id: str, message: str, reply_markup: dict | None = None) -> bool:
    if not settings.enable_telegram_notifications:
        return False
    if not settings.telegram_bot_token or not chat_id:
        return False

    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    try:
        response = httpx.post(url, json=payload, timeout=8)
        return response.status_code == 200
    except httpx.HTTPError:
        logger.exception('telegram_send_failed', extra={'chat_id': chat_id})
        return False


def send_telegram_message_with_id(chat_id: str, message: str, reply_markup: dict | None = None) -> tuple[bool, int | None]:
    if not settings.enable_telegram_notifications:
        return False, None
    if not settings.telegram_bot_token or not chat_id:
        return False, None

    url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    try:
        response = httpx.post(url, json=payload, timeout=8)
        if response.status_code != 200:
            return False, None
        data = response.json()
        message_id = data.get('result', {}).get('message_id')
        return True, int(message_id) if message_id is not None else None
    except httpx.HTTPError:
        logger.exception('telegram_send_failed', extra={'chat_id': chat_id})
        return False, None


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


def _is_duplicate_notification(db: Session, channel: str, message: str, student_id: int | None) -> bool:
    recent = db.query(CommunicationLog).filter(
        CommunicationLog.channel == channel,
        CommunicationLog.message == message,
        CommunicationLog.student_id == student_id,
    ).order_by(CommunicationLog.created_at.desc()).first()
    if not recent:
        return False
    return (datetime.utcnow() - recent.created_at).total_seconds() <= 900


def _is_duplicate_teacher_event(db: Session, teacher_id: int, notification_type: str | None, session_id: int | None) -> bool:
    if not notification_type or not session_id:
        return False
    recent = db.query(CommunicationLog).filter(
        CommunicationLog.teacher_id == teacher_id,
        CommunicationLog.notification_type == notification_type,
        CommunicationLog.session_id == session_id,
    ).order_by(CommunicationLog.created_at.desc()).first()
    if not recent:
        return False
    return (datetime.utcnow() - recent.created_at).total_seconds() <= 3600


def _record_comm_log(db: Session, log: CommunicationLog, *, context: dict) -> None:
    try:
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception('notification_log_write_failed', extra=context)


def _teacher_delete_minutes(db: Session, teacher_id: int) -> int:
    if not teacher_id:
        return 15
    row = db.query(AuthUser).filter(AuthUser.id == teacher_id).first()
    if not row or not row.notification_delete_minutes:
        return 15
    return max(1, min(int(row.notification_delete_minutes), 240))


def _teacher_ephemeral_throttle(db: Session, teacher_id: int) -> bool:
    now = datetime.utcnow()
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
) -> None:
    if not critical and batch_id and _is_quiet_now_for_batch(db, batch_id=batch_id):
        logger.info('teacher_notification_suppressed_quiet_hours', extra={'teacher_id': teacher_id, 'batch_id': batch_id})
        return

    if _is_duplicate_teacher_event(db, teacher_id, notification_type, session_id):
        logger.info('teacher_notification_suppressed_duplicate', extra={'teacher_id': teacher_id, 'event_type': notification_type})
        return

    if delete_at and not critical and notification_type != 'attendance_submitted':
        if _teacher_ephemeral_throttle(db, teacher_id):
            if notification_type in ('class_start', 'attendance_open', 'attendance_closing'):
                _trim_oldest_teacher_ephemeral(db, teacher_id)
            if _teacher_ephemeral_throttle(db, teacher_id):
                logger.info('teacher_notification_throttled', extra={'teacher_id': teacher_id, 'event_type': notification_type})
                return

    if not notification_type:
        notification_type = 'unknown'
    ok, message_id = send_telegram_message_with_id(chat_id, message, reply_markup=reply_markup)
    status = 'sent' if ok else 'failed'
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
        created_at=datetime.utcnow(),
    )
    _record_comm_log(db, log, context={'channel': 'telegram', 'teacher_id': teacher_id})


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
) -> None:
    if not critical and _should_suppress_non_critical(db, student_id=student_id):
        logger.info('notification_suppressed_quiet_hours', extra={'channel': 'telegram', 'student_id': student_id})
        return

    if _is_duplicate_notification(db, 'telegram', message, student_id):
        logger.info('duplicate_notification_suppressed', extra={'channel': 'telegram', 'student_id': student_id})
        return

    status = 'sent' if send_telegram_message(chat_id, message, reply_markup=reply_markup) else 'failed'
    log = CommunicationLog(
        student_id=student_id,
        channel='telegram',
        message=message,
        status=status,
        created_at=datetime.utcnow(),
        telegram_chat_id=chat_id,
        notification_type=notification_type or '',
        session_id=session_id,
        reference_id=reference_id,
    )
    _record_comm_log(db, log, context={'channel': 'telegram', 'student_id': student_id})


def queue_notification(db: Session, student: Student | None, channel: str, message: str, critical: bool = False) -> None:
    if not critical and _should_suppress_non_critical(db, student=student):
        logger.info('notification_suppressed_quiet_hours', extra={'channel': channel, 'student_id': student.id if student else None})
        return

    if _is_duplicate_notification(db, channel, message, student.id if student else None):
        logger.info('duplicate_notification_suppressed', extra={'channel': channel, 'student_id': student.id if student else None})
        return

    status = 'queued'
    if channel == 'telegram' and student and student.telegram_chat_id:
        status = 'sent' if send_telegram_message(student.telegram_chat_id, message) else 'failed'

    log = CommunicationLog(
        student_id=student.id if student else None,
        channel=channel,
        message=message,
        status=status,
        created_at=datetime.utcnow(),
        telegram_chat_id=student.telegram_chat_id if student and channel == 'telegram' else None,
    )
    _record_comm_log(db, log, context={'channel': channel, 'student_id': student.id if student else None})


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


def delete_due_telegram_messages(db: Session) -> dict:
    now = datetime.utcnow()
    rows = (
        db.query(CommunicationLog)
        .filter(
            CommunicationLog.channel == 'telegram',
            CommunicationLog.delete_at.is_not(None),
            CommunicationLog.delete_at <= now,
            CommunicationLog.telegram_message_id.is_not(None),
            CommunicationLog.status.not_in(['deleted', 'delete_failed']),
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
