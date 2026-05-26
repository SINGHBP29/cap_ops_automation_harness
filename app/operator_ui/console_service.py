from __future__ import annotations

import asyncio
from collections import Counter
from copy import deepcopy
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

from app.ai_search import get_ai_search_adapter
from app.models.approval import ApprovalSubmission
from app.models.feedback import FeedbackIncidentAutomationSubmission
from app.diagnosis.incident import IncidentPacketService
from app.diagnosis.rca import RCAEngine
from app.diagnosis.rlm import RLMIncidentContext
from app.diagnosis.rlm import build_rlm_incident_analysis
from app.release_control.plan import ControlledReleaseService
from app.release_control.router_policy import get_traffic_router_status
from app.release_control.shadow import build_shadow_test_report
from app.release_control.temporal_service import ensure_controlled_release_workflow
from app.release_control.temporal_service import get_controlled_release_workflow_state
from app.release_control.temporal_service import signal_temporal_refresh
from app.state.approval import get_approval_backend
from app.state.approval import get_latest_approval
from app.state.feedback import get_automation_policy
from app.state.feedback import get_effective_automation_policy
from app.state.feedback import get_feedback_state
from app.state.feedback import get_incident_automation_override
from app.state.feedback import list_incident_outcomes
from app.state.feedback import set_incident_automation_override
from app.state.approval import save_approval_decision
from app.state.audit import get_controlled_release_audit_backend
from app.state.ops_ledger import recent_events
from app.state.ops_ledger import recent_signals
from app.services.search_service import execute_search_against_index
from app.services.feedback_automation_service import FeedbackAutomationService


