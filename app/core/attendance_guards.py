from __future__ import annotations

from datetime import date

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.models import Batch, BatchSchedule, CalendarOverride, Role
from app.services.auth_service import validate_session_token


def extract_session_token(request: Request) -> str | None:
    cookie_token = request.cookies.get('auth_session')
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get('Authorization', '')
    if auth_header.lower().startswith('bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return None


def require_teacher_or_admin(request: Request, *, strict: bool = True) -> dict:
    auth_user = validate_session_token(extract_session_token(request))
    if not auth_user:
        if strict:
            raise HTTPException(status_code=403, detail='Unauthorized')
        return {}
    role = (auth_user.get('role') or '').lower()
    if role not in (Role.TEACHER.value, Role.ADMIN.value):
        if strict:
            raise HTTPException(status_code=403, detail='Unauthorized')
        return {}
    return auth_user


def available_batches_for_date(db: Session, target_date: date) -> list[Batch]:
    target_weekday = int(target_date.weekday())
    active_batches = db.query(Batch).filter(Batch.active.is_(True)).order_by(Batch.name.asc()).all()
    if not active_batches:
        return []

    batch_ids = [int(row.id) for row in active_batches]
    scheduled_batch_ids = {
        int(batch_id)
        for (batch_id,) in (
            db.query(BatchSchedule.batch_id)
            .filter(
                BatchSchedule.batch_id.in_(batch_ids),
                BatchSchedule.weekday == target_weekday,
            )
            .distinct()
            .all()
        )
    }
    override_rows = (
        db.query(CalendarOverride)
        .filter(
            CalendarOverride.batch_id.in_(batch_ids),
            CalendarOverride.override_date == target_date,
        )
        .order_by(CalendarOverride.id.asc())
        .all()
    )
    latest_override_by_batch: dict[int, CalendarOverride] = {}
    for row in override_rows:
        latest_override_by_batch[int(row.batch_id)] = row

    available_ids: set[int] = set()
    for row in active_batches:
        batch_id = int(row.id)
        override = latest_override_by_batch.get(batch_id)
        if override and bool(override.cancelled):
            continue
        if override and str(override.new_start_time or '').strip():
            available_ids.add(batch_id)
            continue
        if batch_id in scheduled_batch_ids:
            available_ids.add(batch_id)

    return [row for row in active_batches if int(row.id) in available_ids]
