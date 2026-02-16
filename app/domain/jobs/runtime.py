from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.domain.jobs.job_lock import acquire_job_lock, release_job_lock
from app.metrics import run_timed_job
from app.models import Center
from app.services.observability_counters import record_observability_event
from app.services.center_scope_service import center_context


logger = logging.getLogger(__name__)


def with_db(task, *, job_label: str) -> None:
    db: Session = SessionLocal()
    try:
        center_rows = db.query(Center.id).order_by(Center.id.asc()).all()
        center_ids = [int(center_id) for (center_id,) in center_rows if int(center_id or 0) > 0] or [1]
        for center_id in center_ids:
            lock_token = acquire_job_lock(job_label, center_id)
            if not lock_token:
                logger.info('job_lock_skipped_concurrent job=%s center_id=%s', job_label, center_id)
                record_observability_event(f'job_lock_skipped:{job_label}:{center_id}')
                continue
            logger.info('job_lock_acquired job=%s center_id=%s', job_label, center_id)
            with center_context(center_id):
                try:
                    task(db, center_id)
                    record_observability_event(f'job_success_count:{job_label}:{center_id}')
                except Exception:
                    db.rollback()
                    logger.exception('job_center_failure center_id=%s job=%s', center_id, job_label)
                    record_observability_event(f'job_failure_count:{job_label}:{center_id}')
                finally:
                    release_job_lock(job_label, center_id, lock_token)
    finally:
        db.close()


def run_job(label: str, task) -> None:
    run_timed_job(label, lambda: with_db(task, job_label=label))
