from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.domain.jobs.runtime import run_job
from app.services.telegram_linking_service import poll_telegram_updates_for_linking


logger = logging.getLogger(__name__)


def execute() -> None:
    def _job(db: Session, center_id: int):
        outcome = poll_telegram_updates_for_linking(db, center_id=int(center_id or 0))
        if not outcome.get('ok'):
            logger.debug('telegram_link_polling_skipped reason=%s', outcome.get('reason'))
            return
        if int(outcome.get('processed') or 0) > 0:
            logger.info(
                'telegram_link_polling_processed processed=%s linked=%s',
                outcome.get('processed'),
                outcome.get('linked'),
            )

    run_job('telegram_link_polling', _job)
