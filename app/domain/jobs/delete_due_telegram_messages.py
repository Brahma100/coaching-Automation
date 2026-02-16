from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.comms_service import delete_due_telegram_messages


def execute() -> None:
    run_job('telegram_auto_delete', lambda db, center_id: delete_due_telegram_messages(db, center_id=int(center_id or 0)))
