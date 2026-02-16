from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.inbox_automation import send_inbox_escalations


def execute() -> None:
    run_job('inbox_escalation', lambda db, center_id: send_inbox_escalations(db, center_id=int(center_id or 0)))
