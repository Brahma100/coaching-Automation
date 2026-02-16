from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.attendance_auto_close_job import auto_close_attendance_sessions


def execute() -> None:
    run_job('auto_close_attendance_sessions', lambda db, center_id: auto_close_attendance_sessions(db, center_id=int(center_id or 0)))
