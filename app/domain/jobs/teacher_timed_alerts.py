from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.domain.jobs.runtime import run_job
from app.models import Batch, BatchSchedule
from app.services.class_session_resolver import resolve_or_create_class_session
from app.services.teacher_notification_service import send_class_start_reminder


def execute(*, time_provider: TimeProvider = default_time_provider) -> None:
    def _job(db: Session, center_id: int):
        now = time_provider.now().replace(tzinfo=None)
        today = time_provider.today()
        weekday = today.weekday()
        schedules = (
            db.query(BatchSchedule, Batch)
            .join(Batch, Batch.id == BatchSchedule.batch_id)
            .filter(BatchSchedule.weekday == weekday, Batch.active.is_(True), Batch.center_id == center_id)
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

    run_job('teacher_timed_alerts', _job)

