from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NotificationRule(BaseModel):
    id: str
    tenant_id: str
    event: str
    enabled: bool = True
    template_id: str
    preferred_providers: list[str] = Field(default_factory=lambda: ["telegram"])
    conditions: dict[str, Any] = Field(default_factory=dict)
    quiet_hours_exempt: bool = False


class NotificationRuleUpsert(BaseModel):
    tenant_id: str
    event: str
    enabled: bool = True
    template_id: str
    preferred_providers: list[str] = Field(default_factory=lambda: ["telegram"])
    conditions: dict[str, Any] = Field(default_factory=dict)
    quiet_hours_exempt: bool = False
