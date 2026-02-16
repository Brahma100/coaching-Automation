from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from communication.api.auth import require_admin_role
from communication.app_state import get_context
from communication.models import ProviderConfig, ProviderConfigUpsert, ProviderHealth

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderConfig])
async def list_providers(tenant_id: str):
    ctx = get_context()
    return [c for c in ctx.store.provider_configs.values() if c.tenant_id == tenant_id]


@router.post("", response_model=ProviderConfig, dependencies=[Depends(require_admin_role)])
async def upsert_provider(payload: ProviderConfigUpsert):
    ctx = get_context()
    provider = ctx.registry.get(payload.provider.value)
    valid, details = await provider.validate_config(payload.secrets)
    if not valid:
        raise HTTPException(status_code=400, detail=details)

    item = ProviderConfig(
        id=ctx.store.new_id(),
        tenant_id=payload.tenant_id,
        provider=payload.provider,
        name=payload.name,
        enabled=payload.enabled,
        encrypted_secrets={k: ctx.crypto.encrypt(v) for k, v in payload.secrets.items()},
        metadata=payload.metadata,
    )
    await ctx.store.upsert_provider(item)
    await ctx.store.add_audit("provider.upsert", "api", {"provider": item.provider.value, "tenant_id": item.tenant_id})
    return item


@router.get("/health", response_model=ProviderHealth)
async def provider_health(tenant_id: str, provider: str):
    ctx = get_context()
    config = next(
        (c for c in ctx.store.provider_configs.values() if c.tenant_id == tenant_id and c.provider.value == provider),
        None,
    )
    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found")
    adapter = ctx.registry.get(provider)
    secrets = {k: ctx.crypto.decrypt(v) for k, v in config.encrypted_secrets.items()}
    healthy, details = await adapter.health_check(secrets)
    return ProviderHealth(provider=config.provider, healthy=healthy, details=details)
