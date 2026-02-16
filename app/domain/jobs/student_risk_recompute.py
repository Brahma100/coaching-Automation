from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.student_risk_service import recompute_all_student_risk


def execute() -> None:
    run_job('student_risk_recompute', lambda db, center_id: recompute_all_student_risk(db, center_id=int(center_id or 0)))
