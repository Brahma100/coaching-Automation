from __future__ import annotations

import asyncio
from datetime import datetime

from communication.core.provider_registry import ProviderRegistry
from communication.core.rate_limiter import QuietHoursPolicy, RateLimiter
from communication.core.retry_engine import RetryEngine
from communication.core.state_store import InMemoryStore
from communication.models import MessageStatus
from communication.security.crypto import TokenCrypto


class DeliveryWorker:
    def __init__(
        self,
        store: InMemoryStore,
        providers: ProviderRegistry,
        retry_engine: RetryEngine,
        rate_limiter: RateLimiter,
        quiet_hours: QuietHoursPolicy,
        token_crypto: TokenCrypto,
    ) -> None:
        self.store = store
        self.providers = providers
        self.retry_engine = retry_engine
        self.rate_limiter = rate_limiter
        self.quiet_hours = quiet_hours
        self.token_crypto = token_crypto
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run(self) -> None:
        while self._running:
            await self._tick()
            await asyncio.sleep(0.5)

    async def _tick(self) -> None:
        now = datetime.utcnow()
        for item in list(self.store.queue.values()):
            if item.status not in {MessageStatus.pending, MessageStatus.retrying}:
                continue
            if item.next_attempt_at > now:
                continue

            quiet = self.store.quiet_hours.get(item.tenant_id)
            if quiet and not item.critical and self.quiet_hours.is_quiet(quiet):
                item.next_attempt_at = self.retry_engine.next_attempt(item.retry_count)
                continue

            if not self.rate_limiter.allow():
                break

            await self.store.write_log(item.id, item.tenant_id, item.active_provider, MessageStatus.sending, {})
            item.status = MessageStatus.sending
            item.updated_at = datetime.utcnow()

            success = await self._deliver(item)
            if success:
                item.status = MessageStatus.delivered
                await self.store.write_log(item.id, item.tenant_id, item.active_provider, MessageStatus.delivered, {"ok": True})
            else:
                await self._handle_failure(item)
            item.updated_at = datetime.utcnow()

    async def _deliver(self, item) -> bool:
        provider_name = item.active_provider
        if not provider_name:
            return False

        provider = self.providers.get(provider_name)
        provider_cfg = self._provider_config(item.tenant_id, provider_name)
        if not provider_cfg:
            return False

        secrets = {k: self.token_crypto.decrypt(v) for k, v in provider_cfg.encrypted_secrets.items()}
        response = await provider.send_message(secrets, item.recipient_id, item.content)
        await self.store.add_audit(
            action="send_message",
            actor="delivery_worker",
            details={"queue_id": item.id, "provider": provider_name, "response": response},
        )
        return bool(response.get("ok"))

    async def _handle_failure(self, item) -> None:
        current = item.active_provider
        await self.store.write_log(item.id, item.tenant_id, current, MessageStatus.failed, {"reason": "provider send failed"})

        has_fallback = item.current_provider_index + 1 < len(item.preferred_providers)
        if has_fallback:
            item.current_provider_index += 1
            item.status = MessageStatus.retrying
            item.next_attempt_at = datetime.utcnow()
            await self.store.write_log(
                item.id,
                item.tenant_id,
                item.active_provider,
                MessageStatus.retrying,
                {"reason": "fallback provider"},
            )
            return

        if self.retry_engine.should_retry(item.retry_count):
            item.retry_count += 1
            item.current_provider_index = 0
            item.status = MessageStatus.retrying
            item.next_attempt_at = self.retry_engine.next_attempt(item.retry_count)
            await self.store.write_log(
                item.id,
                item.tenant_id,
                item.active_provider,
                MessageStatus.retrying,
                {"retry_count": item.retry_count},
            )
            return

        item.status = MessageStatus.failed

    def _provider_config(self, tenant_id: str, provider_name: str):
        for cfg in self.store.provider_configs.values():
            if cfg.tenant_id == tenant_id and cfg.provider.value == provider_name and cfg.enabled:
                return cfg
        return None
