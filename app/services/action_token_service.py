import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.services.center_scope_service import get_current_center_id
from app.models import ActionToken


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def load_token_row(db: Session, token: str) -> ActionToken | None:
    token_hash = _hash_token(token)
    row = db.query(ActionToken).filter(ActionToken.token_hash == token_hash).first()
    if not row:
        return None
    if not hmac.compare_digest(token_hash, row.token_hash):
        return None
    return row


def create_action_token(
    db: Session,
    action_type: str,
    payload: dict,
    ttl_minutes: int = 30,
    expected_role: str | None = None,
    center_id: int | None = None,
    issued_ip: str | None = None,
    issued_user_agent: str | None = None,
    *,
    time_provider: TimeProvider = default_time_provider,
):
    payload = dict(payload or {})
    clean_role = str(expected_role or payload.get('expected_role') or payload.get('role') or 'teacher').strip().lower()
    if clean_role not in ('teacher', 'admin', 'student'):
        clean_role = 'teacher'
    payload.setdefault('expected_role', clean_role)
    clean_center_id = int(center_id or payload.get('center_id') or get_current_center_id() or 1)
    if clean_center_id <= 0:
        clean_center_id = 1
    payload.setdefault('center_id', clean_center_id)

    raw = secrets.token_urlsafe(24)
    token_hash = _hash_token(raw)
    row = ActionToken(
        token_hash=token_hash,
        action_type=action_type,
        expected_role=clean_role,
        center_id=clean_center_id,
        payload_json=json.dumps(payload),
        expires_at=time_provider.now().replace(tzinfo=None) + timedelta(minutes=ttl_minutes),
        consumed=False,
        consumed_at=None,
        issued_ip=str(issued_ip or ''),
        issued_user_agent=str(issued_user_agent or ''),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'token': raw, 'expires_at': row.expires_at.isoformat(), 'action_type': action_type}


def verify_and_consume_token(
    db: Session,
    token: str,
    expected_action_type: str,
    *,
    time_provider: TimeProvider = default_time_provider,
):
    row = load_token_row(db, token)
    if not row:
        raise ValueError('Invalid token')
    if row.consumed:
        raise ValueError('Token already consumed')
    if row.action_type != expected_action_type:
        raise ValueError('Token action mismatch')
    if row.expires_at < time_provider.now().replace(tzinfo=None):
        raise ValueError('Token expired')

    payload = json.loads(row.payload_json or '{}')
    consume_token(db, token)
    return payload


def verify_token(
    db: Session,
    token: str,
    expected_action_type: str,
    request_role: str | None = None,
    request_center_id: int | None = None,
    request_ip: str | None = None,
    request_user_agent: str | None = None,
    *,
    time_provider: TimeProvider = default_time_provider,
):
    row = load_token_row(db, token)
    if not row:
        raise ValueError('Invalid token')
    if row.consumed:
        raise ValueError('Token already consumed')
    if row.action_type != expected_action_type:
        raise ValueError('Token action mismatch')
    if row.expires_at < time_provider.now().replace(tzinfo=None):
        raise ValueError('Token expired')
    payload = json.loads(row.payload_json or '{}')

    clean_request_role = str(request_role or '').strip().lower()
    if clean_request_role and clean_request_role != str(row.expected_role or '').strip().lower():
        raise ValueError('Token role mismatch')
    context_center_id = int(get_current_center_id() or 0)
    clean_request_center_id = int(request_center_id or context_center_id or 0)
    if clean_request_center_id > 0 and int(row.center_id or 0) != clean_request_center_id:
        raise ValueError('Token center mismatch')
    if request_ip and row.issued_ip and request_ip != row.issued_ip:
        import logging
        logging.getLogger(__name__).warning('token_replay_signal ip_mismatch')
    if request_user_agent and row.issued_user_agent and request_user_agent != row.issued_user_agent:
        import logging
        logging.getLogger(__name__).warning('token_replay_signal ua_mismatch')
    return payload


def consume_token(
    db: Session,
    token: str,
    *,
    time_provider: TimeProvider = default_time_provider,
) -> None:
    row = load_token_row(db, token)
    if not row:
        raise ValueError('Invalid token')
    if row.consumed:
        raise ValueError('Token already consumed')
    row.consumed = True
    row.consumed_at = time_provider.now().replace(tzinfo=None)
    db.commit()
