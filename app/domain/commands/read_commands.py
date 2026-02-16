from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.frontend_routes import attendance_session_url, session_summary_url
from app.models import ActionToken
from app.services.action_token_service import create_action_token
from app.services.inbox_automation import resolve_review_action_on_open
from app.services.notes_service import create_download_log
from app.services import snapshot_service

logger = logging.getLogger(__name__)


def generate_dashboard_tokens(
    db: Session,
    *,
    action_type: str,
    payload: dict[str, Any],
    ttl_minutes: int,
) -> dict[str, Any]:
    token = create_action_token(
        db=db,
        action_type=action_type,
        payload=payload,
        ttl_minutes=ttl_minutes,
    )['token']
    if action_type == 'attendance_open':
        return {'token': token, 'url': attendance_session_url(int(payload.get('session_id') or 0), token)}
    if action_type in ('session_summary', 'notification_summary'):
        return {'token': token, 'url': session_summary_url(int(payload.get('session_id') or 0), token)}
    return {'token': token, 'url': None}


def generate_session_student_action_tokens(
    db: Session,
    *,
    student_id: int,
    parent_id: int | None,
    fee_record_id: int | None,
    pending_action_id: int | None,
) -> dict[str, str]:
    notify_token = create_action_token(
        db,
        action_type='notify-parent',
        payload={'student_id': student_id, 'parent_id': parent_id, 'pending_action_id': pending_action_id},
        ttl_minutes=60,
    )['token']
    fee_token = create_action_token(
        db,
        action_type='send-fee-reminder',
        payload={'student_id': student_id, 'fee_record_id': fee_record_id, 'pending_action_id': pending_action_id},
        ttl_minutes=60,
    )['token']
    return {
        'notify_parent_url': f'/actions/notify-parent?token={notify_token}',
        'fee_reminder_url': f'/actions/send-fee-reminder?token={fee_token}',
    }


def ensure_session_actions(db: Session, *, teacher_id: int, session_id: int) -> None:
    resolve_review_action_on_open(db, teacher_id=teacher_id, session_id=session_id)


def prepare_notification_side_effects(db: Session, *, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    logger.warning('prepare_notification_side_effects_invoked mode=%s', mode)
    if mode == 'session_student_actions':
        return generate_session_student_action_tokens(
            db,
            student_id=int(payload.get('student_id') or 0),
            parent_id=payload.get('parent_id'),
            fee_record_id=payload.get('fee_record_id'),
            pending_action_id=payload.get('pending_action_id'),
        )
    raise ValueError(f'Unsupported mode: {mode}')


def persist_teacher_today_snapshot(db: Session, *, teacher_id: int, day: date, payload: dict[str, Any]) -> None:
    snapshot_service.upsert_teacher_today_snapshot(db, teacher_id=teacher_id, day=day, payload=payload)


def persist_admin_ops_snapshot(db: Session, *, day: date, payload: dict[str, Any]) -> None:
    snapshot_service.upsert_admin_ops_snapshot(db, day=day, payload=payload)


def persist_student_dashboard_snapshot(db: Session, *, student_id: int, day: date, payload: dict[str, Any]) -> None:
    snapshot_service.upsert_student_dashboard_snapshot(db, student_id=student_id, day=day, payload=payload)


def mark_expired_token_consumed(db: Session, token_row: ActionToken | None) -> None:
    if not token_row:
        return
    token_row.consumed = True
    db.commit()


def record_note_download_event(
    db: Session,
    *,
    note_id: int,
    student_id: int | None,
    batch_id: int | None,
    ip_address: str,
    user_agent: str,
) -> None:
    create_download_log(
        db,
        note_id=note_id,
        student_id=student_id,
        batch_id=batch_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
