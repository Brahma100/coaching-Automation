from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.services.attendance_service import submit_attendance as submit_attendance_legacy
from app.services.attendance_session_service import submit_attendance_for_session


class SafePermissionError(PermissionError):
    pass


def submit_attendance(
    db: Session,
    *,
    session_id: int | None = None,
    batch_id: int | None = None,
    attendance_date: date | None = None,
    records: list[dict],
    subject: str = 'General',
    teacher_id: int = 0,
    scheduled_start=None,
    topic_planned: str = '',
    topic_completed: str = '',
    actor_role: str | None,
    actor_user_id: int = 0,
    allow_edit_submitted: bool = False,
    time_provider: TimeProvider = default_time_provider,
) -> dict:
    if actor_role is None:
        raise ValueError('actor_role is required')
    normalized_role = str(actor_role).strip().lower()
    if normalized_role not in ('admin', 'teacher'):
        raise SafePermissionError('Invalid actor_role for attendance submit')
    if session_id is not None:
        return submit_attendance_for_session(
            db=db,
            session_id=session_id,
            records=records,
            actor_role=normalized_role,
            teacher_id=teacher_id,
            allow_edit_submitted=allow_edit_submitted,
            time_provider=time_provider,
        )
    return submit_attendance_legacy(
        db=db,
        batch_id=int(batch_id or 0),
        attendance_date=attendance_date,
        records=records,
        subject=subject,
        teacher_id=teacher_id,
        scheduled_start=scheduled_start,
        topic_planned=topic_planned,
        topic_completed=topic_completed,
        class_session_id=None,
        actor_role=normalized_role,
        actor_user_id=actor_user_id,
    )
