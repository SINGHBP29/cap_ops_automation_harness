from __future__ import annotations

from typing import Any
from typing import Dict

from app.models.ops_event import RawOpsEvent
from app.services.ops_event_ingestion_service import ingest_ops_event


def build_query_log_event(
    *,
    search_event: Dict[str, Any],
    routing: Dict[str, Any],
    routing_key: str,
    request_id: str | None,
    session_id: str | None,
    client_host: str | None,
) -> RawOpsEvent:
    return RawOpsEvent(
        source_type="query_log",
        event_type="search_response",
        capability="semantic_search",
        origin="api_generated",
        severity="info",
        query=search_event.get("query"),
        session_id=session_id,
        release_phase=str(routing.get("release_phase", "baseline")),
        metrics={
            "results_count": search_event.get("results_count"),
            "latency_ms": search_event.get("latency_ms"),
            "status_code": search_event.get("status_code"),
        },
        facts={
            "index_name": search_event.get("index_name"),
            "candidate_ready": routing.get("candidate_ready"),
            "shadow_mirror_enabled": routing.get("shadow_mirror_enabled"),
        },
        metadata={
            "request_id": request_id,
            "routing_key": routing_key,
            "client_host": client_host,
            "event_origin": "api_generated",
        },
    )


async def record_query_log_event(
    *,
    search_event: Dict[str, Any],
    routing: Dict[str, Any],
    routing_key: str,
    request_id: str | None,
    session_id: str | None,
    client_host: str | None,
) -> Dict[str, Any]:
    event = build_query_log_event(
        search_event=search_event,
        routing=routing,
        routing_key=routing_key,
        request_id=request_id,
        session_id=session_id,
        client_host=client_host,
    )
    return await ingest_ops_event(event, derive_signals=False)
