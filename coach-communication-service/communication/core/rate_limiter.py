from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


class QuietHoursPolicy:
    def __init__(self, timezone: str = "UTC") -> None:
        self.timezone = timezone

    def is_quiet(self, quiet_range: tuple[int, int], now: datetime | None = None) -> bool:
        now = now or datetime.now(ZoneInfo(self.timezone))
        start, end = quiet_range
        hour = now.hour
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end


class RateLimiter:
    def __init__(self, per_second: int = 15) -> None:
        self.per_second = per_second
        self._tokens = per_second
        self._last_reset = datetime.utcnow()

    def allow(self) -> bool:
        now = datetime.utcnow()
        if (now - self._last_reset).total_seconds() >= 1:
            self._tokens = self.per_second
            self._last_reset = now
        if self._tokens <= 0:
            return False
        self._tokens -= 1
        return True
