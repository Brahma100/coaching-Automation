from __future__ import annotations

from datetime import datetime


def get_utcnow() -> datetime:
    # Wrapped to allow deterministic overrides in tests/CI.
    return datetime.utcnow()
