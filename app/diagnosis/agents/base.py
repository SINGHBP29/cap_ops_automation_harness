from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List

from app.services.rlm_models import CodeActStep
from app.services.rlm_models import FocusedEvidenceWindow
from app.services.rlm_models import RLMSubtaskResult


@dataclass
class RLMIncidentContext:
    generated_at: str
    incident_packet: Dict[str, Any]
    diagnostics_report: Dict[str, Any]
    controlled_release_packet: Dict[str, Any]
    shadow_test_report: Dict[str, Any]
    traffic_router_status: Dict[str, Any]
    recent_signals: List[Dict[str, Any]]

    @property
    def incident_id(self) -> str:
        return str(self.incident_packet.get("incident_id", "unknown-incident"))

    @property
    def diagnosis(self) -> Dict[str, Any]:
        return self.incident_packet.get("diagnosis", {})

    @property
    def runbook(self) -> Dict[str, Any]:
        return self.incident_packet.get("runbook", {})

    @property
    def evaluation(self) -> Dict[str, Any]:
        return self.incident_packet.get("evaluation", {})

    @property
    def incident_query(self) -> str:
        dataset = self.runbook.get("eval_dataset", {})
        queries = dataset.get("incident_queries", [])
        if queries:
            return str(queries[0])
        return str(self.diagnosis.get("query", "unknown-query"))

    @property
    def signal_type(self) -> str:
        return str(self.diagnosis.get("signal_type", "unknown"))


class BaseRLMSubtask:
    key = "base"
    title = "Base RLM Subtask"
    focus = ""
    evidence_sources: tuple[str, ...] = ()

    async def analyze(self, context: RLMIncidentContext) -> RLMSubtaskResult:
        raise NotImplementedError

    def _window(self, snapshot: Dict[str, Any]) -> FocusedEvidenceWindow:
        return FocusedEvidenceWindow(
            focus=self.focus,
            sources=list(self.evidence_sources),
            snapshot=snapshot,
        )

    def _result(
        self,
        *,
        status: str,
        summary: str,
        confidence: str,
        evidence_window: FocusedEvidenceWindow,
        codeact_steps: List[CodeActStep],
        findings: Dict[str, Any],
        recommended_actions: List[str],
    ) -> RLMSubtaskResult:
        return RLMSubtaskResult(
            key=self.key,
            title=self.title,
            status=status,
            summary=summary,
            confidence=confidence,
            evidence_window=evidence_window,
            codeact_steps=codeact_steps,
            findings=findings,
            recommended_actions=recommended_actions,
        )
