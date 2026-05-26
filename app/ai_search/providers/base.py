from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict


class AISearchProvider(ABC):
    provider_name = "unknown"

    @abstractmethod
    async def search(
        self,
        *,
        query_text: str,
        index_name: str,
        limit: int = 20,
        search_mode: str = "live",
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_index_stats(self, index_name: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_index_settings(self, index_name: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def ensure_candidate_index_ready(self, force: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_candidate_index_cached_state(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        raise NotImplementedError
