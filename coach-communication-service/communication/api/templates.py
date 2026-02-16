from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends

from communication.api.auth import require_admin_role
from communication.app_state import get_context
from communication.models import MessageTemplate, MessageTemplateUpsert

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplatePreviewRequest(BaseModel):
    body: str
    provider: str
    sample: dict[str, object]


@router.get("", response_model=list[MessageTemplate])
async def list_templates(tenant_id: str):
    ctx = get_context()
    return [t for t in ctx.store.templates.values() if t.tenant_id == tenant_id]


@router.post("", response_model=MessageTemplate, dependencies=[Depends(require_admin_role)])
async def upsert_template(payload: MessageTemplateUpsert):
    ctx = get_context()
    template = MessageTemplate(id=ctx.store.new_id(), **payload.model_dump())
    await ctx.store.upsert_template(template)
    await ctx.store.add_audit("template.upsert", "api", {"tenant_id": payload.tenant_id, "template_id": template.id})
    return template


@router.post("/preview")
async def preview_template(payload: TemplatePreviewRequest):
    ctx = get_context()
    rendered = ctx.template_engine.preview(payload.body, payload.sample, payload.provider)
    return {"preview": rendered}
