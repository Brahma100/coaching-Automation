from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.domain.jobs.runtime import run_job
from app.models import Student
from app.services.comms_service import send_daily_brief


def execute(*, time_provider: TimeProvider = default_time_provider) -> None:
    def _job(db: Session, center_id: int):
        today = time_provider.now().strftime('%d %b %Y')
        students = db.query(Student).filter(Student.center_id == center_id).all()
        for s in students:
            send_daily_brief(db, s, f"Daily Brief ({today}): revise yesterday topics and complete homework.")

    run_job('daily_briefs', _job)

