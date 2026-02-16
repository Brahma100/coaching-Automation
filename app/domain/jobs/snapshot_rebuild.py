from __future__ import annotations

from app.domain.jobs.runtime import run_job
from app.services.snapshot_rebuild_service import rebuild_snapshots_for_center


def execute() -> None:
    run_job('snapshot_rebuild', lambda db, center_id: rebuild_snapshots_for_center(db, center_id=int(center_id or 0)))
