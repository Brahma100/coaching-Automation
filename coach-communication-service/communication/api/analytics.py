from __future__ import annotations

from fastapi import APIRouter

from communication.app_state import get_context

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def summary():
    ctx = get_context()
    return {
        "sent": ctx.store.metrics["sent"],
        "delivered": ctx.store.metrics["delivered"],
        "failed": ctx.store.metrics["failed"],
        "retry_count": ctx.store.metrics["retry_count"],
    }


@router.get("/provider-comparison")
async def provider_comparison(tenant_id: str):
    ctx = get_context()
    out: dict[str, dict[str, int]] = {}
    for log in ctx.store.logs.values():
        if log.tenant_id != tenant_id:
            continue
        bucket = out.setdefault(log.provider, {"delivered": 0, "failed": 0})
        if log.status.value == "delivered":
            bucket["delivered"] += 1
        if log.status.value == "failed":
            bucket["failed"] += 1
    return out
