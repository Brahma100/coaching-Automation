from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import inspect
import typing
from typing import Any, Callable

from app.config import settings
from app.core.time_provider import default_time_provider
from app.metrics import record_cache_event
from app.services.observability_counters import record_observability_event


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return default_time_provider.now().replace(tzinfo=None)


def cache_key(prefix: str, identifier: str | int | None = None) -> str:
    if identifier is None or identifier == '':
        return prefix
    return f"{prefix}:{identifier}"


def _current_center_id() -> int | None:
    try:
        from app.services.center_scope_service import get_current_center_id

        return get_current_center_id()
    except Exception:
        return None


def _extract_center_from_key(key: str) -> int | None:
    text = str(key or '').strip()
    if not text.startswith('center:'):
        return None
    parts = text.split(':', 2)
    if len(parts) < 3:
        return None
    try:
        return int(parts[1])
    except Exception:
        return None


def _strip_center_prefix(key: str) -> str:
    text = str(key or '')
    if not text.startswith('center:'):
        return text
    parts = text.split(':', 2)
    if len(parts) < 3:
        return text
    return parts[2]


def _effective_center_namespace() -> int:
    return int(_current_center_id() or 0)


def _scope_cache_key(key: str) -> str:
    center_id = _effective_center_namespace()
    requested_center = _extract_center_from_key(key)
    if requested_center is not None:
        if center_id > 0 and requested_center != center_id:
            logger.error(
                'cache_center_mismatch_detected',
                extra={
                    'op': 'scope_key',
                    'current_center_id': center_id,
                    'requested_center_id': requested_center,
                    'key': str(key),
                },
            )
            record_observability_event('cache_center_mismatch')
            return f"center:{center_id}:{_strip_center_prefix(key)}"
        return str(key)
    return f"center:{center_id}:{key}"


def _scope_cache_prefix(prefix: str) -> str:
    center_id = _effective_center_namespace()
    requested_center = _extract_center_from_key(prefix)
    if requested_center is not None:
        if center_id > 0 and requested_center != center_id:
            logger.error(
                'cache_center_mismatch_detected',
                extra={
                    'op': 'scope_prefix',
                    'current_center_id': center_id,
                    'requested_center_id': requested_center,
                    'prefix': str(prefix),
                },
            )
            record_observability_event('cache_center_mismatch')
            return f"center:{center_id}:{_strip_center_prefix(prefix)}"
        return str(prefix)
    return f"center:{center_id}:{prefix}"


def _extract_payload_center_id(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    raw = value.get('center_id')
    if raw is None:
        return None
    try:
        cid = int(raw)
        return cid if cid > 0 else None
    except Exception:
        return None


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ('1', 'true', 'yes', 'y', 'on')


def bypass_cache(context: Any | None = None) -> bool:
    if context is None:
        return False
    if isinstance(context, dict):
        return _normalize_bool(context.get('bypass_cache'))
    try:
        query = getattr(context, 'query_params', None)
        if query is not None:
            return _normalize_bool(query.get('bypass_cache'))
    except Exception:
        return False
    return False


class CacheBackend:
    def get(self, key: str) -> Any | None:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: int) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> None:
        raise NotImplementedError


