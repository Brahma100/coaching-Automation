from __future__ import annotations

from app.config import settings


def _base() -> str:
    return settings.frontend_base_url.rstrip('/')


def attendance_session_url(session_id: int, token: str) -> str:
    return f"{_base()}/attendance/session/{session_id}?token={token}"


def attendance_review_url(session_id: int, token: str) -> str:
    return f"{_base()}/attendance/review/{session_id}?token={token}"


def class_start_url(session_id: int, token: str) -> str:
    return f"{_base()}/class/start/{session_id}?token={token}"


def session_summary_url(session_id: int, token: str) -> str:
    return f"{_base()}/session/summary/{session_id}?token={token}"
