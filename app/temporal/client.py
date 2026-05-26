from __future__ import annotations

import asyncio
from typing import Optional

from temporalio.client import Client

from app.config import settings

_client: Optional[Client] = None
_client_lock = asyncio.Lock()


async def get_temporal_client() -> Client:
    if not settings.TEMPORAL_ENABLED:
        raise RuntimeError("Temporal integration is disabled.")

    global _client
    if _client is not None:
        return _client

    async with _client_lock:
        if _client is None:
            _client = await Client.connect(
                settings.TEMPORAL_ADDRESS,
                namespace=settings.TEMPORAL_NAMESPACE,
            )
    return _client
