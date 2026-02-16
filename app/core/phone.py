from __future__ import annotations


def normalize_phone(phone: str) -> str:
    return ''.join(ch for ch in str(phone or '') if ch.isdigit())
