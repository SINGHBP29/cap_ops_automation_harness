"""API-facing signal detection for live search traffic."""

from app.services.signal_service import process_search_event

__all__ = ["process_search_event"]
