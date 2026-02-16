from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from communication.app_state import get_context
from communication.models import MessageQueueItem

router = APIRouter(prefix="/messages", tags=["messages"])


class EventRequest(BaseModel):
    event: str
    tenant_id: str
    user_id: str
    payload: dict[str, object] = Field(default_factory=dict)


class BroadcastRequest(BaseModel):
    tenant_id: str
    event: str = "manual.broadcast"
    recipients: list[str]
    payload: dict[str, object] = Field(default_factory=dict)


@router.post("/events")
async def emit_event(payload: EventRequest):
    ctx = get_context()
    await ctx.event_bus.emit(
        payload.event,
        {
            "tenant_id": payload.tenant_id,
            "event": payload.event,
            "user_id": payload.user_id,
            "payload": payload.payload,
        },
    )
    return {"queued": True}


@router.post("/broadcast")
async def broadcast(payload: BroadcastRequest):
    ctx = get_context()
    await ctx.event_bus.emit(
        payload.event,
        {
            "tenant_id": payload.tenant_id,
            "event": payload.event,
            "user_id": "system",
            "payload": {**payload.payload, "recipients": payload.recipients},
        },
    )
    return {"queued": True, "recipient_count": len(payload.recipients)}


@router.get("/queue", response_model=list[MessageQueueItem])
async def queue(tenant_id: str):
    ctx = get_context()
    return [q for q in ctx.store.queue.values() if q.tenant_id == tenant_id]


@router.get("/logs")
async def logs(tenant_id: str):
    ctx = get_context()
    return [log for log in ctx.store.logs.values() if log.tenant_id == tenant_id]
