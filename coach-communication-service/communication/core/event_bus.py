from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_name: str, handler: EventHandler) -> None:
        async with self._lock:
            self._handlers.setdefault(event_name, []).append(handler)

    async def emit(self, event_name: str, data: dict[str, Any]) -> None:
        handlers = self._handlers.get(event_name, []) + self._handlers.get("*", [])
        if not handlers:
            return
        await asyncio.gather(*(handler(data) for handler in handlers))
