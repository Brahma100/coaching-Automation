from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import CommunicationLog


def is_duplicate_send(
    db: Session,
    *,
    event_type: str,
    entity_id: int,
    receiver_id: str,
    window_seconds: int = 300,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    if not event_type or int(entity_id or 0) <= 0 or not str(receiver_id or '').strip():
        return False
    cutoff = time_provider.now().replace(tzinfo=None) - timedelta(seconds=max(1, int(window_seconds or 300)))
    row = (
        db.query(CommunicationLog.id)
        .filter(
            CommunicationLog.event_type == str(event_type),
            CommunicationLog.telegram_chat_id == str(receiver_id).strip(),
            CommunicationLog.created_at >= cutoff,
            or_(
                CommunicationLog.delivery_status.in_(['sent', 'duplicate_suppressed']),
                CommunicationLog.status == 'sent',
            ),
            or_(
                CommunicationLog.reference_id == int(entity_id),
                CommunicationLog.session_id == int(entity_id),
                CommunicationLog.student_id == int(entity_id),
                CommunicationLog.teacher_id == int(entity_id),
            ),
        )
        .first()
    )
    return row is not None
