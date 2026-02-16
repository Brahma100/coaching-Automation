from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.google_sheets_backup import backup_daily_to_google_sheet


def execute() -> None:
    run_job('google_backup', lambda db, center_id: backup_daily_to_google_sheet(db, center_id=int(center_id or 0)))
