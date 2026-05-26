from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


DEFAULT_POSITIVE_QUERIES = [
    "python",
    "learning python",
    "kafka",
]

NEGATIVE_CONTROL_QUERY = "zzzz-nonexistent-control"

CAPABILITY_OWNERS = {
    "catalog": {
        "primary_owner": "Catalog / Indexing owner",
        "secondary_owner": "Search platform owner",
        "approver": "Catalog lead / Search lead",
    },
    "autocomplete": {
        "primary_owner": "Search UX / Autocomplete owner",
        "secondary_owner": "Backend API owner",
        "approver": "Search lead / Product owner",
    },
    "semantic_index": {
        "primary_owner": "Semantic Search / ML owner",
        "secondary_owner": "Search / Indexing owner",
        "approver": "Search lead / ML lead",
    },
    "personalization": {
        "primary_owner": "Personalization owner",
        "secondary_owner": "ML platform owner",
        "approver": "Product lead / Search lead",
    },
    "merchandising_controls": {
        "primary_owner": "Merchandising / Search Rules owner",
        "secondary_owner": "Backend API owner",
        "approver": "Merchandising lead",
    },
    "semantic_search": {
        "primary_owner": "Search / Indexing owner",
        "secondary_owner": "Backend API owner",
        "approver": "Search lead / Merchandiser",
    },
    "ranking": {
        "primary_owner": "Ranking / Relevance owner",
        "secondary_owner": "Backend API owner",
        "approver": "Search lead / Merchandiser",
    },
    "search_api": {
        "primary_owner": "Backend API owner",
        "secondary_owner": "Platform owner",
        "approver": "Engineering lead",
    },
    "search_platform": {
        "primary_owner": "Search platform owner",
        "secondary_owner": "Infrastructure owner",
        "approver": "Engineering lead",
    },
}


@dataclass
class EvidenceItem:
    source: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Diagnosis:
    signal_type: str
    severity: str
    affected_capability: str
    root_cause: str
    confidence: str
    impact_summary: str
    evidence_pack: List[EvidenceItem] = field(default_factory=list)


@dataclass
class OwnerAssignment:
    primary_owner: str
    secondary_owner: str
    approver: str


@dataclass
class EvalDataset:
    positive_queries: List[str]
    incident_queries: List[str]
    negative_controls: List[str]
    success_criteria: List[str]


@dataclass
class Runbook:
    title: str
    candidate_fix: List[str]
    owner: OwnerAssignment
    eval_dataset: EvalDataset
    rollback_plan: List[str]
    risk_level: str
    evidence_summary: List[str]


@dataclass
class EvalCheck:
    name: str
    mode: str
    status: str
    objective: str
    pass_criteria: str


@dataclass
class ApprovalWorkflow:
    route_for_approval: str
    auto_approval_eligible: bool
    release_window: str
    approval_state: str


@dataclass
class Evaluation:
    status: str
    checks: List[EvalCheck]
    business_guardrails: List[str]
    approval_workflow: ApprovalWorkflow


