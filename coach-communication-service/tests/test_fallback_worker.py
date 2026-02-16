import asyncio

from communication.core import InMemoryStore, ProviderRegistry, QuietHoursPolicy, RateLimiter, RetryEngine
from communication.models import MessageQueueItem, MessageStatus, ProviderConfig, ProviderType
from communication.security.crypto import TokenCrypto
from communication.workers.delivery_worker import DeliveryWorker


class FailingProvider:
    name = "telegram"

    async def send_message(self, config, recipient_id, content):
        return {"ok": False}

    async def validate_config(self, config):
        return True, "ok"

    async def health_check(self, config):
        return True, "ok"


class SuccessProvider:
    name = "whatsapp"

    async def send_message(self, config, recipient_id, content):
        return {"ok": True}

    async def validate_config(self, config):
        return True, "ok"

    async def health_check(self, config):
        return True, "ok"


def test_fallback_to_second_provider():
    asyncio.run(_run())


async def _run():
    store = InMemoryStore()
    crypto = TokenCrypto("test-secret")
    registry = ProviderRegistry()
    registry.register(FailingProvider())
    registry.register(SuccessProvider())

    await store.upsert_provider(
        ProviderConfig(
            id=store.new_id(),
            tenant_id="t1",
            provider=ProviderType.telegram,
            name="tg",
            encrypted_secrets={"bot_token": crypto.encrypt("x")},
        )
    )
    await store.upsert_provider(
        ProviderConfig(
            id=store.new_id(),
            tenant_id="t1",
            provider=ProviderType.whatsapp,
            name="wa",
            encrypted_secrets={"access_token": crypto.encrypt("y"), "phone_number_id": crypto.encrypt("1")},
        )
    )

    item = MessageQueueItem(
        id=store.new_id(),
        tenant_id="t1",
        event="attendance.submitted",
        recipient_id="123",
        preferred_providers=["telegram", "whatsapp"],
        content="hello",
        payload={},
    )
    await store.add_queue_item(item)

    worker = DeliveryWorker(store, registry, RetryEngine(), RateLimiter(per_second=10), QuietHoursPolicy(), crypto)
    await worker._tick()
    await worker._tick()

    assert store.queue[item.id].status == MessageStatus.delivered
