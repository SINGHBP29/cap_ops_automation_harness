from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any
from typing import Dict
from urllib.parse import quote_plus

from app.config import settings
from app.diagnosis.incident import IncidentPacketService
from app.release_control.plan import ControlledReleaseService
from app.signal_detection.capture import OpsSignalCaptureService
from app.models.ops_event import RawOpsEvent


@dataclass(frozen=True)
class OperatingModelPhase:
    phase_id: str
    title: str
    purpose: str
    owning_service: str
    primary_endpoint: str
    supporting_components: list[str]


class AISearchOpsHarnessService:
    """High-level class map for the Magellan AI Search operating model."""

    def __init__(
        self,
        *,
        signal_capture_service: OpsSignalCaptureService | None = None,
        incident_packet_service: IncidentPacketService | None = None,
        controlled_release_service: ControlledReleaseService | None = None,
    ) -> None:
        self._signal_capture_service = signal_capture_service or OpsSignalCaptureService()
        self._incident_packet_service = incident_packet_service or IncidentPacketService()
        self._controlled_release_service = controlled_release_service or ControlledReleaseService(
            incident_packet_service=self._incident_packet_service,
        )

    def describe_operating_model(self, operator_query: str | None = None) -> Dict[str, Any]:
        query = (operator_query or "").strip()
        query_suffix = f"?query={quote_plus(query)}" if query else ""
        console_data_params = "use_llm=true"
        if query:
            console_data_params += f"&query={quote_plus(query)}"

        phases = [
            OperatingModelPhase(
                phase_id="00",
                title="Operating Model",
                purpose="Turn every AI Search anomaly into a structured ops task after go-live.",
                owning_service=self.__class__.__name__,
                primary_endpoint=f"/operating-model{query_suffix}",
                supporting_components=["Search API / Gateway", "Operator UI", "Temporal Workflow"],
            ),
            OperatingModelPhase(
                phase_id="01",
                title="Capture Ops Signals",
                purpose="Ingest query, catalog, inventory, multimodal, UGC, and MXP events into one ledger.",
                owning_service=OpsSignalCaptureService.__name__,
                primary_endpoint="/ops-events/ingest",
                supporting_components=["AI Search Adapter", "Observability Layer", "Ops Ledger"],
            ),
            OperatingModelPhase(
                phase_id="02",
                title="Diagnose Capability",
                purpose="Map symptoms to the responsible AI Search capability and likely root cause.",
                owning_service=IncidentPacketService.__name__,
                primary_endpoint="/incident-packet",
                supporting_components=["Signal Detection", "RCA Engine", "RLM Analysis"],
            ),
            OperatingModelPhase(
                phase_id="03",
                title="Propose Runbook",
                purpose="Generate a fix, eval set, owner path, canary plan, and rollback plan.",
                owning_service=IncidentPacketService.__name__,
                primary_endpoint=f"/operator-console-data?{console_data_params}",
                supporting_components=["Runbook Factory", "Eval Factory", "Operator Console"],
            ),
            OperatingModelPhase(
                phase_id="04",
                title="Release Safely",
                purpose="Coordinate guarded rollouts through evals, approvals, canaries, and rollback conditions.",
                owning_service=ControlledReleaseService.__name__,
                primary_endpoint="/controlled-release-packet",
                supporting_components=["Human Approval", "Temporal Workflow", "Release Controller"],
            ),
        ]
        return {
            "service": self.__class__.__name__,
            "operator_query": query or None,
            "entrypoints": {
                "operator_console": f"/operator-console{query_suffix}",
                "operator_console_data": f"/operator-console-data?{console_data_params}",
                "temporal_ui": settings.TEMPORAL_UI_URL,
            },
            "phases": [asdict(phase) for phase in phases],
        }

    async def capture_ops_signal(self, event: RawOpsEvent, derive_signals: bool = True) -> Dict[str, Any]:
        return await self._signal_capture_service.ingest_event(event, derive_signals=derive_signals)

    async def diagnose_capability(self, use_llm: bool = False) -> Dict[str, Any]:
        if use_llm:
            return await self._incident_packet_service.build_packet_llm()
        return await self._incident_packet_service.build_packet()

    async def propose_runbook(self, use_llm: bool = False) -> Dict[str, Any]:
        packet = await self.diagnose_capability(use_llm=use_llm)
        return {
            "incident_id": packet["incident_id"],
            "diagnosis": packet["diagnosis"],
            "runbook": packet["runbook"],
            "evaluation": packet["evaluation"],
        }

    async def release_safely(self, use_llm: bool = False, record_audit: bool = False) -> Dict[str, Any]:
        if use_llm:
            return await self._controlled_release_service.build_packet_llm(record_audit=record_audit)
        return await self._controlled_release_service.build_packet(record_audit=record_audit)
