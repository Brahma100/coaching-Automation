from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import AutomationFailureLog
from app.services.center_scope_service import get_current_center_id


logger = logging.getLogger(__name__)


def log_automation_failure(
    db: Session,
    *,
    job_name: str,
    entity_type: str,
    entity_id: int | None,
    error_message: str,
    center_id: int | None = None,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    effective_center_id = int(center_id or get_current_center_id() or 1)
    row = AutomationFailureLog(
        center_id=effective_center_id,
        job_name=str(job_name or 'unknown'),
        entity_type=str(entity_type or ''),
        entity_id=int(entity_id) if entity_id is not None else None,
        error_message=str(error_message or ''),
        created_at=time_provider.now().replace(tzinfo=None),
    )
    try:
        db.add(row)
        db.flush()
    except Exception:
        db.rollback()
        logger.error(
            'automation_failure_log_write_failed',
            extra={
                'job': job_name,
                'center_id': effective_center_id,
                'entity_type': entity_type,
                'entity_id': entity_id,
            },
        )
