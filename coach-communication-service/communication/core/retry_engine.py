from __future__ import annotations

from datetime import datetime, timedelta


class RetryEngine:
    def __init__(self, base_seconds: int = 2, max_retries: int = 4) -> None:
        self.base_seconds = base_seconds
        self.max_retries = max_retries

    def next_attempt(self, retry_count: int) -> datetime:
        delay = self.base_seconds * (2 ** retry_count)
        return datetime.utcnow() + timedelta(seconds=delay)

    def should_retry(self, retry_count: int) -> bool:
        return retry_count < self.max_retries
