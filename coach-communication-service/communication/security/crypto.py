from __future__ import annotations

import base64
import hashlib
import os


class TokenCrypto:
    def __init__(self, seed: str | None = None) -> None:
        self.seed = seed or os.getenv("COMMUNICATION_SECRET", "change-me-in-production")

    def _keystream(self, length: int) -> bytes:
        stream = b""
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(f"{self.seed}:{counter}".encode("utf-8")).digest()
            stream += block
            counter += 1
        return stream[:length]

    def encrypt(self, value: str) -> str:
        raw = value.encode("utf-8")
        stream = self._keystream(len(raw))
        cipher = bytes(a ^ b for a, b in zip(raw, stream))
        return base64.urlsafe_b64encode(cipher).decode("utf-8")

    def decrypt(self, value: str) -> str:
        cipher = base64.urlsafe_b64decode(value.encode("utf-8"))
        stream = self._keystream(len(cipher))
        plain = bytes(a ^ b for a, b in zip(cipher, stream))
        return plain.decode("utf-8")
