from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from uuid import uuid4


class SignalEnvelopeService:
    """Attach provenance so mock, API, and ingested signals stay clearly separated."""

    def enrich_api_detector_signal(
        self,
        *,
        signal: Dict[str, Any],
        detector_name: str,
        search_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        enriched = dict(signal)
        enriched.setdefault("signal_id", f"sig_{uuid4().hex[:12]}")
        enriched.setdefault("created_at", datetime.now(tz=UTC).isoformat())
        enriched["signal_origin"] = "api_generated"
        enriched["signal_emitter"] = detector_name
        evidence = dict(enriched.get("evidence") or {})
        evidence.setdefault("search_event", dict(search_event))
        enriched["evidence"] = evidence
        return enriched

    def enrich_ingested_signal(
        self,
        *,
        signal: Dict[str, Any],
        normalized_event: Dict[str, Any],
        event_origin: str,
        emitter: str,
    ) -> Dict[str, Any]:
        enriched = dict(signal)
        enriched.setdefault("signal_id", f"sig_{uuid4().hex[:12]}")
        enriched.setdefault("created_at", datetime.now(tz=UTC).isoformat())
        enriched["signal_origin"] = event_origin
        enriched["signal_emitter"] = emitter
        enriched.setdefault("source_event_id", normalized_event.get("event_id"))
        evidence = dict(enriched.get("evidence") or {})
        metadata = dict(evidence.get("metadata") or {})
        metadata.setdefault("event_origin", event_origin)
        metadata.setdefault("event_source_type", normalized_event.get("source_type"))
        evidence["metadata"] = metadata
        enriched["evidence"] = evidence
        return enriched
