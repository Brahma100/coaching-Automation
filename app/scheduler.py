from datetime import date, datetime, timedelta
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AllowedUser, AllowedUserStatus, AuthUser, Batch, BatchSchedule, Role, Student
from app.services.action_token_service import create_action_token
from app.services.attendance_auto_close_job import auto_close_attendance_sessions
from app.services.comms_service import delete_due_telegram_messages, queue_notification, send_daily_brief, send_telegram_message
from app.services.class_session_resolver import resolve_or_create_class_session
from app.services.daily_teacher_brief_service import build_daily_teacher_brief, format_daily_teacher_brief, resolve_teacher_chat_id
from app.services.fee_service import trigger_fee_reminders
from app.services.google_sheets_backup import backup_daily_to_google_sheet
from app.services.inbox_automation import send_inbox_escalations
from app.services.student_automation_engine import send_daily_digest, send_homework_due_tomorrow, send_weekly_motivation
from app.services.student_risk_service import recompute_all_student_risk
from app.services.teacher_notification_service import send_class_start_reminder
from app.frontend_routes import attendance_session_url
from app.metrics import run_timed_job


scheduler = BackgroundScheduler(timezone=settings.app_timezone)
logger = logging.getLogger(__name__)


def _with_db(task):
    db: Session = SessionLocal()
    try:
        task(db)
    finally:
        db.close()


def _run_job(label: str, task) -> None:
    run_timed_job(label, lambda: _with_db(task))


def pre_class_notifications_job():
    def _job(db: Session):
        today = date.today()
        batches = db.query(Batch).all()
        for batch in batches:
            students = db.query(Student).filter(Student.batch_id == batch.id).all()
            for s in students:
                msg = f"Reminder: Your class for {batch.name} is today ({today}) at {batch.start_time}."
                queue_notification(db, s, 'telegram', msg)

    _run_job('pre_class_notifications', _job)


def fee_reminders_job():
    _run_job('fee_reminders', lambda db: trigger_fee_reminders(db))


def daily_brief_job():
    def _job(db: Session):
        today = datetime.now().strftime('%d %b %Y')
        students = db.query(Student).all()
        for s in students:
            send_daily_brief(db, s, f"Daily Brief ({today}): revise yesterday topics and complete homework.")

    _run_job('daily_briefs', _job)


def google_backup_job():
    _run_job('google_backup', lambda db: backup_daily_to_google_sheet(db))


def student_risk_recompute_job():
    _run_job('student_risk_recompute', lambda db: recompute_all_student_risk(db))


def auto_close_attendance_sessions_job():
    _run_job('auto_close_attendance_sessions', lambda db: auto_close_attendance_sessions(db))


def delete_due_telegram_messages_job():
    _run_job('telegram_auto_delete', lambda db: delete_due_telegram_messages(db))


def inbox_escalation_job():
    _run_job('inbox_escalation', lambda db: send_inbox_escalations(db))


def student_homework_reminder_job():
    _run_job('student_homework_reminders', lambda db: send_homework_due_tomorrow(db))


def student_daily_digest_job():
    _run_job('student_daily_digest', lambda db: send_daily_digest(db))


def student_weekly_motivation_job():
    _run_job('student_weekly_motivation', lambda db: send_weekly_motivation(db))


def daily_teacher_brief_job():
    def _job(db: Session):
        today = date.today()
        teachers = (
            db.query(AllowedUser)
            .filter(
                AllowedUser.role == Role.TEACHER.value,
                AllowedUser.status == AllowedUserStatus.ACTIVE.value,
            )
            .all()
        )
        for teacher in teachers:
            chat_id = resolve_teacher_chat_id(db, teacher.phone)
            if not chat_id:
                logger.warning('daily_teacher_brief_skipped_missing_chat_id phone=%s', teacher.phone)
                continue

            auth_user = db.query(AuthUser).filter(AuthUser.phone == teacher.phone).first()
            teacher_id = auth_user.id if auth_user else 0
            summary = build_daily_teacher_brief(db, teacher_id=teacher_id, day=today)
            message = format_daily_teacher_brief(summary, teacher_phone=teacher.phone)
            ok = send_telegram_message(chat_id, message)
            if not ok:
                logger.warning('daily_teacher_brief_send_failed phone=%s', teacher.phone)

    _run_job('daily_teacher_brief', _job)


def teacher_attendance_links_job():
    def _job(db: Session):
        today = date.today()
        weekday = today.weekday()
        schedules = (
            db.query(BatchSchedule, Batch)
            .join(Batch, Batch.id == BatchSchedule.batch_id)
            .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True))
            .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
            .all()
        )
        if not schedules:
            return

        resolved_sessions: dict[int, int] = {}
        for schedule, batch in schedules:
            session, _ = resolve_or_create_class_session(
                db=db,
                batch_id=batch.id,
                schedule_id=schedule.id,
                target_date=today,
                source='telegram',
                teacher_id=0,
            )
            resolved_sessions[schedule.id] = session.id

        teachers = (
            db.query(AllowedUser)
            .filter(
                AllowedUser.role == Role.TEACHER.value,
                AllowedUser.status == AllowedUserStatus.ACTIVE.value,
            )
            .all()
        )
        for teacher in teachers:
            chat_id = resolve_teacher_chat_id(db, teacher.phone)
            if not chat_id:
                continue
            auth_user = db.query(AuthUser).filter(AuthUser.phone == teacher.phone).first()
            teacher_id = auth_user.id if auth_user else 0

            lines = ['Attendance links for today:']
            for schedule, batch in schedules:
                session_id = resolved_sessions.get(schedule.id)
                if not session_id:
                    continue
                end_time = session.scheduled_start + timedelta(minutes=session.duration_minutes or 60)
                ttl_minutes = int(max(1, (end_time + timedelta(minutes=10) - datetime.utcnow()).total_seconds() // 60))
                token = create_action_token(
                    db=db,
                    action_type='attendance_open',
                    payload={
                        'session_id': session_id,
                        'batch_id': batch.id,
                        'schedule_id': schedule.id,
                        'teacher_id': teacher_id,
                        'role': 'teacher',
                    },
                    ttl_minutes=ttl_minutes,
                )
                url = attendance_session_url(session_id, token['token'])
                lines.append(f"- {batch.name} at {schedule.start_time}: {url}")

            send_telegram_message(chat_id, '\n'.join(lines))

    _run_job('teacher_attendance_links', _job)


def teacher_timed_alerts_job():
    def _job(db: Session):
        now = datetime.now()
        today = date.today()
        weekday = today.weekday()
        schedules = (
            db.query(BatchSchedule, Batch)
            .join(Batch, Batch.id == BatchSchedule.batch_id)
            .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True))
            .order_by(BatchSchedule.start_time.asc(), BatchSchedule.id.asc())
            .all()
        )
        if not schedules:
            return

        for schedule, batch in schedules:
            session, _ = resolve_or_create_class_session(
                db=db,
                batch_id=batch.id,
                schedule_id=schedule.id,
                target_date=today,
                source='system',
                teacher_id=0,
            )
            start_time = datetime.combine(today, datetime.strptime(schedule.start_time, '%H:%M').time())
            window_start = start_time - timedelta(minutes=15)
            window_end = start_time + timedelta(minutes=5)
            if window_start <= now < window_end:
                send_class_start_reminder(db, session, schedule_id=schedule.id)

    _run_job('teacher_timed_alerts', _job)


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

    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
