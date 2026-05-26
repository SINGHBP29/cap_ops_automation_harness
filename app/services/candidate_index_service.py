from __future__ import annotations

from typing import Any
from typing import Dict

from app.ai_search import get_ai_search_adapter


async def ensure_shadow_index_ready(force: bool = False) -> Dict[str, Any]:
    adapter = get_ai_search_adapter()
    return await adapter.ensure_candidate_index_ready(force=force)


def get_shadow_index_cached_state() -> Dict[str, Any]:
    adapter = get_ai_search_adapter()
    return adapter.get_candidate_index_cached_state()
