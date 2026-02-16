from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"


class ProviderConfig(BaseModel):
    id: str
    tenant_id: str
    provider: ProviderType
    name: str
    enabled: bool = True
    encrypted_secrets: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderConfigUpsert(BaseModel):
    tenant_id: str
    provider: ProviderType
    name: str
    enabled: bool = True
    secrets: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealth(BaseModel):
    provider: ProviderType
    healthy: bool
    details: str
