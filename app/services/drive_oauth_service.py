from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime
from urllib.parse import urlencode

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.config import settings
from app.core.time_provider import default_time_provider
from app.models import DriveOAuthToken


GOOGLE_AUTH_BASE = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'


class DriveOAuthError(RuntimeError):
    pass


class DriveNotConnectedError(DriveOAuthError):
    pass


def _scope_list() -> list[str]:
    raw = (settings.google_drive_oauth_scopes or '').strip()
    if not raw:
        return ['https://www.googleapis.com/auth/drive.file']
    parts = [chunk.strip() for chunk in raw.replace(',', ' ').split() if chunk.strip()]
    return parts or ['https://www.googleapis.com/auth/drive.file']


def _state_secret() -> bytes:
    return hashlib.sha256((settings.auth_secret or 'change-me').encode('utf-8')).digest()


def _state_encode(payload: dict) -> str:
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    sig = hmac.new(_state_secret(), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + sig).decode('ascii')


def _state_decode(value: str) -> dict | None:
    try:
        raw = base64.urlsafe_b64decode(value.encode('ascii'))
    except Exception:
        return None
    if len(raw) <= 32:
        return None
    body = raw[:-32]
    sig = raw[-32:]
    expected = hmac.new(_state_secret(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(body.decode('utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def decode_oauth_state(state: str) -> dict | None:
    """Decode and validate the OAuth state parameter."""
    return _state_decode(state)


def build_oauth_start_url(admin_user_id: int) -> str:
    if not settings.google_oauth_client_id or not settings.google_oauth_redirect_uri:
        raise DriveOAuthError('Google OAuth is not configured')

    state = _state_encode(
        {
            'uid': int(admin_user_id),
            'nonce': secrets.token_hex(8),
            'ts': int(default_time_provider.now().timestamp()),
        }
    )
    query = {
        'client_id': settings.google_oauth_client_id,
        'redirect_uri': settings.google_oauth_redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(_scope_list()),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
    }
    return f'{GOOGLE_AUTH_BASE}?{urlencode(query)}'


def exchange_code_for_refresh_token(code: str) -> tuple[str | None, str | None]:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret or not settings.google_oauth_redirect_uri:
        raise DriveOAuthError('Google OAuth is not configured')

    payload = {
        'code': code,
        'client_id': settings.google_oauth_client_id,
        'client_secret': settings.google_oauth_client_secret,
        'redirect_uri': settings.google_oauth_redirect_uri,
        'grant_type': 'authorization_code',
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(GOOGLE_TOKEN_URL, data=payload)
    if response.status_code >= 300:
        raise DriveOAuthError(f'Code exchange failed: {response.text[:200]}')

    body = response.json()
    return body.get('refresh_token'), body.get('access_token')


def _encrypt_refresh_token(value: str) -> str:
    plain = (value or '').encode('utf-8')
    if not plain:
        raise DriveOAuthError('Missing refresh token value')
    nonce = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac('sha256', _state_secret(), nonce, 120000, dklen=len(plain))
    cipher = bytes(a ^ b for a, b in zip(plain, key))
    return base64.urlsafe_b64encode(nonce + cipher).decode('ascii')


def _decrypt_refresh_token(value: str) -> str:
    try:
        raw = base64.urlsafe_b64decode((value or '').encode('ascii'))
    except Exception as exc:
        raise DriveOAuthError('Invalid stored refresh token') from exc
    if len(raw) < 17:
        raise DriveOAuthError('Invalid stored refresh token')
    nonce = raw[:16]
    cipher = raw[16:]
    key = hashlib.pbkdf2_hmac('sha256', _state_secret(), nonce, 120000, dklen=len(cipher))
    plain = bytes(a ^ b for a, b in zip(cipher, key))
    return plain.decode('utf-8')


def store_refresh_token(db: Session, *, user_id: int, refresh_token: str) -> DriveOAuthToken:
    encrypted = _encrypt_refresh_token(refresh_token)
    row = db.query(DriveOAuthToken).filter(DriveOAuthToken.user_id == int(user_id)).first()
    if not row:
        row = DriveOAuthToken(user_id=int(user_id), refresh_token=encrypted)
        db.add(row)
    else:
        row.refresh_token = encrypted
    db.commit()
    db.refresh(row)
    return row


def resolve_refresh_token(db: Session, *, user_id: int | None = None) -> tuple[int, str]:
    row = None
    if user_id is not None:
        row = db.query(DriveOAuthToken).filter(DriveOAuthToken.user_id == int(user_id)).first()
    if not row:
        row = db.query(DriveOAuthToken).order_by(DriveOAuthToken.updated_at.desc(), DriveOAuthToken.id.desc()).first()
    if not row:
        raise DriveNotConnectedError('Drive not connected. Admin must connect Drive first.')
    return row.user_id, _decrypt_refresh_token(row.refresh_token)


def get_drive_credentials(db: Session, user_id: int | None = None) -> Credentials:
    owner_user_id, refresh_token = resolve_refresh_token(db, user_id=user_id)
    _ = owner_user_id
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GOOGLE_TOKEN_URL,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=_scope_list(),
    )
    credentials.refresh(Request())
    return credentials


def drive_connected(db: Session) -> bool:
    return db.query(DriveOAuthToken.id).first() is not None


def validate_oauth_state(state: str, expected_user_id: int) -> bool:
    payload = _state_decode(state)
    if not payload:
        return False
    return int(payload.get('uid') or 0) == int(expected_user_id)
