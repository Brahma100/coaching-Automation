import hashlib
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ActionToken


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_action_token(db: Session, action_type: str, payload: dict, ttl_minutes: int = 30):
    raw = secrets.token_urlsafe(24)
    token_hash = _hash_token(raw)
    row = ActionToken(
        token_hash=token_hash,
        action_type=action_type,
        payload_json=json.dumps(payload or {}),
        expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        consumed=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'token': raw, 'expires_at': row.expires_at.isoformat(), 'action_type': action_type}


def verify_and_consume_token(db: Session, token: str, expected_action_type: str):
    token_hash = _hash_token(token)
    row = db.query(ActionToken).filter(ActionToken.token_hash == token_hash).first()
    if not row:
        raise ValueError('Invalid token')
    if row.consumed:
        raise ValueError('Token already consumed')
    if row.action_type != expected_action_type:
        raise ValueError('Token action mismatch')
    if row.expires_at < datetime.utcnow():
        raise ValueError('Token expired')

    row.consumed = True
    db.commit()
    return json.loads(row.payload_json or '{}')


def verify_token(db: Session, token: str, expected_action_type: str):
    token_hash = _hash_token(token)
    row = db.query(ActionToken).filter(ActionToken.token_hash == token_hash).first()
    if not row:
        raise ValueError('Invalid token')
    if row.consumed:
        raise ValueError('Token already consumed')
    if row.action_type != expected_action_type:
        raise ValueError('Token action mismatch')
    if row.expires_at < datetime.utcnow():
        raise ValueError('Token expired')
    return json.loads(row.payload_json or '{}')
