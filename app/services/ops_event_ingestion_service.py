from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from uuid import uuid4

from app.kafka_client.producer import publish_signal
from app.models.capability_signal import CapabilitySignalEvent
from app.models.ops_event import RawOpsEvent
from app.services.capability_signal_engine import CapabilitySignalEngine
from app.services.ops_ledger import ledger_snapshot
from app.services.ops_ledger import store_event
from app.services.ops_ledger import store_signal
from app.services.signal_envelope_service import SignalEnvelopeService


class OpsSignalCaptureService:
    """Capture raw AI Search ops events and derive structured signals."""

    SOURCE_CAPABILITY_MAP = {
        "query_log": "semantic_search",
        "zero_result_session": "semantic_search",
        "catalog_delta": "catalog",
        "inventory_shift": "catalog",
        "autocomplete_probe": "autocomplete",
        "voice_search_attempt": "semantic_index",
        "voice_search_failure": "semantic_index",
        "image_search_attempt": "semantic_index",
        "image_search_failure": "semantic_index",
        "reviews_signal": "semantic_index",
        "ugc_signal": "semantic_index",
        "personalization_event": "personalization",
        "mxp_rule_diff": "merchandising",
        "mxp_override": "merchandising",
    }

    SUPPORTED_CAPABILITIES = {
        "semantic_search",
        "catalog",
        "autocomplete",
        "semantic_index",
        "personalization",
        "merchandising",
    }

    def __init__(self, signal_engine: CapabilitySignalEngine | None = None) -> None:
        self._signal_engine = signal_engine or CapabilitySignalEngine()
        self._envelope_service = SignalEnvelopeService()

    def infer_capability(self, event: RawOpsEvent) -> str:
        if event.capability:
            return event.capability
        return self.SOURCE_CAPABILITY_MAP.get(event.source_type, "unknown")

    def normalize_event(self, event: RawOpsEvent) -> Dict[str, Any]:
        created_at = event.created_at or datetime.now(tz=UTC).isoformat()
        capability = self.infer_capability(event)
        event_origin = event.origin or str(event.metadata.get("event_origin") or "ops_api")
        metadata = dict(event.metadata)
        metadata.setdefault("event_origin", event_origin)
        return {
            "event_id": f"evt_{uuid4().hex[:12]}",
            "source_type": event.source_type,
            "event_type": event.event_type,
            "capability": capability,
            "event_origin": event_origin,
            "severity": event.severity,
            "query": event.query,
            "session_id": event.session_id,
            "entity_id": event.entity_id,
            "release_phase": event.release_phase,
            "created_at": created_at,
            "metrics": dict(event.metrics),
            "facts": dict(event.facts),
            "metadata": metadata,
        }

    def to_capability_signal_event(self, event: RawOpsEvent) -> CapabilitySignalEvent | None:
        capability = self.infer_capability(event)
        if capability not in self.SUPPORTED_CAPABILITIES:
            return None
        return CapabilitySignalEvent(
            capability=capability,  # type: ignore[arg-type]
            event_type=event.event_type,
            query=event.query,
            request_id=str(event.metadata.get("request_id") or "") or None,
            trace_id=str(event.metadata.get("trace_id") or "") or None,
            release_phase=event.release_phase,
            metrics=dict(event.metrics),
            facts=dict(event.facts),
            metadata=dict(event.metadata),
        )

    async def ingest_event(self, event: RawOpsEvent, derive_signals: bool = True) -> Dict[str, Any]:
        normalized = self.normalize_event(event)
        await store_event(normalized)

        derived_signals = []
        if derive_signals:
            capability_event = self.to_capability_signal_event(event)
            if capability_event is not None:
                derived_signals = self._signal_engine.evaluate(capability_event)
                for signal in derived_signals:
                    enriched_signal = self._envelope_service.enrich_ingested_signal(
                        signal=signal,
                        normalized_event=normalized,
                        event_origin=normalized["event_origin"],
                        emitter=event.source_type,
                    )
                    publish_signal(enriched_signal)
                    await store_signal(enriched_signal)

        snapshot = ledger_snapshot()
        return {
            "ingested_at": datetime.now(tz=UTC).isoformat(),
            "event": normalized,
            "derived_signal_count": len(derived_signals),
            "derived_signals": derived_signals,
            "ledger_counts": {
                "events": snapshot["event_count"],
                "signals": snapshot["signal_count"],
            },
        }


_service = OpsSignalCaptureService()


async def ingest_ops_event(event: RawOpsEvent, derive_signals: bool = True) -> Dict[str, Any]:
    return await _service.ingest_event(event, derive_signals=derive_signals)
