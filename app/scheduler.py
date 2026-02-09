from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Batch, Student
from app.services.comms_service import queue_notification, send_daily_brief
from app.services.fee_service import trigger_fee_reminders
from app.services.google_sheets_backup import backup_daily_to_google_sheet


scheduler = BackgroundScheduler(timezone=settings.app_timezone)


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


def start_scheduler():
    scheduler.add_job(pre_class_notifications_job, 'cron', hour=6, minute=30, id='pre_class_notifications')
    scheduler.add_job(fee_reminders_job, 'cron', hour=9, minute=0, id='fee_reminders')
    scheduler.add_job(daily_brief_job, 'cron', hour=20, minute=0, id='daily_briefs')
    scheduler.add_job(google_backup_job, 'cron', hour=23, minute=30, id='google_backup')

    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
