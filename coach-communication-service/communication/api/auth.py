from __future__ import annotations

from fastapi import Header, HTTPException


async def require_admin_role(x_role: str = Header(default="viewer")) -> str:
    if x_role not in {"admin", "owner"}:
        raise HTTPException(status_code=403, detail="Admin role required")
    return x_role
