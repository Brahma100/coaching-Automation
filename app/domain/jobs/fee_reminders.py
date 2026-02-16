from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.fee_service import trigger_fee_reminders


def execute() -> None:
    run_job('fee_reminders', lambda db, center_id: trigger_fee_reminders(db, center_id=int(center_id or 0)))
