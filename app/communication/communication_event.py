from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CommunicationEventType(str, Enum):
    CLASS_STARTED = "CLASS_STARTED"
    ATTENDANCE_SUBMITTED = "ATTENDANCE_SUBMITTED"
    FEE_DUE = "FEE_DUE"
    HOMEWORK_ASSIGNED = "HOMEWORK_ASSIGNED"
    STUDENT_ADDED = "STUDENT_ADDED"
    BATCH_RESCHEDULED = "BATCH_RESCHEDULED"
    DAILY_BRIEF = "DAILY_BRIEF"


class CommunicationEvent(BaseModel):
    event_type: str
    tenant_id: str
    actor_id: int | None = None
    entity_type: str
    entity_id: int
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
    channels: list[str]
