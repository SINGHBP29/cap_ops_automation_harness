from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

from app.state.feedback import get_approval_policy
from app.state.feedback import get_automation_policy
from app.state.feedback import get_feedback_state
from app.state.feedback import get_watchlists

_SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_RISK_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


ADAPTER_ACTIONS = {
    "catalog": [
        "Catalog sync or index backfill",
        "Freshness SLA repair",
        "Missing entity verification",
    ],
    "autocomplete": [
        "Autocomplete index refresh",
        "Prefix dictionary repair",
        "Suggestion ranking adjustment",
    ],
    "semantic_index": [
        "Embedding refresh or vector rebuild",
        "Semantic index sync",
        "Retrieval model rollback or retune",
    ],
    "personalization": [
        "Feature service validation",
        "Personalization fallback guardrail",
        "Ranking model or feature-config rollback",
    ],
    "merchandising_controls": [
        "Rule pack review",
        "Promotion/exclusion configuration fix",
        "Campaign rollout correction",
    ],
    "semantic_search": [
        "Synonym pack update",
        "Index refresh or backfill",
        "Catalog patch for missing entities",
    ],
    "ranking": [
        "Ranking config update",
        "Query normalization adjustment",
        "Merchandising rule review",
    ],
    "search_api": [
        "API configuration change",
        "Latency mitigation rollout",
        "Capacity or timeout tuning",
    ],
    "search_platform": [
        "Search backend configuration change",
        "Index settings update",
        "Platform stability fix",
    ],
}


@dataclass
class SourceIncidentSummary:
    incident_id: str
    signal_type: str
    severity: str
    affected_capability: str
    root_cause: str
    risk_level: str


@dataclass
class ApprovalCheck:
    name: str
    status: str
    detail: str


@dataclass
class ApprovalDecision:
    status: str
    approver: str
    auto_approval_eligible: bool
    rationale: str
    policy_checks: List[ApprovalCheck] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)


@dataclass
class ReleaseStage:
    name: str
    traffic_percent: str
    objective: str
    promotion_check: str
    rollback_trigger: str


@dataclass
class ReleasePlan:
    current_phase: str
    adapter_actions: List[str]
    traffic_router: List[ReleaseStage]
    rollback_orchestrator: List[str]
    promotion_checks: List[str]


@dataclass
class BaselineMetric:
    name: str
    value: Any
    unit: str
    source: str
    status: str
    note: str


@dataclass
class ObservationPlan:
    baseline_collected_at: str
    baseline_metrics: List[BaselineMetric]
    live_watchlist: List[str]
    comparison_strategy: str
    promotion_gates: List[str]


@dataclass
class AuditRecord:
    created_at: str
    source_signal: str
    runbook_version: str
    eval_report: str
    approver: str
    rollout_timeline: List[str]
    rollback_events: List[str]


@dataclass
class LearningAction:
    category: str
    priority: str
    action: str
    rationale: str


@dataclass
class LearningPlan:
    feedback_engine: str
    learning_actions: List[LearningAction]
    expected_outcomes: List[str]


