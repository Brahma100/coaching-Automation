from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading

from app.core.time_provider import default_time_provider


_LOCK = threading.Lock()
_EVENTS: dict[str, deque[datetime]] = defaultdict(deque)


def record_observability_event(name: str, *, at: datetime | None = None) -> None:
    event = str(name or '').strip().lower()
    if not event:
        return
    now = at or default_time_provider.now().replace(tzinfo=None)
    with _LOCK:
        bucket = _EVENTS[event]
        bucket.append(now)
        cutoff = now - timedelta(hours=25)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()


def count_observability_events(name: str, *, window_hours: int = 24, now: datetime | None = None) -> int:
    event = str(name or '').strip().lower()
    if not event:
        return 0
    current = now or default_time_provider.now().replace(tzinfo=None)
    cutoff = current - timedelta(hours=max(1, int(window_hours or 24)))
    with _LOCK:
        bucket = _EVENTS.get(event) or deque()
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return len(bucket)


def clear_observability_events() -> None:
    with _LOCK:
        _EVENTS.clear()
