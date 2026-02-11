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
from app.metrics import record_cache_event


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.utcnow()


def cache_key(prefix: str, identifier: str | int | None = None) -> str:
    if identifier is None or identifier == '':
        return prefix
    return f"{prefix}:{identifier}"


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
        value = self.backend.get(key)
        if value is not None:
            record_cache_event('cache_hit')
            logger.debug('cache hit: %s', key)
        else:
            record_cache_event('cache_miss')
            logger.debug('cache miss: %s', key)
        return value

    def set_cached(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl_value = ttl if ttl is not None else settings.default_cache_ttl
        self.backend.set(key, value, ttl_value)
        logger.debug('cache set: %s ttl=%s', key, ttl_value)

    def invalidate(self, key: str) -> None:
        self.backend.delete(key)
        record_cache_event('cache_invalidate')
        logger.debug('cache invalidate: %s', key)

    def invalidate_prefix(self, prefix: str) -> None:
        self.backend.delete_prefix(prefix)
        record_cache_event('cache_invalidate')
        logger.debug('cache invalidate prefix: %s', prefix)


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