@dataclass
class IncidentPacket:
    incident_id: str
    health_rating: str
    diagnosis: Diagnosis
    runbook: Runbook
    evaluation: Evaluation

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IntelligencePipeline:
    def __init__(self, positive_queries: Optional[List[str]] = None):
        self.positive_queries = positive_queries or list(DEFAULT_POSITIVE_QUERIES)

    def _incident_query_value(self, signal: Dict[str, Any]) -> str:
        return str(signal.get("query") or "unknown-query")

    def build_incident_packet(
        self,
        signals_report: Dict[str, Any],
        diagnostics_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        signal = self._select_signal(signals_report)
        diagnosis = self._build_diagnosis(signal, diagnostics_report)
        runbook = self._build_runbook(signal, diagnosis, diagnostics_report)
        evaluation = self._build_evaluation(signal, diagnosis, runbook)

        incident_query = self._incident_query_value(signal)
        packet = IncidentPacket(
            incident_id=f"{diagnosis.signal_type}:{incident_query}",
            health_rating=diagnostics_report.get("health_rating", "UNKNOWN"),
            diagnosis=diagnosis,
            runbook=runbook,
            evaluation=evaluation,
        )
        return packet.to_dict()

    def _select_signal(self, signals_report: Dict[str, Any]) -> Dict[str, Any]:
        recent_signals = signals_report.get("recent_signals", [])
        if not recent_signals:
            raise ValueError("No signals found. Generate or ingest a signal before building a runbook.")

        for signal in reversed(recent_signals):
            signal_type = signal.get("signal_type") or signal.get("type")
            if signal_type and signal_type != "test":
                return signal

        return recent_signals[-1]

    def _build_diagnosis(
        self,
        signal: Dict[str, Any],
        diagnostics_report: Dict[str, Any],
    ) -> Diagnosis:
        signal_type = signal.get("signal_type") or signal.get("type") or "unknown"
        severity = signal.get("severity", "info")
        capability = signal.get("capability") or self._infer_capability(signal_type)
        root_cause = self._infer_root_cause(signal_type, diagnostics_report)
        confidence = self._infer_confidence(signal_type, diagnostics_report)
        impact_summary = self._build_impact_summary(signal, capability, diagnostics_report)

        evidence_pack = [
            EvidenceItem(
                source="signal",
                summary=f"Signal '{signal_type}' detected for capability '{capability}'.",
                details=signal,
            ),
            EvidenceItem(
                source="diagnostics",
                summary="Current service health snapshot collected from the diagnostics endpoint.",
                details=diagnostics_report.get("services", {}),
            ),
            EvidenceItem(
                source="anomalies",
                summary="Anomalies correlated with the current incident.",
                details={"detected_anomalies": diagnostics_report.get("detected_anomalies", [])},
            ),
        ]

        return Diagnosis(
            signal_type=signal_type,
            severity=severity,
            affected_capability=capability,
            root_cause=root_cause,
            confidence=confidence,
            impact_summary=impact_summary,
            evidence_pack=evidence_pack,
        )

    def _build_runbook(
        self,
        signal: Dict[str, Any],
        diagnosis: Diagnosis,
        diagnostics_report: Dict[str, Any],
    ) -> Runbook:
        if diagnosis.signal_type == "zero_result_cluster":
            return self._build_zero_result_runbook(signal, diagnosis, diagnostics_report)

        owners = self._owner_for_capability(diagnosis.affected_capability)
        dataset = EvalDataset(
            positive_queries=list(self.positive_queries),
            incident_queries=[self._incident_query_value(signal)],
            negative_controls=[NEGATIVE_CONTROL_QUERY],
            success_criteria=[
                "The affected query no longer triggers the same incident signal.",
                "Known-good queries continue returning expected results.",
                "No new severe regressions appear in diagnostics or traces.",
            ],
        )
        return Runbook(
            title=f"Candidate runbook for {diagnosis.signal_type}",
            candidate_fix=[
                "Validate the incident is not synthetic or test-generated traffic.",
                "Inspect the latest diagnostics and trace evidence for the failing capability.",
                "Apply the smallest capability-specific fix that resolves the signal.",
            ],
            owner=owners,
            eval_dataset=dataset,
            rollback_plan=[
                "Revert the most recent configuration or data change tied to the failing capability.",
                "Re-run the smoke checks for /search, /signals, metrics, and traces.",
            ],
            risk_level="medium",
            evidence_summary=[
                diagnosis.root_cause,
                diagnosis.impact_summary,
                f"System health rating: {diagnostics_report.get('health_rating', 'UNKNOWN')}",
            ],
        )

    def _build_zero_result_runbook(
        self,
        signal: Dict[str, Any],
        diagnosis: Diagnosis,
        diagnostics_report: Dict[str, Any],
    ) -> Runbook:
        query = self._incident_query_value(signal)
        owners = self._owner_for_capability(diagnosis.affected_capability)
        dataset = EvalDataset(
            positive_queries=list(self.positive_queries),
            incident_queries=[query],
            negative_controls=[NEGATIVE_CONTROL_QUERY],
            success_criteria=[
                f"The query '{query}' returns expected hits if it is a real customer query.",
                "Known-good positive queries still return relevant results.",
                "The negative-control query still returns zero hits.",
                "Zero-result alert rate drops for legitimate search traffic.",
            ],
        )

        candidate_fix = [
            "Confirm whether the triggering query is synthetic test traffic or a real customer query.",
            "If the query is real, verify the expected documents exist in the source catalog.",
            "Check whether those documents are present in the Meilisearch index and backfill or reindex if missing.",
            "If documents exist but still do not match, add synonyms, aliases, or query normalization for the affected terms.",
            "Re-run the eval dataset and confirm the zero-result cluster no longer fires for legitimate queries.",
        ]

        rollback_plan = [
            "Snapshot current search index settings and synonym configuration before any change.",
            "Revert synonym, ranking, or normalization changes if relevance degrades.",
            "Restore the previous indexed dataset if reindexing causes unexpected regressions.",
            "Re-run search, signal, metrics, and trace smoke checks after rollback.",
        ]

        evidence_summary = [
            diagnosis.root_cause,
            diagnosis.impact_summary,
            f"Search backend status: {diagnostics_report.get('services', {}).get('search_backend', {}).get('status', 'UNKNOWN')}",
        ]

        return Runbook(
            title="Candidate runbook for zero-result search incident",
            candidate_fix=candidate_fix,
            owner=owners,
            eval_dataset=dataset,
            rollback_plan=rollback_plan,
            risk_level="medium",
            evidence_summary=evidence_summary,
        )

    def _build_evaluation(
        self,
        signal: Dict[str, Any],
        diagnosis: Diagnosis,
        runbook: Runbook,
    ) -> Evaluation:
        query = self._incident_query_value(signal)
        checks = [
            EvalCheck(
                name="Offline benchmark",
                mode="offline",
                status="planned",
                objective="Compare the candidate search behavior across the eval dataset before release.",
                pass_criteria="Incident query improves without regressing the known-good positive queries.",
            ),
            EvalCheck(
                name="Shadow replay",
                mode="shadow",
                status="planned",
                objective="Replay representative traffic or sampled queries in read-only mode.",
                pass_criteria="The new behavior matches or improves baseline relevance with no new severe incident signals.",
            ),
            EvalCheck(
                name="Latency check",
                mode="online-guardrail",
                status="planned",
                objective="Verify the fix does not create a material search latency regression.",
                pass_criteria="P95 latency stays within the current acceptable threshold for search traffic.",
            ),
            EvalCheck(
                name="Business guardrails",
                mode="guardrail",
                status="planned",
                objective="Protect core customer outcomes while the fix is evaluated.",
                pass_criteria="Zero-result rate, result relevance, and query success remain within acceptable bounds.",
            ),
            EvalCheck(
                name="Stats and significance",
                mode="analysis",
                status="planned",
                objective="Require enough observations before promoting a risky relevance change.",
                pass_criteria=f"Use enough volume on '{query}' and adjacent queries to justify rollout confidence.",
            ),
        ]

        business_guardrails = [
            "Do not increase the global zero-result rate for legitimate customer traffic.",
            "Do not degrade known-good positive queries in the eval dataset.",
            "Do not materially regress search latency or stability.",
        ]

        approval_workflow = ApprovalWorkflow(
            route_for_approval=runbook.owner.approver,
            auto_approval_eligible=False,
            release_window="Next low-risk release window after offline and shadow checks pass.",
            approval_state="pending-review",
        )

        status = "candidate" if diagnosis.severity in {"high", "critical"} else "proposed"
        return Evaluation(
            status=status,
            checks=checks,
            business_guardrails=business_guardrails,
            approval_workflow=approval_workflow,
        )

    def _infer_capability(self, signal_type: str) -> str:
        if signal_type == "zero_result_cluster":
            return "semantic_search"
        if signal_type in {"catalog_index_gap", "catalog_freshness_breach", "missing_products_cluster", "catalog_delta"}:
            return "catalog"
        if signal_type in {"autocomplete_zero_suggestions", "autocomplete_latency_spike", "autocomplete_relevance_regression", "autocomplete_fail"}:
            return "autocomplete"
        if signal_type in {"semantic_index_gap", "semantic_index_stale", "semantic_recall_drop", "vector_search_latency_spike"}:
            return "semantic_index"
        if signal_type in {"personalization_fallback_spike", "feature_service_degraded", "personalization_uplift_drop"}:
            return "personalization"
        if signal_type in {"pinning_failure", "exclusion_policy_violation", "merch_rule_conflict", "campaign_result_miss", "rule_diff", "rule_conflict", "policy_violation"}:
            return "merchandising_controls"
        if signal_type == "query_reformulation":
            return "ranking"
        if signal_type == "latency_spike":
            return "search_api"
        if signal_type == "search_api_failure":
            return "search_platform"
        return "unknown"

    def _infer_root_cause(
        self,
        signal_type: str,
        diagnostics_report: Dict[str, Any],
    ) -> str:
        if signal_type == "zero_result_cluster":
            search_backend = diagnostics_report.get("services", {}).get("search_backend", {})
            backend_status = search_backend.get("status")
            if backend_status == "HEALTHY":
                return (
                    "The search backend is healthy, so repeated zero-result queries most likely "
                    "point to index coverage gaps or weak search vocabulary rather than an outage."
                )
            return "Repeated zero-result queries indicate missing content, bad indexing, or a search backend issue."

        if signal_type == "latency_spike":
            return "Search requests exceeded the acceptable latency threshold."

        if signal_type == "search_api_failure":
            return "The search backend returned server-side errors to the application."

        if signal_type in {"catalog_index_gap", "catalog_freshness_breach", "missing_products_cluster"}:
            return "Catalog availability or freshness drift is preventing expected content from appearing in search."

        if signal_type in {"autocomplete_zero_suggestions", "autocomplete_latency_spike", "autocomplete_relevance_regression"}:
            return "Autocomplete quality or responsiveness regressed for common prefixes."

        if signal_type in {"semantic_index_gap", "semantic_index_stale", "semantic_recall_drop", "vector_search_latency_spike"}:
            return "The semantic retrieval layer is stale, incomplete, or underperforming versus its benchmark."

        if signal_type in {"personalization_fallback_spike", "feature_service_degraded", "personalization_uplift_drop"}:
            return "Personalization is falling back, missing features, or no longer delivering the expected uplift."

        if signal_type in {"pinning_failure", "exclusion_policy_violation", "merch_rule_conflict", "campaign_result_miss"}:
            return "Merchandising rules are conflicting, missing expected promoted items, or violating exclusion policy."

        if signal_type == "query_reformulation":
            return "Users are reformulating queries, which suggests the relevance or ranking strategy is weak."

        return "The current signal does not have a specialized root-cause mapping yet."

    def _infer_confidence(
        self,
        signal_type: str,
        diagnostics_report: Dict[str, Any],
    ) -> str:
        if signal_type == "zero_result_cluster":
            signals = diagnostics_report.get("signals_summary", {}).get("by_type", {})
            if signals.get("zero_result_cluster", 0) > 0:
                return "high"
        if signal_type in {
            "catalog_index_gap",
            "catalog_freshness_breach",
            "missing_products_cluster",
            "autocomplete_zero_suggestions",
            "semantic_index_gap",
            "semantic_index_stale",
            "semantic_recall_drop",
            "feature_service_degraded",
            "pinning_failure",
            "exclusion_policy_violation",
        }:
            return "high"
        if signal_type in {"latency_spike", "search_api_failure", "query_reformulation"}:
            return "medium"
        return "low"

    def _build_impact_summary(
        self,
        signal: Dict[str, Any],
        capability: str,
        diagnostics_report: Dict[str, Any],
    ) -> str:
        query = signal.get("query")
        if capability == "semantic_search" and query:
            count = diagnostics_report.get("signals_summary", {}).get("common_queries", {}).get(query, 0)
            return (
                f"The capability '{capability}' is impacted because the query '{query}' has repeated "
                f"zero-result outcomes and appears {count} time(s) in the current signal summary."
            )
        return f"The capability '{capability}' is implicated by the current signal and diagnostics correlation."

    def _owner_for_capability(self, capability: str) -> OwnerAssignment:
        owner = CAPABILITY_OWNERS.get(
            capability,
            {
                "primary_owner": "Application owner",
                "secondary_owner": "Platform owner",
                "approver": "Engineering lead",
            },
        )
        return OwnerAssignment(**owner)
