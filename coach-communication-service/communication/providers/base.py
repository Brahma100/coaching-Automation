from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    name: str

    @abstractmethod
    async def send_message(self, config: dict[str, Any], recipient_id: str, content: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self, config: dict[str, Any]) -> tuple[bool, str]:
        raise NotImplementedError
