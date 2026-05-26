from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Sequence

import httpx

from app.config import settings
from app.diagnosis.agents import BaseRLMSubtask
from app.diagnosis.agents import RLMIncidentContext
from app.diagnosis.agents import build_rlm_agent_graph
from app.diagnosis.agents import default_rlm_agents
from app.services.controlled_release_service import build_controlled_release_packet
from app.services.incident_packet_service import build_incident_packet
from app.services.ops_ledger import recent_signals
from app.services.rca_engine import RCAEngine
from app.services.rlm_models import RLMIncidentAnalysis
from app.services.rlm_models import RLMParentSynthesis
from app.services.rlm_models import OwnerPath
from app.services.shadow_testing_service import build_shadow_test_report
from app.services.traffic_router_service import get_traffic_router_status


class RLMIncidentOrchestrator:
    def __init__(
        self,
        subtasks: Sequence[BaseRLMSubtask] | None = None,
        provider: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
    ):
        self.subtasks = list(subtasks or default_rlm_agents())
        self.graph = build_rlm_agent_graph(self.subtasks)
        default_provider = "none"
        self.provider = (provider or default_provider).lower().strip()
        self.api_url = (api_url or settings.LLM_API_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL or "llama3"

    async def build_context(
        self,
        *,
        incident_packet: Dict[str, Any] | None = None,
        diagnostics_report: Dict[str, Any] | None = None,
        controlled_release_packet: Dict[str, Any] | None = None,
        shadow_test_report: Dict[str, Any] | None = None,
        traffic_router_status: Dict[str, Any] | None = None,
        signals_report: Iterable[Dict[str, Any]] | None = None,
    ) -> RLMIncidentContext:
        packet = incident_packet or await build_incident_packet()

        if diagnostics_report is None:
            diagnostics_report = await RCAEngine().run_diagnostics(run_llm=False)
        if controlled_release_packet is None:
            controlled_release_packet = await build_controlled_release_packet(record_audit=False)
        if shadow_test_report is None:
            shadow_test_report = await build_shadow_test_report(incident_packet=packet)
        if traffic_router_status is None:
            traffic_router_status = await get_traffic_router_status(force_refresh=True)

        return RLMIncidentContext(
            generated_at=datetime.now(tz=UTC).isoformat(),
            incident_packet=packet,
            diagnostics_report=diagnostics_report,
            controlled_release_packet=controlled_release_packet,
            shadow_test_report=shadow_test_report,
            traffic_router_status=traffic_router_status,
            recent_signals=list(recent_signals if signals_report is None else signals_report),
        )

    async def analyze(
        self,
        *,
        context: RLMIncidentContext | None = None,
        use_llm: bool = False,
    ) -> Dict[str, Any]:
        runtime_context = context or await self.build_context()
        graph_state = await self.graph.ainvoke({"context": runtime_context})
        subtask_results = list(graph_state.get("subtask_results", []))
        synthesis = self._build_parent_synthesis(runtime_context, subtask_results)

        analysis = RLMIncidentAnalysis(
            generated_at=runtime_context.generated_at,
            incident_id=runtime_context.incident_id,
            mode="langgraph+llm" if use_llm and self.provider != "none" else "langgraph",
            active_signal_types=_active_signal_types(runtime_context.recent_signals),
            signals_considered=len(runtime_context.recent_signals),
            evidence_sources=[
                "ops_ledger",
                "diagnostics",
                "shadow_test",
                "traffic_router",
                "controlled_release_packet",
            ],
            subtasks=list(subtask_results),
            synthesis=synthesis,
            llm_enrichment={},
        )

        llm_enrichment = await self._build_llm_enrichment(
            analysis=analysis.to_dict(),
            use_llm=use_llm,
        )
        analysis.llm_enrichment = llm_enrichment
        if llm_enrichment.get("used") and llm_enrichment.get("content"):
            narrative = llm_enrichment["content"].get("executive_summary")
            if narrative:
                analysis.synthesis.narrative = str(narrative)
            fix_order = llm_enrichment["content"].get("fix_order")
            if isinstance(fix_order, list):
                analysis.synthesis.recommended_fix_path = _dedupe_items(
                    list(fix_order) + list(analysis.synthesis.recommended_fix_path)
                )[:6]

        return analysis.to_dict()

    def _build_parent_synthesis(
        self,
        context: RLMIncidentContext,
        subtasks: Sequence[Any],
    ) -> RLMParentSynthesis:
        by_key = {subtask.key: subtask for subtask in subtasks}
        capability = by_key["affected_capability"].findings
        data_gap = by_key["data_gap"].findings
        metric_impact = by_key["metric_impact"].findings
        owner = by_key["owner_path"].findings

        owner_path = OwnerPath(
            primary_owner=str(owner.get("primary_owner", "Application owner")),
            secondary_owner=str(owner.get("secondary_owner", "Platform owner")),
            approver=str(owner.get("approver", "Engineering lead")),
            escalation_path=list(owner.get("escalation_path", [])),
        )

        root_cause = self._root_cause(context=context, data_gap=data_gap)
        rollout_readiness = self._rollout_readiness(context)
        confidence = _overall_confidence(subtasks)
        fix_path = _dedupe_items(
            list(by_key["data_gap"].recommended_actions)
            + list(context.runbook.get("candidate_fix", []))
        )[:6]

        return RLMParentSynthesis(
            incident_shape=str(capability.get("incident_shape", "single-signal")),
            affected_capability=str(capability.get("affected_capability", context.diagnosis.get("affected_capability", "unknown"))),
            capability_family=str(capability.get("capability_family", "unknown")),
            data_gap=str(data_gap.get("gap_type", "unknown")),
            metric_impact=list(metric_impact.get("metric_impact", [])),
            owner_path=owner_path,
            likely_root_cause=root_cause,
            recommended_fix_path=fix_path,
            rollout_readiness=rollout_readiness,
            business_impact=str(context.diagnosis.get("impact_summary", "Impact summary unavailable.")),
            confidence=confidence,
            narrative=None,
        )

    def _root_cause(self, *, context: RLMIncidentContext, data_gap: Dict[str, Any]) -> str:
        gap_type = str(data_gap.get("gap_type", "unknown"))
        query = context.incident_query

        if gap_type == "synthetic_test_query":
            return f"The incident is most likely caused by synthetic test traffic for '{query}', not a production search outage."
        if gap_type == "candidate-index-missing":
            return "The candidate index is missing, so evaluation cannot validate a release path yet."
        if gap_type == "baseline_index_empty":
            return "The active search index is empty or unseeded, which creates a direct catalog outage."
        if gap_type == "query_vocabulary_gap":
            return (
                f"The catalog exists, but '{query}' still returns zero hits, which points to vocabulary, synonym, or document-coverage gaps."
            )
        if gap_type == "candidate_catalog_delta":
            return "The candidate index is missing documents compared with baseline, so catalog completeness is the main release risk."
        if gap_type == "rule_configuration_diff":
            return "The candidate search settings differ from baseline, so ranking or rule configuration is the likely change surface."
        return str(context.diagnosis.get("root_cause", "Root cause is still being narrowed."))

    def _rollout_readiness(self, context: RLMIncidentContext) -> str:
        traffic = context.traffic_router_status
        blocked_reason = traffic.get("blocked_reason")
        release_phase = str(traffic.get("release_phase", "shadow"))
        shadow_ready = bool(context.shadow_test_report.get("summary", {}).get("shadow_ready"))
        ready_for_canary = bool(context.shadow_test_report.get("summary", {}).get("ready_for_canary"))
        live_percent = int(traffic.get("live_candidate_percent", 0) or 0)

        if blocked_reason:
            return f"blocked: {blocked_reason}"
        if live_percent > 0:
            return f"live-traffic-active:{release_phase}"
        if release_phase == "shadow" and ready_for_canary:
            return "ready-for-canary-after-approval"
        if release_phase == "shadow" and shadow_ready:
            return "shadow-ready"
        return "shadow-not-ready"

    async def _build_llm_enrichment(
        self,
        *,
        analysis: Dict[str, Any],
        use_llm: bool,
    ) -> Dict[str, Any]:
        if not use_llm:
            return {
                "used": False,
                "status": "disabled",
                "provider": self.provider,
                "model": self.model,
                "content": None,
                "error": "RLM enrichment is disabled for this request.",
            }

        if self.provider == "none":
            return {
                "used": False,
                "status": "disabled",
                "provider": self.provider,
                "model": self.model,
                "content": None,
                "error": "RLM LLM provider is disabled.",
            }

        prompt = self._build_prompt(analysis)
        try:
            content = await self._query_model(prompt)
            parsed = self._parse_json(content)
            return {
                "used": True,
                "status": "ok",
                "provider": self.provider,
                "model": self.model,
                "content": parsed,
                "error": None,
            }
        except Exception as exc:
            return {
                "used": False,
                "status": "fallback",
                "provider": self.provider,
                "model": self.model,
                "content": None,
                "error": str(exc),
            }

    def _build_prompt(self, analysis: Dict[str, Any]) -> str:
        return f"""You are the parent RLM for an operations incident workflow.
Use ONLY the code-executed evidence below. Do not invent telemetry, missing approvals, or index diffs.
If the incident query looks synthetic or test-generated, say so clearly.

Return JSON only with this exact schema:
{{
  "executive_summary": "string",
  "root_cause_story": "string",
  "business_impact_story": "string",
  "owner_handoff": "string",
  "fix_order": ["string", "string", "string"]
}}

RLM analysis:
{json.dumps(analysis, indent=2)}
"""

    async def _query_model(self, prompt: str) -> str:
        if self.provider == "ollama":
            return await self._query_ollama(prompt)
        raise RuntimeError(
            f"Unsupported provider '{self.provider}' for the RLM pipeline. Use 'ollama' or disable enrichment."
        )

    async def _query_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/chat",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("message", {}).get("content", "")).strip()

    def _parse_json(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise RuntimeError("RLM enrichment did not return valid JSON content.")
            return json.loads(content[start : end + 1])


def _active_signal_types(signals: Iterable[Dict[str, Any]]) -> List[str]:
    seen: List[str] = []
    for signal in signals:
        signal_type = str(signal.get("signal_type") or signal.get("type") or "unknown")
        if signal_type == "test" or signal_type in seen:
            continue
        seen.append(signal_type)
    return seen


def _dedupe_items(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _overall_confidence(subtasks: Sequence[Any]) -> str:
    confidences = [str(subtask.confidence).lower() for subtask in subtasks]
    if not confidences:
        return "low"
    if all(confidence == "high" for confidence in confidences):
        return "high"
    if "low" in confidences:
        return "low"
    return "medium"


async def build_rlm_incident_analysis(
    *,
    use_llm: bool = False,
    context: RLMIncidentContext | None = None,
) -> Dict[str, Any]:
    orchestrator = RLMIncidentOrchestrator(
        provider=os.getenv("RLM_ANALYSIS_LLM_PROVIDER", "ollama" if use_llm else "none"),
        api_url=os.getenv("RLM_ANALYSIS_LLM_API_URL", "http://host.docker.internal:11434"),
        model=os.getenv("RLM_ANALYSIS_LLM_MODEL", "llama3"),
    )
    return await orchestrator.analyze(context=context, use_llm=use_llm)


async def main(use_llm: bool = False) -> None:
    analysis = await build_rlm_incident_analysis(use_llm=use_llm)
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the RLM incident analysis packet.")
    parser.add_argument("--use-llm", action="store_true", help="Enable Ollama enrichment for the parent synthesis.")
    args = parser.parse_args()
    asyncio.run(main(use_llm=args.use_llm))