class OperatorConsoleService:
    def __init__(
        self,
        *,
        incident_packet_service: IncidentPacketService | None = None,
        controlled_release_service: ControlledReleaseService | None = None,
        rca_engine_factory: type[RCAEngine] = RCAEngine,
        feedback_automation_service: FeedbackAutomationService | None = None,
    ) -> None:
        self._incident_packet_service = incident_packet_service or IncidentPacketService()
        self._controlled_release_service = controlled_release_service or ControlledReleaseService(
            incident_packet_service=self._incident_packet_service,
        )
        self._rca_engine_factory = rca_engine_factory
        self._feedback_automation_service = feedback_automation_service or FeedbackAutomationService()

    async def build_console_data(self, use_llm: bool = True, operator_query: str | None = None) -> Dict[str, Any]:
        incident_packet = await (
            self._incident_packet_service.build_packet_llm()
            if use_llm
            else self._incident_packet_service.build_packet()
        )
        incident_packet = self._apply_operator_query_override(incident_packet, operator_query)
        controlled_release_packet = await (
            self._controlled_release_service.build_packet_llm_from_incident(incident_packet, record_audit=False)
            if use_llm
            else self._controlled_release_service.build_packet_from_incident(incident_packet, record_audit=False)
        )

        rca = self._rca_engine_factory()
        diagnostics = await rca.run_diagnostics(run_llm=False)
        shadow_test = await self._build_shadow_test(incident_packet, operator_query)
        temporal_start = await ensure_controlled_release_workflow(incident_packet)
        if temporal_start.get("status") == "started":
            await asyncio.sleep(0.6)
        temporal = await get_controlled_release_workflow_state(incident_packet["incident_id"])
        traffic_router = await get_traffic_router_status(force_refresh=True)
        if traffic_router.get("candidate_ready") and not temporal.get("shadow_ready", False):
            await signal_temporal_refresh(
                incident_packet["incident_id"],
                "Refresh after candidate index sync.",
            )
            await asyncio.sleep(0.5)
            temporal = await get_controlled_release_workflow_state(incident_packet["incident_id"])

        rlm_context = RLMIncidentContext(
            generated_at=datetime.now(tz=UTC).isoformat(),
            incident_packet=incident_packet,
            diagnostics_report=diagnostics,
            controlled_release_packet=controlled_release_packet,
            shadow_test_report=shadow_test,
            traffic_router_status=traffic_router,
            recent_signals=list(recent_signals),
        )
        rlm_analysis = await build_rlm_incident_analysis(use_llm=use_llm, context=rlm_context)

        latest_approval = get_latest_approval(incident_packet["incident_id"])
        feedback_automation = self._feedback_automation_service.evaluate(
            incident_packet=incident_packet,
            controlled_release_packet=controlled_release_packet,
            shadow_test=shadow_test,
            current_phase=str(temporal.get("release_phase") or traffic_router.get("release_phase") or "shadow"),
            approval=latest_approval or temporal.get("approval"),
        )
        approval_required = not controlled_release_packet["approval"]["auto_approval_eligible"]
        effective_query = incident_packet["runbook"]["eval_dataset"]["incident_queries"][0]
        supervisor_view = await self._build_supervisor_view(
            effective_query=effective_query,
            incident_packet=incident_packet,
            traffic_router=traffic_router,
            shadow_test=shadow_test,
            signals=list(recent_signals),
            events=list(recent_events),
        )

        return {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "operator_query": (operator_query or "").strip() or None,
            "effective_query": effective_query,
            "signals": {
                "recent_signals": list(recent_signals),
            },
            "diagnostics": diagnostics,
            "incident_packet": incident_packet,
            "controlled_release_packet": controlled_release_packet,
            "shadow_test": shadow_test,
            "rlm_analysis": rlm_analysis,
            "temporal": {
                **temporal,
                "startup_status": temporal_start.get("status"),
                "ui_url": temporal.get("ui_url"),
            },
            "supervisor": supervisor_view,
            "traffic_router": traffic_router,
            "business_impact": self._build_business_impact(incident_packet, controlled_release_packet),
            "approval": {
                "required": approval_required,
                "backend": get_approval_backend(),
                "latest": latest_approval,
                "gate_message": self._approval_gate_message(approval_required, latest_approval),
            },
            "audit_ledger": self._controlled_release_service.get_audit_ledger(),
            "feedback": {
                "state": get_feedback_state(),
                "automation": feedback_automation,
                "effective_automation": get_effective_automation_policy(incident_packet["incident_id"]),
                "incident_override": get_incident_automation_override(incident_packet["incident_id"]),
                "recent_outcomes": list_incident_outcomes(limit=12),
            },
            "state_backends": {
                "approval_backend": get_approval_backend(),
                "audit_backend": get_controlled_release_audit_backend(),
            },
            "stage_statuses": self._build_stage_statuses(
                signals=list(recent_signals),
                incident_packet=incident_packet,
                controlled_release_packet=controlled_release_packet,
                shadow_test=shadow_test,
                temporal=temporal,
                latest_approval=latest_approval,
            ),
            "report_links": {
                "incident_report": "/incident-report.md" + ("?use_llm=true" if use_llm else ""),
                "controlled_release_report": "/controlled-release-report.md" + ("?use_llm=true" if use_llm else ""),
                "rlm_analysis": "/rlm-incident-analysis-llm" if use_llm else "/rlm-incident-analysis",
                "temporal_ui": temporal.get("ui_url"),
            },
        }

    def feedback_state_view(self, incident_id: str | None = None) -> Dict[str, Any]:
        return {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "incident_id": incident_id,
            "global_state": get_feedback_state(),
            "global_automation_policy": get_automation_policy(),
            "incident_override": get_incident_automation_override(incident_id or ""),
            "effective_automation_policy": get_effective_automation_policy(incident_id),
        }

    def feedback_outcomes_view(self, limit: int = 50) -> Dict[str, Any]:
        normalized_limit = max(1, min(int(limit), 200))
        return {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "records": list_incident_outcomes(limit=normalized_limit),
        }

    def update_incident_automation_controls(
        self,
        submission: FeedbackIncidentAutomationSubmission,
    ) -> Dict[str, Any]:
        if not submission.incident_id.strip():
            raise ValueError("Incident id is required.")
        if (
            not submission.clear_override
            and submission.enabled is None
            and submission.auto_promote_enabled is None
            and submission.auto_rollback_enabled is None
        ):
            raise ValueError("Provide at least one automation control change or clear the override.")

        override = set_incident_automation_override(
            submission.incident_id,
            enabled=submission.enabled,
            auto_promote_enabled=submission.auto_promote_enabled,
            auto_rollback_enabled=submission.auto_rollback_enabled,
            note=submission.note,
            clear_override=submission.clear_override,
        )
        return {
            "incident_id": submission.incident_id,
            "incident_override": override,
            "effective_automation_policy": get_effective_automation_policy(submission.incident_id),
            "global_automation_policy": get_automation_policy(),
        }

    def record_human_approval(self, submission: ApprovalSubmission) -> Dict[str, Any]:
        record = {
            "incident_id": submission.incident_id,
            "reviewer": submission.reviewer.strip(),
            "decision": submission.decision,
            "rationale": submission.rationale.strip(),
            "reviewed_business_impact": submission.reviewed_business_impact,
            "reviewed_business_guardrails": submission.reviewed_business_guardrails,
            "created_at": datetime.now(tz=UTC).isoformat(),
        }
        return save_approval_decision(record)

    async def _build_shadow_test(self, incident_packet: Dict[str, Any], operator_query: str | None) -> Dict[str, Any]:
        query = (operator_query or "").strip()
        if query:
            return await build_shadow_test_report(queries=[query], incident_packet=incident_packet)
        return await build_shadow_test_report(incident_packet=incident_packet)

    async def _build_supervisor_view(
        self,
        *,
        effective_query: str,
        incident_packet: Dict[str, Any],
        traffic_router: Dict[str, Any],
        shadow_test: Dict[str, Any],
        signals: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        summary = self._build_signal_summary(
            signals=signals,
            events=events,
            incident_packet=incident_packet,
            traffic_router=traffic_router,
        )
        inspector = await self._build_query_inspector(
            query=effective_query,
            capability=str(incident_packet.get("diagnosis", {}).get("affected_capability", "unknown")),
            traffic_router=traffic_router,
            shadow_test=shadow_test,
            signals=signals,
            events=events,
        )
        incident_feed = self._build_incident_feed(signals)
        return {
            "signal_summary": summary,
            "query_inspector": inspector,
            "incident_feed": incident_feed,
        }

    def _build_signal_summary(
        self,
        *,
        signals: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        incident_packet: Dict[str, Any],
        traffic_router: Dict[str, Any],
    ) -> Dict[str, Any]:
        severity_counter = Counter(str(signal.get("severity") or "info").lower() for signal in signals)
        capability_counter = Counter(str(signal.get("capability") or "unknown") for signal in signals)
        origin_counter = Counter(str(signal.get("signal_origin") or "unknown") for signal in signals)
        event_origin_counter = Counter(
            str(event.get("event_origin") or event.get("metadata", {}).get("event_origin") or "unknown")
            for event in events
        )
        latest_signal = signals[-1] if signals else None
        return {
            "total_signals": len(signals),
            "total_events": len(events),
            "latest_signal_type": latest_signal.get("signal_type") if latest_signal else None,
            "latest_signal_at": latest_signal.get("created_at") if latest_signal else None,
            "active_capability": incident_packet.get("diagnosis", {}).get("affected_capability", "unknown"),
            "release_phase": traffic_router.get("release_phase", "baseline"),
            "candidate_ready": bool(traffic_router.get("candidate_ready")),
            "live_candidate_percent": int(traffic_router.get("live_candidate_percent", 0) or 0),
            "blocked_reason": traffic_router.get("blocked_reason"),
            "severity_counts": dict(severity_counter),
            "capability_counts": dict(capability_counter),
            "signal_origin_counts": dict(origin_counter),
            "event_origin_counts": dict(event_origin_counter),
        }

    async def _build_query_inspector(
        self,
        *,
        query: str,
        capability: str,
        traffic_router: Dict[str, Any],
        shadow_test: Dict[str, Any],
        signals: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        trimmed_query = str(query or "").strip()
        if not trimmed_query or trimmed_query == "unknown-query":
            return {
                "available": False,
                "query": trimmed_query or "unknown-query",
                "message": "Provide a real query to inspect the exact search behavior and related signals.",
                "related_signals": self._related_signals(signals, None, capability),
                "related_events": self._related_events(events, None, capability),
            }

        adapter = get_ai_search_adapter()
        baseline_result, candidate_result = await asyncio.gather(
            execute_search_against_index(
                query_text=trimmed_query,
                index_name=adapter.baseline_index,
                limit=5,
                search_mode="supervisor-inspect-baseline",
            ),
            execute_search_against_index(
                query_text=trimmed_query,
                index_name=adapter.candidate_index,
                limit=5,
                search_mode="supervisor-inspect-candidate",
            ),
        )

        shadow_comparison = self._find_shadow_comparison(shadow_test, trimmed_query)
        triage_status, triage_note = self._triage_query(
            query=trimmed_query,
            baseline_result=baseline_result,
            candidate_result=candidate_result,
            shadow_comparison=shadow_comparison,
        )

        return {
            "available": True,
            "query": trimmed_query,
            "triage_status": triage_status,
            "triage_note": triage_note,
            "routing": {
                "release_phase": traffic_router.get("release_phase", "baseline"),
                "workflow_status": traffic_router.get("workflow_status", "unknown"),
                "live_candidate_percent": int(traffic_router.get("live_candidate_percent", 0) or 0),
                "shadow_mirror_enabled": bool(traffic_router.get("shadow_mirror_enabled")),
                "candidate_ready": bool(traffic_router.get("candidate_ready")),
                "blocked_reason": traffic_router.get("blocked_reason"),
            },
            "baseline": self._search_snapshot(baseline_result),
            "candidate": self._search_snapshot(candidate_result),
            "shadow_comparison": shadow_comparison,
            "related_signals": self._related_signals(signals, trimmed_query, capability),
            "related_events": self._related_events(events, trimmed_query, capability),
        }

    def _search_snapshot(self, result: Dict[str, Any]) -> Dict[str, Any]:
        payload = result.get("raw_response") or {}
        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        top_hits = []
        if isinstance(hits, list):
            for hit in hits[:5]:
                if not isinstance(hit, dict):
                    top_hits.append(str(hit))
                    continue
                label = (
                    hit.get("title")
                    or hit.get("name")
                    or hit.get("id")
                    or hit.get("objectID")
                    or str(hit)
                )
                top_hits.append(str(label))
        return {
            "index_name": result.get("index_name"),
            "status_code": int(result.get("status_code", 0) or 0),
            "results_count": int(result.get("results_count", 0) or 0),
            "latency_ms": round(float(result.get("latency_ms", 0.0) or 0.0), 2),
            "top_hits": top_hits,
            "error": payload.get("detail") or payload.get("error"),
        }

    def _find_shadow_comparison(self, shadow_test: Dict[str, Any], query: str) -> Dict[str, Any] | None:
        for comparison in shadow_test.get("comparisons", []):
            if str(comparison.get("query")) == query:
                return comparison
        return None

    def _triage_query(
        self,
        *,
        query: str,
        baseline_result: Dict[str, Any],
        candidate_result: Dict[str, Any],
        shadow_comparison: Dict[str, Any] | None,
    ) -> tuple[str, str]:
        baseline_status = int(baseline_result.get("status_code", 0) or 0)
        candidate_status = int(candidate_result.get("status_code", 0) or 0)
        baseline_count = int(baseline_result.get("results_count", 0) or 0)
        candidate_count = int(candidate_result.get("results_count", 0) or 0)

        if baseline_status >= 500 or candidate_status >= 500:
            return (
                "backend-error",
                f"The search backend returned an error while inspecting '{query}'. Review the raw response and backend health first.",
            )
        if baseline_count == 0 and candidate_count == 0:
            return (
                "still-zero",
                f"Both baseline and candidate still return zero results for '{query}', so the issue is still reproducible.",
            )
        if candidate_count > baseline_count:
            return (
                "candidate-improves",
                f"The candidate returns more results than baseline for '{query}'. Verify relevance and then consider canary promotion.",
            )
        if candidate_count < baseline_count:
            return (
                "candidate-regresses",
                f"The candidate returns fewer results than baseline for '{query}', so promotion should stay blocked.",
            )
        if shadow_comparison and str(shadow_comparison.get("delta", {}).get("outcome")) == "candidate-improves":
            return (
                "shadow-improves",
                f"Shadow replay suggests the candidate improves '{query}' while holding the same live-visible behavior.",
            )
        return (
            "steady",
            f"Baseline and candidate behave similarly for '{query}'. Use signals, latency, and business guardrails to decide the next step.",
        )

    def _related_signals(
        self,
        signals: List[Dict[str, Any]],
        query: str | None,
        capability: str,
    ) -> List[Dict[str, Any]]:
        related = []
        for signal in reversed(signals):
            signal_query = str(signal.get("query") or "").strip()
            signal_capability = str(signal.get("capability") or "unknown")
            if query and signal_query == query:
                related.append(self._signal_preview(signal))
                continue
            if signal_capability == capability:
                related.append(self._signal_preview(signal))
        return related[:8]

    def _signal_preview(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "signal_type": signal.get("signal_type") or signal.get("type"),
            "severity": signal.get("severity", "info"),
            "capability": signal.get("capability", "unknown"),
            "query": signal.get("query"),
            "origin": signal.get("signal_origin", "unknown"),
            "created_at": signal.get("created_at"),
            "summary": signal.get("summary"),
        }

    def _related_events(
        self,
        events: List[Dict[str, Any]],
        query: str | None,
        capability: str,
    ) -> List[Dict[str, Any]]:
        related = []
        for event in reversed(events):
            event_query = str(event.get("query") or "").strip()
            event_capability = str(event.get("capability") or "unknown")
            if query and event_query == query:
                related.append(self._event_preview(event))
                continue
            if event_capability == capability:
                related.append(self._event_preview(event))
        return related[:8]

    def _event_preview(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "source_type": event.get("source_type"),
            "event_type": event.get("event_type"),
            "capability": event.get("capability"),
            "query": event.get("query"),
            "origin": event.get("event_origin") or event.get("metadata", {}).get("event_origin") or "unknown",
            "created_at": event.get("created_at"),
        }

    def _build_incident_feed(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        feed = []
        for signal in reversed(signals[-12:]):
            feed.append(
                {
                    "signal_type": signal.get("signal_type") or signal.get("type"),
                    "severity": signal.get("severity", "info"),
                    "capability": signal.get("capability", "unknown"),
                    "query": signal.get("query"),
                    "origin": signal.get("signal_origin", "unknown"),
                    "created_at": signal.get("created_at"),
                    "summary": signal.get("summary") or "No summary attached.",
                }
            )
        return feed

    def _apply_operator_query_override(
        self,
        incident_packet: Dict[str, Any],
        operator_query: str | None,
    ) -> Dict[str, Any]:
        query = (operator_query or "").strip()
        if not query:
            return incident_packet

        packet = deepcopy(incident_packet)
        eval_dataset = packet.setdefault("runbook", {}).setdefault("eval_dataset", {})
        incident_queries = list(eval_dataset.get("incident_queries", []))
        if incident_queries:
            incident_queries[0] = query
        else:
            incident_queries = [query]
        eval_dataset["incident_queries"] = incident_queries
        packet["operator_query"] = query
        return packet

    def _approval_gate_message(self, approval_required: bool, latest_approval: Dict[str, Any] | None) -> str:
        if not approval_required:
            return "This change is eligible for policy-based auto approval."
        if latest_approval is None:
            return "Human approval is required after reviewing business impact and business guardrails."
        if latest_approval.get("decision") == "approved":
            return "Human approval has been recorded. The rollout can move to the release gate."
        if latest_approval.get("decision") == "changes-requested":
            return "Changes were requested before approval. Update the runbook or fix proposal first."
        if latest_approval.get("decision") == "rejected":
            return "The release was rejected. Do not promote until the incident plan changes."
        return "Human approval state is present but not yet promotable."

    def _build_business_impact(
        self,
        incident_packet: Dict[str, Any],
        controlled_release_packet: Dict[str, Any],
    ) -> Dict[str, Any]:
        diagnosis = incident_packet["diagnosis"]
        query = str(incident_packet["runbook"]["eval_dataset"]["incident_queries"][0] or "unknown-query")
        capability = diagnosis["affected_capability"]
        severity = diagnosis["severity"]
        risk_level = controlled_release_packet["source_incident"]["risk_level"]

        customer_effects = [
            f"Users searching for '{query}' may receive no useful results.",
            f"The affected capability is '{capability}', so discovery quality is degraded before any backend outage occurs.",
        ]

        business_effects = [
            "Reduced discovery can lower click-through, conversion, and trust for affected searches.",
            "Catalog gaps or weak synonyms can hide inventory that should otherwise be discoverable.",
            "Shipping a bad fix without approval could widen the zero-result problem to more traffic.",
        ]

        return {
            "severity": severity,
            "risk_level": risk_level,
            "summary": diagnosis["impact_summary"],
            "customer_effects": customer_effects,
            "business_effects": business_effects,
            "guardrails": incident_packet["evaluation"]["business_guardrails"],
            "approval_context": controlled_release_packet["approval"]["rationale"],
        }

    def _build_stage_statuses(
        self,
        signals: List[Dict[str, Any]],
        incident_packet: Dict[str, Any],
        controlled_release_packet: Dict[str, Any],
        shadow_test: Dict[str, Any],
        temporal: Dict[str, Any],
        latest_approval: Dict[str, Any] | None,
    ) -> List[Dict[str, str]]:
        approval_status = "pending"
        if latest_approval:
            approval_status = latest_approval.get("decision", "pending")

        observe_status = "baseline-ready"
        if shadow_test.get("summary", {}).get("shadow_ready"):
            observe_status = "ready"
        elif shadow_test.get("summary", {}).get("shadow_status") in {"candidate-index-missing", "candidate-errors"}:
            observe_status = "planned"

        return [
            {"stage": "1 Detect", "status": "active" if signals else "idle"},
            {"stage": "2 Diagnose", "status": "ready" if incident_packet else "idle"},
            {"stage": "3 Runbook", "status": "ready" if incident_packet.get("runbook") else "idle"},
            {"stage": "4 Evaluate", "status": incident_packet.get("evaluation", {}).get("status", "idle")},
            {"stage": "5 Approve", "status": approval_status},
            {
                "stage": "6 Release",
                "status": temporal.get("release_phase")
                or controlled_release_packet.get("release", {}).get("current_phase", "idle"),
            },
            {"stage": "7 Observe", "status": observe_status},
            {"stage": "8 Learn", "status": "candidate"},
        ]
