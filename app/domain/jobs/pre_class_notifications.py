from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import Batch, Student
from app.services.comms_service import queue_notification
from app.domain.jobs.runtime import run_job


def execute(*, time_provider: TimeProvider = default_time_provider) -> None:
    def _job(db: Session, center_id: int):
        today = time_provider.today()
        batches = db.query(Batch).filter(Batch.center_id == center_id).all()
        for batch in batches:
            students = db.query(Student).filter(Student.batch_id == batch.id, Student.center_id == center_id).all()
            for s in students:
                msg = f"Reminder: Your class for {batch.name} is today ({today}) at {batch.start_time}."
                queue_notification(db, s, 'telegram', msg)

    run_job('pre_class_notifications', _job)

