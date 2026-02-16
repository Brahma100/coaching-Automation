from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from app.config import settings


logger = logging.getLogger(__name__)

_bootstrap_lock = asyncio.Lock()
_bootstrapped = False
_bootstrap_pid: int | None = None
_ctx: Any = None


def _ensure_communication_repo_on_path() -> None:
    service_repo = Path(__file__).resolve().parents[2] / "coach-communication-service"
    if service_repo.exists() and str(service_repo) not in sys.path:
        sys.path.append(str(service_repo))


async def startup_embedded_communication() -> None:
    global _bootstrapped, _bootstrap_pid, _ctx
    if (settings.communication_mode or "").strip().lower() != "embedded":
        return

    async with _bootstrap_lock:
        current_pid = os.getpid()
        if _bootstrapped and _bootstrap_pid == current_pid:
            return

        _ensure_communication_repo_on_path()
        from communication.app_state import build_context, set_context  # type: ignore

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
        _ctx = ctx
        _bootstrapped = True
        _bootstrap_pid = current_pid
        logger.info("embedded_communication_started", extra={"pid": current_pid})


async def shutdown_embedded_communication() -> None:
    global _bootstrapped, _bootstrap_pid, _ctx
    if (settings.communication_mode or "").strip().lower() != "embedded":
        return

    async with _bootstrap_lock:
        if not _bootstrapped:
            return
        try:
            if _ctx is not None:
                await _ctx.worker.stop()
                logger.info("embedded_communication_stopped", extra={"pid": os.getpid()})
        finally:
            _ctx = None
            _bootstrapped = False
            _bootstrap_pid = None
