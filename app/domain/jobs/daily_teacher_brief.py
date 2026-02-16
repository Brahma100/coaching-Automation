from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.domain.jobs.runtime import run_job
from app.models import AllowedUser, AllowedUserStatus, AuthUser, Role
from app.services.comms_service import queue_teacher_telegram
from app.services.daily_teacher_brief_service import build_daily_teacher_brief, format_daily_teacher_brief, resolve_teacher_chat_id


logger = logging.getLogger(__name__)


def execute(*, time_provider: TimeProvider = default_time_provider) -> None:
    def _job(db: Session, center_id: int):
        today = time_provider.today()
        teachers = (
            db.query(AllowedUser)
            .filter(
                AllowedUser.role == Role.TEACHER.value,
                AllowedUser.status == AllowedUserStatus.ACTIVE.value,
            )
            .all()
        )
        for teacher in teachers:
            chat_id = resolve_teacher_chat_id(db, teacher.phone)
            if not chat_id:
                logger.warning('daily_teacher_brief_skipped_missing_chat_id phone=%s', teacher.phone)
                continue

            auth_user = db.query(AuthUser).filter(AuthUser.phone == teacher.phone, AuthUser.center_id == center_id).first()
            if not auth_user or int(auth_user.center_id or 0) != center_id:
                continue
            teacher_id = auth_user.id if auth_user else 0
            summary = build_daily_teacher_brief(db, teacher_id=teacher_id, day=today, time_provider=time_provider)
            message = format_daily_teacher_brief(summary, teacher_phone=teacher.phone)
            result = queue_teacher_telegram(
                db,
                teacher_id=int(teacher_id),
                chat_id=chat_id,
                message=message,
                critical=True,
                notification_type='daily_teacher_brief',
                session_id=None,
            )
            if not bool(result.get('ok')):
                logger.warning('daily_teacher_brief_send_failed phone=%s', teacher.phone)

    run_job('daily_teacher_brief', _job)
