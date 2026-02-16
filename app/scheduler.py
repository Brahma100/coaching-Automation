import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.core.time_provider import TimeProvider, default_time_provider
from app.domain.jobs import (
    auto_close_attendance_sessions as auto_close_attendance_sessions_domain_job,
    daily_brief as daily_brief_domain_job,
    daily_teacher_brief as daily_teacher_brief_domain_job,
    delete_due_telegram_messages as delete_due_telegram_messages_domain_job,
    fee_reminders as fee_reminders_domain_job,
    google_backup as google_backup_domain_job,
    inbox_escalation as inbox_escalation_domain_job,
    pre_class_notifications as pre_class_notifications_domain_job,
    snapshot_rebuild as snapshot_rebuild_domain_job,
    student_daily_digest as student_daily_digest_domain_job,
    student_homework_reminder as student_homework_reminder_domain_job,
    student_risk_recompute as student_risk_recompute_domain_job,
    student_weekly_motivation as student_weekly_motivation_domain_job,
    teacher_attendance_links as teacher_attendance_links_domain_job,
    teacher_timed_alerts as teacher_timed_alerts_domain_job,
    telegram_link_polling as telegram_link_polling_domain_job,
)
from app.services.telegram_linking_service import should_poll_telegram_updates


scheduler = BackgroundScheduler(timezone=settings.app_timezone)
logger = logging.getLogger(__name__)


def pre_class_notifications_job(*, time_provider: TimeProvider = default_time_provider):
    pre_class_notifications_domain_job.execute(time_provider=time_provider)


def fee_reminders_job():
    fee_reminders_domain_job.execute()


def daily_brief_job(*, time_provider: TimeProvider = default_time_provider):
    daily_brief_domain_job.execute(time_provider=time_provider)


def google_backup_job():
    google_backup_domain_job.execute()


def student_risk_recompute_job():
    student_risk_recompute_domain_job.execute()


def snapshot_rebuild_job():
    snapshot_rebuild_domain_job.execute()


def auto_close_attendance_sessions_job():
    auto_close_attendance_sessions_domain_job.execute()


def delete_due_telegram_messages_job():
    delete_due_telegram_messages_domain_job.execute()


def inbox_escalation_job():
    inbox_escalation_domain_job.execute()


def student_homework_reminder_job():
    student_homework_reminder_domain_job.execute()


def student_daily_digest_job():
    student_daily_digest_domain_job.execute()


def student_weekly_motivation_job():
    student_weekly_motivation_domain_job.execute()


def telegram_link_polling_job():
    telegram_link_polling_domain_job.execute()


def daily_teacher_brief_job(*, time_provider: TimeProvider = default_time_provider):
    daily_teacher_brief_domain_job.execute(time_provider=time_provider)


def teacher_attendance_links_job(*, time_provider: TimeProvider = default_time_provider):
    teacher_attendance_links_domain_job.execute(time_provider=time_provider)


def teacher_timed_alerts_job(*, time_provider: TimeProvider = default_time_provider):
    teacher_timed_alerts_domain_job.execute(time_provider=time_provider)


def _parse_hhmm(value: str, default_hour: int = 7, default_minute: int = 30) -> tuple[int, int]:
    try:
        hour_raw, minute_raw = (value or '').split(':', 1)
        hour = int(hour_raw)
        minute = int(minute_raw)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
        return hour, minute
    except Exception:
        return default_hour, default_minute


def start_scheduler():
    brief_hour, brief_minute = _parse_hhmm(settings.daily_teacher_brief_time)
    scheduler.add_job(pre_class_notifications_job, 'cron', hour=6, minute=30, id='pre_class_notifications')
    scheduler.add_job(teacher_timed_alerts_job, 'interval', minutes=1, id='teacher_timed_alerts')
    scheduler.add_job(delete_due_telegram_messages_job, 'interval', minutes=1, id='telegram_auto_delete')
    poll_enabled, poll_reason = should_poll_telegram_updates()
    if poll_enabled:
        interval_seconds = max(5, int(settings.telegram_link_polling_interval_seconds or 20))
        scheduler.add_job(telegram_link_polling_job, 'interval', seconds=interval_seconds, id='telegram_link_polling')
        logger.info(
            'telegram_link_polling_enabled mode=%s interval_seconds=%s reason=%s',
            settings.telegram_link_polling_mode,
            interval_seconds,
            poll_reason,
        )
    else:
        logger.info(
            'telegram_link_polling_disabled mode=%s reason=%s',
            settings.telegram_link_polling_mode,
            poll_reason,
        )
    scheduler.add_job(inbox_escalation_job, 'interval', minutes=10, id='inbox_escalation')
    scheduler.add_job(student_homework_reminder_job, 'cron', hour=20, minute=0, id='student_homework_reminders')
    scheduler.add_job(student_daily_digest_job, 'cron', hour=20, minute=30, id='student_daily_digest')
    scheduler.add_job(student_weekly_motivation_job, 'cron', day_of_week='sun', hour=19, minute=0, id='student_weekly_motivation')
    scheduler.add_job(auto_close_attendance_sessions_job, 'interval', minutes=5, id='auto_close_attendance_sessions')
    scheduler.add_job(fee_reminders_job, 'cron', hour=9, minute=0, id='fee_reminders')
    scheduler.add_job(daily_brief_job, 'cron', hour=20, minute=0, id='daily_briefs')
    scheduler.add_job(daily_teacher_brief_job, 'cron', hour=brief_hour, minute=brief_minute, id='daily_teacher_brief')
    scheduler.add_job(google_backup_job, 'cron', hour=23, minute=30, id='google_backup')
    scheduler.add_job(student_risk_recompute_job, 'cron', hour=1, minute=30, id='student_risk_recompute')
    scheduler.add_job(snapshot_rebuild_job, 'interval', minutes=15, id='snapshot_rebuild')

    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
