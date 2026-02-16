from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from communication.api.auth import require_admin_role
from communication.app_state import get_context
from communication.models import NotificationRule, NotificationRuleUpsert

router = APIRouter(prefix="/rules", tags=["rules"])


class QuietHoursRequest(BaseModel):
    tenant_id: str
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=23)


@router.get("", response_model=list[NotificationRule])
async def list_rules(tenant_id: str):
    ctx = get_context()
    return [rule for rule in ctx.store.rules.values() if rule.tenant_id == tenant_id]


@router.post("", response_model=NotificationRule, dependencies=[Depends(require_admin_role)])
async def upsert_rule(payload: NotificationRuleUpsert):
    ctx = get_context()
    rule = NotificationRule(id=ctx.store.new_id(), **payload.model_dump())
    await ctx.store.upsert_rule(rule)
    await ctx.store.add_audit("rule.upsert", "api", {"tenant_id": payload.tenant_id, "rule_id": rule.id})
    return rule


@router.put("/quiet-hours", dependencies=[Depends(require_admin_role)])
async def set_quiet_hours(payload: QuietHoursRequest):
    ctx = get_context()
    ctx.store.quiet_hours[payload.tenant_id] = (payload.start_hour, payload.end_hour)
    await ctx.store.add_audit(
        "quiet_hours.set",
        "api",
        {"tenant_id": payload.tenant_id, "start_hour": payload.start_hour, "end_hour": payload.end_hour},
    )
    return {"tenant_id": payload.tenant_id, "quiet_hours": [payload.start_hour, payload.end_hour]}


@router.get("/quiet-hours")
async def get_quiet_hours(tenant_id: str):
    ctx = get_context()
    quiet_hours = ctx.store.quiet_hours.get(tenant_id, (22, 7))
    return {"tenant_id": tenant_id, "quiet_hours": [quiet_hours[0], quiet_hours[1]]}
