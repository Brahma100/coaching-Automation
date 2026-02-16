from __future__ import annotations

import logging
import threading
import uuid

from app.cache import cache, cache_key


logger = logging.getLogger(__name__)
_lock = threading.RLock()
_KEY_PREFIX = 'job_lock'


def _lock_key(job_label: str, center_id: int) -> str:
    return cache_key(_KEY_PREFIX, f'{job_label}:{int(center_id or 0)}')


def acquire_job_lock(job_label: str, center_id: int, *, ttl_seconds: int = 900) -> str | None:
    key = _lock_key(job_label, center_id)
    token = uuid.uuid4().hex
    backend = cache.backend

    # Redis path (atomic SET NX EX).
    client = getattr(backend, '_client', None)
    if client is not None:
        try:
            ok = client.set(key, token, nx=True, ex=max(1, int(ttl_seconds)))
            return token if ok else None
        except Exception:
            logger.exception('job_lock_redis_acquire_failed', extra={'key': key})
            return None

    # In-memory/backend-agnostic path.
    with _lock:
        existing = backend.get(key)
        if existing is not None:
            return None
        backend.set(key, token, max(1, int(ttl_seconds)))
        return token


def release_job_lock(job_label: str, center_id: int, token: str) -> None:
    key = _lock_key(job_label, center_id)
    if not token:
        return
    backend = cache.backend
    client = getattr(backend, '_client', None)

    if client is not None:
        try:
            current = client.get(key)
            if current is None:
                return
            if str(current) == str(token):
                client.delete(key)
            return
        except Exception:
            logger.exception('job_lock_redis_release_failed', extra={'key': key})
            return

    with _lock:
        current = backend.get(key)
        if current is None:
            return
        if str(current) == str(token):
            backend.delete(key)

