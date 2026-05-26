from __future__ import annotations

from typing import Callable

from app.ai_search.providers.base import AISearchProvider
from app.ai_search.providers.meilisearch import MeilisearchProvider
from app.config import settings

_provider: AISearchProvider | None = None
ProviderBuilder = Callable[[], AISearchProvider]


def _build_meilisearch_provider() -> AISearchProvider:
    return MeilisearchProvider(
        base_url=settings.AI_SEARCH_BASE_URL,
        baseline_index=settings.AI_SEARCH_BASELINE_INDEX,
        candidate_index=settings.AI_SEARCH_CANDIDATE_INDEX,
    )


PROVIDER_BUILDERS: dict[str, ProviderBuilder] = {
    "meilisearch": _build_meilisearch_provider,
}


def get_ai_search_provider() -> AISearchProvider:
    global _provider

    if _provider is not None:
        return _provider

    provider_name = settings.AI_SEARCH_PROVIDER.strip().lower()
    builder = PROVIDER_BUILDERS.get(provider_name)
    if builder is not None:
        _provider = builder()
        return _provider

    raise ValueError(
        f"Unsupported AI_SEARCH_PROVIDER '{settings.AI_SEARCH_PROVIDER}'. "
        "Add a provider implementation under app/ai_search/providers."
    )
