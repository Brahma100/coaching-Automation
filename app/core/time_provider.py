from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import settings


APP_TIMEZONE = settings.app_timezone or "Asia/Kolkata"
APP_ZONEINFO = ZoneInfo(APP_TIMEZONE)


class TimeProvider:
    def now(self) -> datetime:
        return datetime.now(APP_ZONEINFO)

    def today(self) -> date:
        return self.now().date()

    def local_now(self, tz: str) -> datetime:
        return datetime.now(ZoneInfo(tz))


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("Naive datetime not allowed in business logic")
    return dt


default_time_provider = TimeProvider()
