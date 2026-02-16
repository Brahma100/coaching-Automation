from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.time_provider import TimeProvider, default_time_provider
from app.models import RateLimitState
from app.services.observability_counters import record_observability_event


logger = logging.getLogger(__name__)


class SafeRateLimitError(ValueError):
    pass


def check_rate_limit(
    db: Session,
    *,
    center_id: int,
    scope_type: str,
    scope_key: str,
    action_name: str,
    max_requests: int,
    window_seconds: int,
    time_provider: TimeProvider = default_time_provider,
) -> bool:
    scoped_center_id = int(center_id or 1)
    normalized_scope_type = str(scope_type or 'user').strip().lower() or 'user'
    normalized_scope_key = str(scope_key or '').strip() or 'unknown'
    normalized_action_name = str(action_name or '').strip() or 'unknown_action'
    max_allowed = max(1, int(max_requests or 1))
    window = max(1, int(window_seconds or 60))
    now = time_provider.now().replace(tzinfo=None)

    row = (
        db.query(RateLimitState)
        .filter(
            RateLimitState.center_id == scoped_center_id,
            RateLimitState.scope_type == normalized_scope_type,
            RateLimitState.scope_key == normalized_scope_key,
            RateLimitState.action_name == normalized_action_name,
        )
        .with_for_update()
        .first()
    )

    if row is None:
        row = RateLimitState(
            center_id=scoped_center_id,
            scope_type=normalized_scope_type,
            scope_key=normalized_scope_key,
            action_name=normalized_action_name,
            window_start=now,
            request_count=1,
        )
        db.add(row)
        db.flush()
        return True

    if (now - row.window_start).total_seconds() >= window:
        row.window_start = now
        row.request_count = 1
        db.flush()
        return True

    if int(row.request_count or 0) >= max_allowed:
        record_observability_event('rate_limit_block')
        logger.warning(
            'rate_limit_blocked',
            extra={
                'center_id': scoped_center_id,
                'scope_type': normalized_scope_type,
                'scope_key': normalized_scope_key,
                'action_name': normalized_action_name,
                'max_requests': max_allowed,
                'window_seconds': window,
            },
        )
        retry_after = max(
            1,
            int((row.window_start + timedelta(seconds=window) - now).total_seconds()),
        )
        raise SafeRateLimitError(f'Rate limit exceeded. Retry in {retry_after} seconds.')

    row.request_count = int(row.request_count or 0) + 1
    db.flush()
    return True
