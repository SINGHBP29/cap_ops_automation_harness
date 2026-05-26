from __future__ import annotations

import math
import os
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict

import httpx

from app.monitoring.metrics import ACTIVE_SIGNALS
from app.monitoring.metrics import HTTP_REQUESTS_TOTAL
from app.monitoring.metrics import SIGNALS_TOTAL
from app.monitoring.metrics import ZERO_RESULT_QUERIES_TOTAL
from app.services.controlled_release_pipeline import ControlledReleasePipeline
from app.services.incident_packet_service import IncidentPacketService
from app.services.llm_controlled_release_pipeline import LLMControlledReleasePipeline
from app.services.release_audit_ledger import append_controlled_release_record
from app.services.release_audit_ledger import get_controlled_release_audit_backend
from app.services.release_audit_ledger import list_controlled_release_records


class ControlledReleaseService:
    """Build release-safe rollout packets after eval, approval, and guardrail checks."""

    def __init__(
        self,
        *,
        incident_packet_service: IncidentPacketService | None = None,
        release_pipeline: ControlledReleasePipeline | None = None,
    ) -> None:
        self._incident_packet_service = incident_packet_service or IncidentPacketService()
        self._release_pipeline = release_pipeline or ControlledReleasePipeline()

    def _sum_metric_samples(self, metric: Any, sample_name: str) -> float:
        total = 0.0
        for family in metric.collect():
            for sample in family.samples:
                if sample.name == sample_name:
                    total += float(sample.value)
        return total

    async def _prometheus_scalar(self, query: str) -> Dict[str, Any]:
        url = os.getenv("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{url}/api/v1/query",
                    params={"query": query},
                    timeout=3.0,
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("data", {}).get("result", [])
                if not result:
                    return {
                        "value": None,
                        "status": "unavailable",
                        "source": "prometheus",
                        "note": f"No result for query: {query}",
                    }
                value = float(result[0]["value"][1])
                if not math.isfinite(value):
                    return {
                        "value": None,
                        "status": "unavailable",
                        "source": "prometheus",
                        "note": f"{query} (non-finite result)",
                    }
                return {
                    "value": value,
                    "status": "ok",
                    "source": "prometheus",
                    "note": query,
                }
        except Exception as exc:
            return {
                "value": None,
                "status": "unavailable",
                "source": "prometheus",
                "note": f"{query} ({exc})",
            }

    async def build_telemetry_snapshot(self) -> Dict[str, Any]:
        request_rate = await self._prometheus_scalar("sum(rate(signal_engine_http_requests_total[5m]))")
        p95_latency = await self._prometheus_scalar(
            "histogram_quantile(0.95, sum(rate(signal_engine_http_request_duration_seconds_bucket[5m])) by (le))"
        )

        metrics = [
            {
                "name": "request_rate_rps",
                "value": request_rate["value"],
                "unit": "req/s",
                "source": request_rate["source"],
                "status": request_rate["status"],
                "note": request_rate["note"],
            },
            {
                "name": "search_p95_latency_seconds",
                "value": p95_latency["value"],
                "unit": "s",
                "source": p95_latency["source"],
                "status": p95_latency["status"],
                "note": p95_latency["note"],
            },
            {
                "name": "active_signals",
                "value": self._sum_metric_samples(ACTIVE_SIGNALS, "signal_engine_active_signals"),
                "unit": "count",
                "source": "in-process",
                "status": "ok",
                "note": "Current in-memory active signal gauge.",
            },
            {
                "name": "zero_result_queries_total",
                "value": self._sum_metric_samples(ZERO_RESULT_QUERIES_TOTAL, "signal_engine_zero_result_queries_total"),
                "unit": "count",
                "source": "in-process",
                "status": "ok",
                "note": "Total zero-result queries observed by the detector.",
            },
            {
                "name": "signals_total",
                "value": self._sum_metric_samples(SIGNALS_TOTAL, "signal_engine_signals_total"),
                "unit": "count",
                "source": "in-process",
                "status": "ok",
                "note": "Total emitted operational signals across severities and types.",
            },
            {
                "name": "http_requests_total",
                "value": self._sum_metric_samples(HTTP_REQUESTS_TOTAL, "signal_engine_http_requests_total"),
                "unit": "count",
                "source": "in-process",
                "status": "ok",
                "note": "Total counted requests excluding explicitly excluded health endpoints.",
            },
        ]

        return {
            "collected_at": datetime.now(tz=UTC).isoformat(),
            "metrics": metrics,
        }

    async def build_packet(self, record_audit: bool = False) -> Dict[str, Any]:
        incident_packet = await self._incident_packet_service.build_packet()
        return await self.build_packet_from_incident(incident_packet, record_audit=record_audit)

    async def build_packet_from_incident(
        self,
        incident_packet: Dict[str, Any],
        record_audit: bool = False,
    ) -> Dict[str, Any]:
        telemetry_snapshot = await self.build_telemetry_snapshot()
        packet = self._release_pipeline.build_packet(incident_packet, telemetry_snapshot)
        if record_audit:
            append_controlled_release_record(packet["audit_record"])
        return packet

    async def build_packet_llm(self, record_audit: bool = False) -> Dict[str, Any]:
        incident_packet = await self._incident_packet_service.build_packet()
        return await self.build_packet_llm_from_incident(incident_packet, record_audit=record_audit)

    async def build_packet_llm_from_incident(
        self,
        incident_packet: Dict[str, Any],
        record_audit: bool = False,
    ) -> Dict[str, Any]:
        telemetry_snapshot = await self.build_telemetry_snapshot()
        pipeline = LLMControlledReleasePipeline(
            provider=os.getenv("CONTROLLED_RELEASE_LLM_PROVIDER", "ollama"),
            api_url=os.getenv("CONTROLLED_RELEASE_LLM_API_URL", "http://host.docker.internal:11434"),
            model=os.getenv("CONTROLLED_RELEASE_LLM_MODEL", "llama3"),
        )
        packet = await pipeline.build_packet(incident_packet, telemetry_snapshot)
        if record_audit:
            append_controlled_release_record(packet["audit_record"])
        return packet

    def get_audit_ledger(self) -> Dict[str, Any]:
        return {
            "backend": get_controlled_release_audit_backend(),
            "records": list_controlled_release_records(),
        }


_service = ControlledReleaseService()


async def build_telemetry_snapshot() -> Dict[str, Any]:
    return await _service.build_telemetry_snapshot()


async def build_controlled_release_packet(record_audit: bool = False) -> Dict[str, Any]:
    return await _service.build_packet(record_audit=record_audit)


async def build_controlled_release_packet_from_incident(
    incident_packet: Dict[str, Any],
    record_audit: bool = False,
) -> Dict[str, Any]:
    return await _service.build_packet_from_incident(incident_packet, record_audit=record_audit)


async def build_controlled_release_packet_llm(record_audit: bool = False) -> Dict[str, Any]:
    return await _service.build_packet_llm(record_audit=record_audit)


async def build_controlled_release_packet_llm_from_incident(
    incident_packet: Dict[str, Any],
    record_audit: bool = False,
) -> Dict[str, Any]:
    return await _service.build_packet_llm_from_incident(incident_packet, record_audit=record_audit)


def get_controlled_release_audit_ledger() -> Dict[str, Any]:
    return _service.get_audit_ledger()
