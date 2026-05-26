from __future__ import annotations

from typing import Any
from typing import Dict

from app.ai_search.factory import get_ai_search_provider
from app.ai_search.models import AISearchConnectionConfig
from app.ai_search.providers.base import AISearchProvider
from app.config import settings

_adapter: "AISearchAdapter | None" = None


class AISearchAdapter:
    """Application-facing wrapper around the configured AI search provider."""

    def __init__(self, provider: AISearchProvider, config: AISearchConnectionConfig):
        self._provider = provider
        self._config = config

    @property
    def provider_name(self) -> str:
        return self._config.provider

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def baseline_index(self) -> str:
        return self._config.baseline_index

    @property
    def candidate_index(self) -> str:
        return self._config.candidate_index

    async def search(
        self,
        *,
        query_text: str,
        index_name: str,
        limit: int = 20,
        search_mode: str = "live",
    ) -> Dict[str, Any]:
        return await self._provider.search(
            query_text=query_text,
            index_name=index_name,
            limit=limit,
            search_mode=search_mode,
        )

    async def search_baseline(
        self,
        *,
        query_text: str,
        limit: int = 20,
        search_mode: str = "live",
    ) -> Dict[str, Any]:
        return await self.search(
            query_text=query_text,
            index_name=self.baseline_index,
            limit=limit,
            search_mode=search_mode,
        )

    async def fetch_index_stats(self, index_name: str) -> Dict[str, Any]:
        return await self._provider.fetch_index_stats(index_name)

    async def fetch_index_settings(self, index_name: str) -> Dict[str, Any]:
        return await self._provider.fetch_index_settings(index_name)

    async def ensure_candidate_index_ready(self, force: bool = False) -> Dict[str, Any]:
        return await self._provider.ensure_candidate_index_ready(force=force)

    def get_candidate_index_cached_state(self) -> Dict[str, Any]:
        return self._provider.get_candidate_index_cached_state()

    async def health(self) -> Dict[str, Any]:
        return await self._provider.health()


def get_ai_search_adapter() -> AISearchAdapter:
    global _adapter

    if _adapter is not None:
        return _adapter

    config = AISearchConnectionConfig(
        provider=settings.AI_SEARCH_PROVIDER,
        base_url=settings.AI_SEARCH_BASE_URL,
        baseline_index=settings.AI_SEARCH_BASELINE_INDEX,
        candidate_index=settings.AI_SEARCH_CANDIDATE_INDEX,
    )
    _adapter = AISearchAdapter(
        provider=get_ai_search_provider(),
        config=config,
    )
    return _adapter
