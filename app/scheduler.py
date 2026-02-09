from datetime import date, datetime
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AllowedUser, AllowedUserStatus, AuthUser, Batch, BatchSchedule, Role, Student
from app.services.action_token_service import create_action_token
from app.services.attendance_auto_close_job import auto_close_attendance_sessions
from app.services.comms_service import queue_notification, send_daily_brief, send_telegram_message
from app.services.class_session_resolver import resolve_or_create_class_session
from app.services.daily_teacher_brief_service import build_daily_teacher_brief, format_daily_teacher_brief, resolve_teacher_chat_id
from app.services.fee_service import trigger_fee_reminders
from app.services.google_sheets_backup import backup_daily_to_google_sheet
from app.services.student_risk_service import recompute_all_student_risk


scheduler = BackgroundScheduler(timezone=settings.app_timezone)
logger = logging.getLogger(__name__)


def _with_db(task):
    db: Session = SessionLocal()
    try:
        task(db)
    finally:
        db.close()


def pre_class_notifications_job():
    def _job(db: Session):
        today = date.today()
        batches = db.query(Batch).all()
        for batch in batches:
            students = db.query(Student).filter(Student.batch_id == batch.id).all()
            for s in students:
                msg = f"Reminder: Your class for {batch.name} is today ({today}) at {batch.start_time}."
                queue_notification(db, s, 'telegram', msg)

    _with_db(_job)


def fee_reminders_job():
    _with_db(lambda db: trigger_fee_reminders(db))


def daily_brief_job():
    def _job(db: Session):
        today = datetime.now().strftime('%d %b %Y')
        students = db.query(Student).all()
        for s in students:
            send_daily_brief(db, s, f"Daily Brief ({today}): revise yesterday topics and complete homework.")

    _with_db(_job)


def google_backup_job():
    _with_db(lambda db: backup_daily_to_google_sheet(db))


def student_risk_recompute_job():
    _with_db(lambda db: recompute_all_student_risk(db))


def auto_close_attendance_sessions_job():
    _with_db(lambda db: auto_close_attendance_sessions(db))


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

    _with_db(_job)


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
                token = create_action_token(
                    db=db,
                    action_type='attendance-session',
                    payload={
                        'session_id': session_id,
                        'batch_id': batch.id,
                        'schedule_id': schedule.id,
                        'teacher_id': teacher_id,
                        'source': 'telegram',
                        'date': today.isoformat(),
                    },
                    ttl_minutes=720,
                )
                url = f"{settings.app_base_url}/ui/attendance/session/{session_id}?token={token['token']}"
                lines.append(f"- {batch.name} at {schedule.start_time}: {url}")

            send_telegram_message(chat_id, '\n'.join(lines))

    _with_db(_job)


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
    scheduler.add_job(teacher_attendance_links_job, 'cron', hour=6, minute=45, id='teacher_attendance_links')
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