class MemoryCacheBackend(CacheBackend):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, tuple[datetime, Any]] = {}

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if _utc_now() >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        expires_at = _utc_now() + timedelta(seconds=max(1, int(ttl)))
        with self._lock:
            self._store[key] = (expires_at, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [key for key in self._store.keys() if key.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)


class RedisCacheBackend(CacheBackend):
    def __init__(self, redis_url: str) -> None:
        import redis  # type: ignore

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set(self, key: str, value: Any, ttl: int) -> None:
        payload = json.dumps(value, default=str)
        self._client.setex(key, max(1, int(ttl)), payload)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def delete_prefix(self, prefix: str) -> None:
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break


@dataclass
class CacheManager:
    backend: CacheBackend

    def bypass_cache(self, context: Any | None = None) -> bool:
        return bypass_cache(context)

    def get_cached(self, key: str) -> Any | None:
        requested_center = _extract_center_from_key(key)
        current_center = _effective_center_namespace()
        if requested_center is not None and current_center > 0 and requested_center != current_center:
            logger.error(
                'cache_center_mismatch_detected',
                extra={
                    'op': 'get',
                    'current_center_id': current_center,
                    'requested_center_id': requested_center,
                    'key': str(key),
                },
            )
            record_observability_event('cache_center_mismatch')
            return None
        scoped_key = _scope_cache_key(key)
        value = self.backend.get(scoped_key)
        if value is not None:
            record_cache_event('cache_hit')
            logger.debug('cache hit: %s', scoped_key)
        else:
            record_cache_event('cache_miss')
            logger.debug('cache miss: %s', scoped_key)
        return value

    def set_cached(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl_value = ttl if ttl is not None else settings.default_cache_ttl
        payload_center_id = _extract_payload_center_id(value)
        current_center = _effective_center_namespace()
        if payload_center_id is not None and current_center > 0 and payload_center_id != current_center:
            logger.error(
                'cache_center_mismatch_detected',
                extra={
                    'op': 'set',
                    'current_center_id': current_center,
                    'payload_center_id': payload_center_id,
                    'key': str(key),
                },
            )
            record_observability_event('cache_center_mismatch')
            return
        scoped_key = _scope_cache_key(key)
        self.backend.set(scoped_key, value, ttl_value)
        logger.debug('cache set: %s ttl=%s', scoped_key, ttl_value)

    def invalidate(self, key: str) -> None:
        scoped_key = _scope_cache_key(key)
        self.backend.delete(scoped_key)
        record_cache_event('cache_invalidate')
        logger.debug('cache invalidate: %s', scoped_key)

    def invalidate_prefix(self, prefix: str) -> None:
        scoped_prefix = _scope_cache_prefix(prefix)
        self.backend.delete_prefix(scoped_prefix)
        record_cache_event('cache_invalidate')
        logger.debug('cache invalidate prefix: %s', scoped_prefix)


def _build_cache_backend() -> CacheBackend:
    if settings.cache_backend == 'redis' and settings.cache_redis_url:
        try:
            return RedisCacheBackend(settings.cache_redis_url)
        except Exception:
            logger.exception('redis_cache_init_failed_falling_back_to_memory')
    return MemoryCacheBackend()


cache = CacheManager(backend=_build_cache_backend())


def _extract_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    if 'request' in kwargs:
        return kwargs['request']
    for arg in args:
        if getattr(arg, 'query_params', None) is not None:
            return arg
    return None


def _resolved_signature(func: Callable[..., Any]) -> inspect.Signature:
    """
    FastAPI resolves string annotations using the callable's globals.
    Since our wrappers live in app.cache, copying a signature that contains
    string annotations (from `from __future__ import annotations`) can cause
    FastAPI to misinterpret parameters like `request` as query params.
    """

    sig = inspect.signature(func)
    try:
        hints = typing.get_type_hints(func, globalns=getattr(func, '__globals__', None))
    except Exception:
        return sig

    parameters = []
    for name, param in sig.parameters.items():
        if name in hints:
            parameters.append(param.replace(annotation=hints[name]))
        else:
            parameters.append(param)

    return_annotation = hints.get('return', sig.return_annotation)
    return sig.replace(parameters=parameters, return_annotation=return_annotation)


def cached_view(
    ttl: int | None = None,
    key_builder: Callable[..., str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if _normalize_bool(kwargs.get('bypass_cache')) or bypass_cache(_extract_request(args, kwargs)):
                    record_cache_event('cache_bypass')
                    return await func(*args, **kwargs)
                key = key_builder(*args, **kwargs) if key_builder else None
                if key:
                    cached = cache.get_cached(key)
                    if cached is not None:
                        return cached
                result = await func(*args, **kwargs)
                if key:
                    cache.set_cached(key, result, ttl)
                return result

            # Ensure FastAPI sees the original endpoint signature (not *args/**kwargs),
            # otherwise it will treat args/kwargs as required query params and 422.
            async_wrapper.__signature__ = _resolved_signature(func)  # type: ignore[attr-defined]
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if _normalize_bool(kwargs.get('bypass_cache')) or bypass_cache(_extract_request(args, kwargs)):
                record_cache_event('cache_bypass')
                return func(*args, **kwargs)
            key = key_builder(*args, **kwargs) if key_builder else None
            if key:
                cached = cache.get_cached(key)
                if cached is not None:
                    return cached
            result = func(*args, **kwargs)
            if key:
                cache.set_cached(key, result, ttl)
            return result

        sync_wrapper.__signature__ = _resolved_signature(func)  # type: ignore[attr-defined]
        return sync_wrapper

    return decorator
