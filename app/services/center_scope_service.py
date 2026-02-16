from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from app.models import Center


_current_center_id: ContextVar[int | None] = ContextVar('current_center_id', default=None)


def set_current_center_id(center_id: int | None) -> Token:
    clean = int(center_id or 0)
    return _current_center_id.set(clean if clean > 0 else None)


def reset_current_center_id(token: Token) -> None:
    _current_center_id.reset(token)


def get_current_center_id() -> int | None:
    value = _current_center_id.get()
    clean = int(value or 0)
    return clean if clean > 0 else None


@contextmanager
def center_context(center_id: int | None):
    token = set_current_center_id(center_id)
    try:
        yield
    finally:
        reset_current_center_id(token)


def get_or_create_default_center_id(db: Session) -> int:
    row = db.query(Center).filter(Center.slug == 'default-center').first()
    if row:
        return int(row.id)
    row = db.query(Center).order_by(Center.id.asc()).first()
    if row:
        return int(row.id)
    row = Center(name='default-center', slug='default-center', timezone='Asia/Kolkata')
    db.add(row)
    db.commit()
    db.refresh(row)
    return int(row.id)


def get_actor_center_id(user: dict | None) -> int | None:
    request_center_id = get_current_center_id()
    if int(request_center_id or 0) > 0:
        return int(request_center_id)
    if not user:
        return 1
    explicit = int(user.get('center_id') or 0)
    if explicit > 0:
        return explicit
    return 1


def apply_center_scope(query: Query, user: dict | None):
    db = query.session
    if db is None:
        return query

    entity = None
    if query.column_descriptions:
        entity = query.column_descriptions[0].get('entity')
    if entity is None:
        return query
    if not hasattr(entity, 'center_id'):
        return query

    center_id = get_actor_center_id(user)
    if int(center_id or 0) <= 0:
        return query.filter(false())
    return query.filter(entity.center_id == int(center_id))
