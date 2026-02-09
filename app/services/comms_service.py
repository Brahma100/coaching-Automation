import json
import logging
from datetime import datetime
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CommunicationLog, Student
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


def _is_duplicate_notification(db: Session, channel: str, message: str, student_id: int | None) -> bool:
    recent = db.query(CommunicationLog).filter(
        CommunicationLog.channel == channel,
        CommunicationLog.message == message,
        CommunicationLog.student_id == student_id,
    ).order_by(CommunicationLog.created_at.desc()).first()
    if not recent:
        return False
    return (datetime.utcnow() - recent.created_at).total_seconds() <= 900


def queue_telegram_by_chat_id(
    db: Session,
    chat_id: str,
    message: str,
    student_id: int | None = None,
    reply_markup: dict | None = None,
    critical: bool = False,
) -> None:
    if not critical and _should_suppress_non_critical(db, student_id=student_id):
        logger.info('notification_suppressed_quiet_hours', extra={'channel': 'telegram', 'student_id': student_id})
        return

    if _is_duplicate_notification(db, 'telegram', message, student_id):
        logger.info('duplicate_notification_suppressed', extra={'channel': 'telegram', 'student_id': student_id})
        return

    status = 'sent' if send_telegram_message(chat_id, message, reply_markup=reply_markup) else 'failed'
    try:
        log = CommunicationLog(
            student_id=student_id,
            channel='telegram',
            message=message,
            status=status,
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception('notification_log_write_failed', extra={'channel': 'telegram', 'student_id': student_id})


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

    try:
        log = CommunicationLog(
            student_id=student.id if student else None,
            channel=channel,
            message=message,
            status=status,
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception('notification_log_write_failed', extra={'channel': channel, 'student_id': student.id if student else None})


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
