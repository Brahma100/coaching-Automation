from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.student_automation_engine import send_daily_digest


def execute() -> None:
    run_job('student_daily_digest', lambda db, center_id: send_daily_digest(db, center_id=int(center_id or 0)))
