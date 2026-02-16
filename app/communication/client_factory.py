from __future__ import annotations

import logging
from functools import lru_cache

from app.communication.clients import EmbeddedCommunicationClient, RemoteCommunicationClient
from app.config import settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_communication_client():
    mode = (settings.communication_mode or "embedded").strip().lower()
    logger.info(
        "communication_mode_selected",
        extra={"mode": mode, "service_url": settings.communication_service_url},
    )
    if mode == "embedded":
        return EmbeddedCommunicationClient()
    return RemoteCommunicationClient(settings.communication_service_url)
