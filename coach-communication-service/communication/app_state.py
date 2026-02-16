from __future__ import annotations

from dataclasses import dataclass

from communication.core import (
    EventBus,
    InMemoryStore,
    MessageDispatcher,
    ProviderRegistry,
    QuietHoursPolicy,
    RateLimiter,
    RetryEngine,
    TemplateEngine,
)
from communication.providers import TelegramProvider, WhatsAppProvider
from communication.security.crypto import TokenCrypto
from communication.workers.delivery_worker import DeliveryWorker


@dataclass
class AppContext:
    store: InMemoryStore
    event_bus: EventBus
    dispatcher: MessageDispatcher
    registry: ProviderRegistry
    template_engine: TemplateEngine
    retry_engine: RetryEngine
    rate_limiter: RateLimiter
    quiet_hours: QuietHoursPolicy
    worker: DeliveryWorker
    crypto: TokenCrypto


_ctx: AppContext | None = None


def build_context() -> AppContext:
    store = InMemoryStore()
    event_bus = EventBus()
    template_engine = TemplateEngine()
    dispatcher = MessageDispatcher(store, template_engine)
    registry = ProviderRegistry()
    registry.register(TelegramProvider())
    registry.register(WhatsAppProvider())
    retry_engine = RetryEngine()
    limiter = RateLimiter(per_second=20)
    quiet_hours = QuietHoursPolicy(timezone="UTC")
    crypto = TokenCrypto()
    worker = DeliveryWorker(store, registry, retry_engine, limiter, quiet_hours, crypto)
    return AppContext(
        store=store,
        event_bus=event_bus,
        dispatcher=dispatcher,
        registry=registry,
        template_engine=template_engine,
        retry_engine=retry_engine,
        rate_limiter=limiter,
        quiet_hours=quiet_hours,
        worker=worker,
        crypto=crypto,
    )


def set_context(ctx: AppContext) -> None:
    global _ctx
    _ctx = ctx


def get_context() -> AppContext:
    if _ctx is None:
        set_context(build_context())
    return _ctx
