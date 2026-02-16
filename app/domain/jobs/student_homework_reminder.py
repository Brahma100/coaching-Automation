from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.student_automation_engine import send_homework_due_tomorrow


def execute() -> None:
    run_job('student_homework_reminders', lambda db, center_id: send_homework_due_tomorrow(db, center_id=int(center_id or 0)))
