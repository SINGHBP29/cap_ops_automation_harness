"""Release-time change application entry points for the search backend."""

from app.services.candidate_index_service import ensure_shadow_index_ready
from app.services.candidate_index_service import get_shadow_index_cached_state
from app.services.traffic_router_service import sync_candidate_index

__all__ = [
    "ensure_shadow_index_ready",
    "get_shadow_index_cached_state",
    "sync_candidate_index",
]
