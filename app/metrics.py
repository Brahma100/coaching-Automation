from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.config import settings


logger = logging.getLogger('app.metrics')


class MetricsExporter:
    def export_cache_minute(self, *, minute_start: datetime, counts: dict[str, int]) -> None:
        raise NotImplementedError


class LogMetricsExporter(MetricsExporter):
    def export_cache_minute(self, *, minute_start: datetime, counts: dict[str, int]) -> None:
        logger.info(
            'cache_metrics minute=%s cache_hit=%s cache_miss=%s cache_bypass=%s cache_invalidate=%s',
            minute_start.isoformat(),
            counts.get('cache_hit', 0),
            counts.get('cache_miss', 0),
            counts.get('cache_bypass', 0),
            counts.get('cache_invalidate', 0),
        )


_exporter: MetricsExporter = LogMetricsExporter()


def set_metrics_exporter(exporter: MetricsExporter) -> None:
    global _exporter
    _exporter = exporter


class _MinuteCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._minute_start_epoch: int | None = None
        self._counts: dict[str, int] = {}

    def _minute_epoch(self, ts: float) -> int:
        return int(ts // 60) * 60

    def _flush_locked(self, minute_epoch: int) -> None:
        if not self._counts:
            return
        minute_start = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=minute_epoch)
        try:
            _exporter.export_cache_minute(minute_start=minute_start, counts=dict(self._counts))
        except Exception:
            logger.exception('metrics_export_failed minute=%s', minute_start.isoformat())
        self._counts.clear()

    def record(self, key: str) -> None:
        now = time.time()
        minute_epoch = self._minute_epoch(now)
        with self._lock:
            if self._minute_start_epoch is None:
                self._minute_start_epoch = minute_epoch
            if minute_epoch != self._minute_start_epoch:
                self._flush_locked(self._minute_start_epoch)
                self._minute_start_epoch = minute_epoch
            self._counts[key] = self._counts.get(key, 0) + 1

    def flush(self) -> None:
        with self._lock:
            if self._minute_start_epoch is None:
                return
            self._flush_locked(self._minute_start_epoch)


_cache_counter = _MinuteCounter()


def record_cache_event(event: str) -> None:
    _cache_counter.record(event)


def flush_cache_metrics() -> None:
    _cache_counter.flush()


def _timed(
    *,
    label: str,
    threshold_ms: int | None = None,
    log_label: str = 'timed',
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        threshold_value = threshold_ms if threshold_ms is not None else settings.metrics_slow_ms

        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args: object, **kwargs: object):
                started = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration_ms = (time.perf_counter() - started) * 1000.0
                    if duration_ms >= threshold_value:
                        logger.info(
                            'service_timer label=%s duration_ms=%.2f event=%s',
                            label,
                            duration_ms,
                            log_label,
                        )

            return async_wrapper  # type: ignore[return-value]

        def sync_wrapper(*args: object, **kwargs: object):
            started = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - started) * 1000.0
                if duration_ms >= threshold_value:
                    logger.info(
                        'service_timer label=%s duration_ms=%.2f event=%s',
                        label,
                        duration_ms,
                        log_label,
                    )

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def timed_service(label: str, *, threshold_ms: int | None = None) -> Callable[[Callable[..., object]], Callable[..., object]]:
    return _timed(label=label, threshold_ms=threshold_ms, log_label='service')


def timed_snapshot(label: str, *, threshold_ms: int | None = None) -> Callable[[Callable[..., object]], Callable[..., object]]:
    return _timed(label=label, threshold_ms=threshold_ms, log_label='snapshot')


def run_timed_job(label: str, fn: Callable[[], object]) -> object:
    start = time.perf_counter()
    logger.info('job_start name=%s', label)
    status = 'ok'
    try:
        return fn()
    except Exception:
        status = 'failed'
        duration_ms = (time.perf_counter() - start) * 1000.0
        logger.exception('job_failed name=%s duration_ms=%.2f', label, duration_ms)
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        logger.info('job_end name=%s status=%s duration_ms=%.2f', label, status, duration_ms)
