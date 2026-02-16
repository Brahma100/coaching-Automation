from __future__ import annotations

from communication.providers.base import BaseProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, provider_name: str) -> BaseProvider:
        if provider_name not in self._providers:
            raise KeyError(f"Provider '{provider_name}' is not registered")
        return self._providers[provider_name]

    def list(self) -> list[str]:
        return sorted(self._providers)
