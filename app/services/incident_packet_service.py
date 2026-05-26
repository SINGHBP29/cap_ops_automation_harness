from __future__ import annotations

import os
from typing import Any
from typing import Dict

from app.services.intelligence_pipeline import IntelligencePipeline
from app.services.llm_intelligence_pipeline import LLMIntelligencePipeline
from app.services.ops_ledger import recent_signals
from app.services.rca_engine import RCAEngine


class IncidentPacketService:
    """Diagnose capability issues and build evidence-backed incident packets."""

    def __init__(
        self,
        *,
        pipeline: IntelligencePipeline | None = None,
        rca_engine_factory: type[RCAEngine] = RCAEngine,
    ) -> None:
        self._pipeline = pipeline or IntelligencePipeline()
        self._rca_engine_factory = rca_engine_factory

    def build_signals_report(self) -> Dict[str, Any]:
        return {
            "recent_signals": list(recent_signals)
        }

    async def build_diagnostics_report(self) -> Dict[str, Any]:
        rca = self._rca_engine_factory()
        return await rca.run_diagnostics(run_llm=False)

    async def build_packet(self) -> Dict[str, Any]:
        signals_report = self.build_signals_report()
        diagnostics_report = await self.build_diagnostics_report()
        return self._pipeline.build_incident_packet(signals_report, diagnostics_report)

    async def build_packet_llm(self) -> Dict[str, Any]:
        signals_report = self.build_signals_report()
        diagnostics_report = await self.build_diagnostics_report()
        pipeline = LLMIntelligencePipeline(
            provider=os.getenv("INCIDENT_PACKET_LLM_PROVIDER", "ollama"),
            api_url=os.getenv("INCIDENT_PACKET_LLM_API_URL", "http://host.docker.internal:11434"),
            model=os.getenv("INCIDENT_PACKET_LLM_MODEL", "llama3"),
        )
        return await pipeline.build_incident_packet(signals_report, diagnostics_report)


_service = IncidentPacketService()


async def build_incident_packet() -> Dict[str, Any]:
    return await _service.build_packet()


async def build_incident_packet_llm() -> Dict[str, Any]:
    return await _service.build_packet_llm()
