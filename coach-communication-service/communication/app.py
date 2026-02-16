from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from communication.api import router as api_router
from communication.app_state import build_context, set_context


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = build_context()
    set_context(ctx)

    async def handler(data: dict[str, object]) -> None:
        await ctx.dispatcher.dispatch_event(
            tenant_id=str(data["tenant_id"]),
            event=str(data["event"]),
            user_id=str(data["user_id"]),
            payload=dict(data["payload"]),
        )

    await ctx.event_bus.subscribe("*", handler)
    await ctx.worker.start()
    yield
    await ctx.worker.stop()


app = FastAPI(title="coach-communication-service", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
