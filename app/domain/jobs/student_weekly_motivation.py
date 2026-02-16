from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.student_automation_engine import send_weekly_motivation


def execute() -> None:
    run_job('student_weekly_motivation', lambda db, center_id: send_weekly_motivation(db, center_id=int(center_id or 0)))