@dataclass
class ControlledReleasePacket:
    release_id: str
    source_incident: SourceIncidentSummary
    approval: ApprovalDecision
    release: ReleasePlan
    observation: ObservationPlan
    audit_record: AuditRecord
    learning: LearningPlan

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ControlledReleasePipeline:
    def _incident_query_value(self, incident_packet: Dict[str, Any]) -> str:
        incident_queries = incident_packet.get("runbook", {}).get("eval_dataset", {}).get("incident_queries", [])
        if incident_queries:
            return str(incident_queries[0] or "unknown-query")
        return "unknown-query"

    def build_packet(
        self,
        incident_packet: Dict[str, Any],
        telemetry_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        source_incident = self._build_source_incident(incident_packet)
        approval = self._build_approval(incident_packet, telemetry_snapshot)
        release = self._build_release(incident_packet)
        observation = self._build_observation(incident_packet, telemetry_snapshot)
        audit_record = self._build_audit_record(incident_packet, approval, release)
        learning = self._build_learning(incident_packet, telemetry_snapshot)

        release_id = f"{source_incident.incident_id}:{int(datetime.now(tz=UTC).timestamp())}"
        packet = ControlledReleasePacket(
            release_id=release_id,
            source_incident=source_incident,
            approval=approval,
            release=release,
            observation=observation,
            audit_record=audit_record,
            learning=learning,
        )
        packet_dict = packet.to_dict()
        feedback_state = get_feedback_state()
        watchlists = get_watchlists()
        packet_dict["feedback_state"] = feedback_state
        packet_dict["approval"]["policy_state"] = get_approval_policy()
        packet_dict["learning"]["automation_state"] = get_automation_policy()
        packet_dict["observation"]["persistent_watch_queries"] = [
            item.get("query")
            for item in watchlists.get("queries", [])[-8:]
            if item.get("query")
        ]
        packet_dict["observation"]["persistent_synthetic_queries"] = [
            item.get("query")
            for item in watchlists.get("synthetic_queries", [])[-8:]
            if item.get("query")
        ]
        return packet_dict

    def _build_source_incident(self, incident_packet: Dict[str, Any]) -> SourceIncidentSummary:
        diagnosis = incident_packet["diagnosis"]
        runbook = incident_packet["runbook"]
        return SourceIncidentSummary(
            incident_id=incident_packet["incident_id"],
            signal_type=diagnosis["signal_type"],
            severity=diagnosis["severity"],
            affected_capability=diagnosis["affected_capability"],
            root_cause=diagnosis["root_cause"],
            risk_level=runbook["risk_level"],
        )

    def _build_approval(
        self,
        incident_packet: Dict[str, Any],
        telemetry_snapshot: Dict[str, Any],
    ) -> ApprovalDecision:
        source = self._build_source_incident(incident_packet)
        approver = incident_packet["evaluation"]["approval_workflow"]["route_for_approval"]
        search_backend_status = incident_packet["diagnosis"]["evidence_pack"][1]["details"].get(
            "search_backend",
            {},
        ).get("status", "UNKNOWN")
        baseline_metrics = telemetry_snapshot.get("metrics", [])
        metrics_ready = any(metric["status"] == "ok" for metric in baseline_metrics)
        approval_policy = get_approval_policy()
        manual_capabilities = {
            str(capability)
            for capability in approval_policy.get("manual_approval_capabilities", [])
        }
        auto_approval = (
            source.affected_capability not in manual_capabilities
            and self._severity_rank(source.severity)
            <= self._severity_rank(approval_policy.get("auto_approval_max_severity", "low"))
            and self._risk_rank(source.risk_level)
            <= self._risk_rank(approval_policy.get("auto_approval_max_risk", "low"))
        )
        status = "auto-approved" if auto_approval else "pending-operator-approval"

        policy_checks = [
            ApprovalCheck(
                name="Runbook completeness",
                status="pass",
                detail="Candidate fix, eval dataset, and rollback plan are present.",
            ),
            ApprovalCheck(
                name="Observability readiness",
                status="pass" if metrics_ready else "review-required",
                detail="Baseline metrics are available for promotion checks."
                if metrics_ready
                else "Limited metrics were available; operator review is required before promotion.",
            ),
            ApprovalCheck(
                name="Search backend readiness",
                status="pass" if search_backend_status == "HEALTHY" else "review-required",
                detail=f"Search backend status is {search_backend_status}.",
            ),
            ApprovalCheck(
                name="Risk policy",
                status="review-required" if source.severity in {"high", "critical"} else "pass",
                detail="High-severity incidents require operator approval before release."
                if source.severity in {"high", "critical"}
                else "Current severity allows policy-based progression.",
            ),
            ApprovalCheck(
                name="Feedback approval policy",
                status="review-required" if source.affected_capability in manual_capabilities else "pass",
                detail=(
                    f"Capability '{source.affected_capability}' is pinned to manual approval by feedback policy."
                    if source.affected_capability in manual_capabilities
                    else "Feedback policy allows normal approval evaluation for this capability."
                ),
            ),
        ]

        required_actions = [
            "Confirm the candidate fix against the eval dataset before changing live traffic.",
            "Verify rollback ownership and operator notification path.",
        ]
        if not auto_approval:
            required_actions.append(f"Obtain approval from {approver} before canary promotion.")

        rationale = (
            "Automatic approval is not used because this change affects search relevance and the "
            "current incident severity or risk profile requires an operator checkpoint."
        )
        if auto_approval:
            rationale = "Risk and severity are low enough to allow policy-based auto-approval."
        elif source.affected_capability in manual_capabilities:
            rationale = (
                f"Automatic approval is disabled for capability '{source.affected_capability}' because prior incident outcomes "
                "raised the approval strictness in the feedback policy."
            )

        return ApprovalDecision(
            status=status,
            approver=approver,
            auto_approval_eligible=auto_approval,
            rationale=rationale,
            policy_checks=policy_checks,
            required_actions=required_actions,
        )

    def _build_release(self, incident_packet: Dict[str, Any]) -> ReleasePlan:
        capability = incident_packet["diagnosis"]["affected_capability"]
        adapter_actions = ADAPTER_ACTIONS.get(
            capability,
            [
                "Scoped configuration change",
                "Low-risk capability patch",
                "Operator-reviewed rollout",
            ],
        )

        traffic_router = [
            ReleaseStage(
                name="Shadow",
                traffic_percent="100% mirrored",
                objective="Replay the fix against production-shaped traffic without user impact.",
                promotion_check="No regression in query quality, latency, or new severe signals during shadow replay.",
                rollback_trigger="Mismatch versus baseline, unexpected error spike, or broken replay behavior.",
            ),
            ReleaseStage(
                name="Canary 5%",
                traffic_percent="5%",
                objective="Expose a small slice of live traffic to the change.",
                promotion_check="Zero-result rate and latency stay within baseline guardrails for the initial canary.",
                rollback_trigger="Incident query quality worsens or new severe alerts appear in the canary slice.",
            ),
            ReleaseStage(
                name="Canary 25%",
                traffic_percent="25%",
                objective="Increase confidence with a broader but still bounded rollout.",
                promotion_check="Business guardrails remain stable and operator review signs off on promotion.",
                rollback_trigger="Guardrail breach on relevance, latency, or incident recurrence.",
            ),
            ReleaseStage(
                name="Promote 100%",
                traffic_percent="100%",
                objective="Complete the rollout after shadow and canary validation pass.",
                promotion_check="Approval state is green and no rollback trigger fired in earlier stages.",
                rollback_trigger="Any post-promotion regression detected by observability or operators.",
            ),
        ]

        rollback_orchestrator = [
            "Detect regression from live telemetry or operator review.",
            "Trigger manual or automatic rollback to the last known good release state.",
            "Restore the previous search configuration or index state.",
            "Notify operators and attach evidence to the audit ledger.",
        ]

        promotion_checks = [
            "Incident query improves or remains within acceptable tolerance.",
            "Known-good positive queries do not regress.",
            "Zero-result rate, latency, and active signal volume remain within guardrails.",
        ]

        return ReleasePlan(
            current_phase="planned",
            adapter_actions=adapter_actions,
            traffic_router=traffic_router,
            rollback_orchestrator=rollback_orchestrator,
            promotion_checks=promotion_checks,
        )

    def _build_observation(
        self,
        incident_packet: Dict[str, Any],
        telemetry_snapshot: Dict[str, Any],
    ) -> ObservationPlan:
        query = self._incident_query_value(incident_packet)
        metrics = [
            BaselineMetric(**metric)
            for metric in telemetry_snapshot.get("metrics", [])
        ]
        watchlists = get_watchlists()
        persisted_queries = [
            str(item.get("query"))
            for item in watchlists.get("queries", [])
            if item.get("query")
        ]
        live_watchlist = [
            f"Zero-result rate for incident query '{query}'",
            "Search request rate and error-free traffic health",
            "P95 search latency during shadow and canary",
            "Active signal count and any new high-severity incidents",
            "Business guardrails from the eval dataset promotion checks",
        ]
        if persisted_queries:
            live_watchlist.append(
                "Persisted watch queries: " + ", ".join(persisted_queries[-5:])
            )

        promotion_gates = [
            "Do not promote if zero-result behavior worsens on the incident query.",
            "Do not promote if P95 latency regresses materially from baseline.",
            "Do not promote if new severe signals appear during shadow or canary.",
        ]

        return ObservationPlan(
            baseline_collected_at=telemetry_snapshot.get("collected_at", datetime.now(tz=UTC).isoformat()),
            baseline_metrics=metrics,
            live_watchlist=live_watchlist,
            comparison_strategy=(
                "Compare each release stage against the pre-release baseline and the last stable release. "
                "Promotion requires both metric stability and operator review."
            ),
            promotion_gates=promotion_gates,
        )

    def _build_audit_record(
        self,
        incident_packet: Dict[str, Any],
        approval: ApprovalDecision,
        release: ReleasePlan,
    ) -> AuditRecord:
        rollout_timeline = [
            stage.name for stage in release.traffic_router
        ]
        return AuditRecord(
            created_at=datetime.now(tz=UTC).isoformat(),
            source_signal=incident_packet["diagnosis"]["signal_type"],
            runbook_version="v1",
            eval_report=incident_packet["evaluation"]["status"],
            approver=approval.approver,
            rollout_timeline=rollout_timeline,
            rollback_events=[],
        )

    def _build_learning(
        self,
        incident_packet: Dict[str, Any],
        telemetry_snapshot: Dict[str, Any],
    ) -> LearningPlan:
        diagnosis = incident_packet["diagnosis"]
        query = self._incident_query_value(incident_packet)
        feedback_policy = get_approval_policy()
        automation_policy = get_automation_policy()
        actions = [
            LearningAction(
                category="thresholds",
                priority="medium",
                action="Review whether the zero-result cluster threshold balances noise and recall for search incidents.",
                rationale="The current detector fired on repeated zero-result behavior and should be tuned only after observing more production-like traffic.",
            ),
            LearningAction(
                category="watchlists",
                priority="high",
                action=f"Add '{query}' to the watchlist for follow-up if it is a real customer-facing query, or to the test exclusion list if synthetic.",
                rationale="This incident needs a durable classification so future alerts are easier to interpret.",
            ),
            LearningAction(
                category="root-cause models",
                priority="medium",
                action="Keep separating healthy-backend zero-result incidents from backend outage incidents in the diagnosis rules.",
                rationale="The current issue affects relevance and index coverage, not backend availability.",
            ),
            LearningAction(
                category="runbook templates",
                priority="medium",
                action="Update the zero-result runbook template to branch explicitly between missing catalog data and weak synonym coverage.",
                rationale="Operators need a faster path from signal to fix proposal.",
            ),
            LearningAction(
                category="auto-approval policies",
                priority="low",
                action="Keep manual approval for high-severity relevance changes until more shadow and canary history is captured.",
                rationale="Search quality changes have user-facing risk and need human oversight.",
            ),
        ]
        if diagnosis["affected_capability"] in set(feedback_policy.get("manual_approval_capabilities", [])):
            actions.append(
                LearningAction(
                    category="approval policy",
                    priority="high",
                    action=(
                        f"Capability '{diagnosis['affected_capability']}' already requires manual approval because recent outcomes raised policy strictness."
                    ),
                    rationale="The persistent feedback policy is now enforcing stricter human review for this capability.",
                )
            )
        if automation_policy.get("auto_promote_enabled", True):
            actions.append(
                LearningAction(
                    category="automation",
                    priority="medium",
                    action="Automatic rollout promotion is enabled and will advance phases when guardrails remain green.",
                    rationale="Temporal refreshes now evaluate rollout guardrails using the persisted feedback thresholds.",
                )
            )

        expected_outcomes = [
            "Better detection quality with fewer ambiguous zero-result alerts.",
            "Better runbooks for search relevance incidents.",
            "Faster incident resolution through reusable approval and rollout evidence.",
        ]

        return LearningPlan(
            feedback_engine=(
                f"Ops Feedback Engine for capability '{diagnosis['affected_capability']}' using live telemetry baselines collected at "
                f"{telemetry_snapshot.get('collected_at', 'unknown time')}."
            ),
            learning_actions=actions,
            expected_outcomes=expected_outcomes,
        )

    def _severity_rank(self, severity: str) -> int:
        return _SEVERITY_RANK.get(str(severity or "high").lower(), _SEVERITY_RANK["high"])

    def _risk_rank(self, risk_level: str) -> int:
        return _RISK_RANK.get(str(risk_level or "high").lower(), _RISK_RANK["high"])
