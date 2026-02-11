from __future__ import annotations

from contextvars import ContextVar


current_endpoint: ContextVar[str] = ContextVar('current_endpoint', default='background')
