from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any
from typing import Dict
from typing import List

from app.state.feedback import add_watchlist_query
from app.state.feedback import get_approval_policy
from app.state.feedback import get_automation_policy
from app.state.feedback import get_effective_automation_policy
from app.state.feedback import get_feedback_state
from app.state.feedback import get_incident_automation_override
from app.state.feedback import list_incident_outcomes
from app.state.feedback import save_incident_outcome
from app.state.feedback import set_manual_approval_capability
from app.state.feedback import set_threshold
from app.state.feedback import update_automation_metadata

_PHASE_SEQUENCE = {
    "shadow": "canary-5",
    "canary-5": "canary-25",
    "canary-25": "promote-100",
    "promote-100": "completed",
}


class FeedbackAutomationService:
    """Persist learning state and evaluate policy-driven rollout automation."""

    def evaluate(
        self,
        *,
        incident_packet: Dict[str, Any],
        controlled_release_packet: Dict[str, Any],
        shadow_test: Dict[str, Any],
        current_phase: str,
        approval: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        state = get_feedback_state()
        thresholds = state.get("thresholds", {})
        approval_policy = get_approval_policy()
        incident_id = str(incident_packet.get("incident_id") or "")
        global_automation_policy = get_automation_policy()
        automation_policy = get_effective_automation_policy(incident_id)
        incident_override = get_incident_automation_override(incident_id)

        query = self._incident_query(incident_packet)
        capability = str(incident_packet.get("diagnosis", {}).get("affected_capability", "unknown"))
        severity = str(incident_packet.get("diagnosis", {}).get("severity", "info"))
        signal_type = str(incident_packet.get("diagnosis", {}).get("signal_type", "unknown"))

        watchlist_updates: List[str] = []
        if add_watchlist_query(
            query,
            capability=capability,
            severity=severity,
            synthetic=self._looks_synthetic(query),
        ):
            watchlist_updates.append(query)

        guardrail_issues = self._guardrail_issues(
            thresholds=thresholds,
            controlled_release_packet=controlled_release_packet,
            shadow_test=shadow_test,
        )
        guardrail_status = "pass" if not guardrail_issues else "fail"
        approval_decision = str((approval or {}).get("decision", "pending")).lower()

        auto_action = {
            "type": "none",
            "target_phase": None,
            "reason": None,
        }
        if automation_policy.get("enabled", True):
            auto_action = self._auto_action(
                current_phase=current_phase,
                approval_decision=approval_decision,
                guardrail_status=guardrail_status,
                guardrail_issues=guardrail_issues,
                shadow_summary=shadow_test.get("summary", {}),
                automation_policy=automation_policy,
            )

        threshold_updates, policy_updates = self._maybe_record_outcome_and_tune(
            incident_packet=incident_packet,
            current_phase=current_phase,
            auto_action=auto_action,
            guardrail_status=guardrail_status,
            signal_type=signal_type,
            capability=capability,
            query=query,
        )

        update_automation_metadata(
            last_guardrail_status=guardrail_status,
            last_action=auto_action["type"] if auto_action["type"] != "none" else None,
        )

        return {
            "feedback_state": state,
            "approval_policy": approval_policy,
            "global_automation_policy": global_automation_policy,
            "effective_automation_policy": automation_policy,
            "incident_override": incident_override,
            "guardrail_status": guardrail_status,
            "guardrail_issues": guardrail_issues,
            "watchlist_updates": watchlist_updates,
            "auto_action": auto_action,
            "threshold_updates": threshold_updates,
            "policy_updates": policy_updates,
        }

    def _incident_query(self, incident_packet: Dict[str, Any]) -> str:
        incident_queries = (
            incident_packet.get("runbook", {})
            .get("eval_dataset", {})
            .get("incident_queries", [])
        )
        if incident_queries:
            return str(incident_queries[0] or "unknown-query")
        return "unknown-query"

    def _looks_synthetic(self, query: str) -> bool:
        normalized = str(query or "").strip().lower()
        return not normalized or normalized == "unknown-query" or "zzzz" in normalized or "test" in normalized

    def _metrics_by_name(self, controlled_release_packet: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        metrics = controlled_release_packet.get("observation", {}).get("baseline_metrics", [])
        return {
            str(metric.get("name")): deepcopy(metric)
            for metric in metrics
        }

    def _guardrail_issues(
        self,
        *,
        thresholds: Dict[str, Any],
        controlled_release_packet: Dict[str, Any],
        shadow_test: Dict[str, Any],
    ) -> List[str]:
        metrics = self._metrics_by_name(controlled_release_packet)
        shadow_summary = shadow_test.get("summary", {})
        issues: List[str] = []

        p95_latency = metrics.get("search_p95_latency_seconds", {}).get("value")
        latency_ceiling = float(thresholds.get("search_p95_latency_seconds_ceiling", 15.0))
        if isinstance(p95_latency, (int, float)) and p95_latency > latency_ceiling:
            issues.append(
                f"P95 latency {p95_latency:.2f}s exceeded the automation ceiling of {latency_ceiling:.2f}s."
            )

        active_signals = metrics.get("active_signals", {}).get("value")
        max_active_signals = int(thresholds.get("max_active_signals", 10))
        if isinstance(active_signals, (int, float)) and active_signals > max_active_signals:
            issues.append(
                f"Active signals {int(active_signals)} exceeded the automation ceiling of {max_active_signals}."
            )

        zero_result_total = metrics.get("zero_result_queries_total", {}).get("value")
        max_zero_result_total = int(thresholds.get("max_zero_result_total", 3))
        if isinstance(zero_result_total, (int, float)) and zero_result_total > max_zero_result_total:
            issues.append(
                f"Zero-result volume {int(zero_result_total)} exceeded the automation ceiling of {max_zero_result_total}."
            )

        max_shadow_regressions = int(thresholds.get("max_shadow_regressions", 0))
        regressed_queries = int(shadow_summary.get("regressed_queries", 0) or 0)
        if regressed_queries > max_shadow_regressions:
            issues.append(
                f"Shadow replay regressed {regressed_queries} queries, above the allowed {max_shadow_regressions}."
            )

        if int(shadow_summary.get("candidate_unavailable_queries", 0) or 0) > 0:
            issues.append("Candidate replay returned unavailable errors for at least one query.")

        return issues

    def _auto_action(
        self,
        *,
        current_phase: str,
        approval_decision: str,
        guardrail_status: str,
        guardrail_issues: List[str],
        shadow_summary: Dict[str, Any],
        automation_policy: Dict[str, Any],
    ) -> Dict[str, Any]:
        if guardrail_status == "fail" and automation_policy.get("auto_rollback_enabled", True):
            if current_phase in {"canary-5", "canary-25", "promote-100", "completed"}:
                return {
                    "type": "rollback",
                    "target_phase": "rollback",
                    "reason": "; ".join(guardrail_issues),
                }

        if not automation_policy.get("auto_promote_enabled", True):
            return {"type": "none", "target_phase": None, "reason": None}

        if approval_decision != "approved":
            return {"type": "none", "target_phase": None, "reason": "Awaiting approval."}

        if not bool(shadow_summary.get("shadow_ready", False)):
            return {"type": "none", "target_phase": None, "reason": "Shadow replay is not ready."}

        if guardrail_status != "pass":
            return {"type": "none", "target_phase": None, "reason": "; ".join(guardrail_issues)}

        target_phase = _PHASE_SEQUENCE.get(current_phase)
        if not target_phase:
            return {"type": "none", "target_phase": None, "reason": None}
        return {
            "type": "advance-release",
            "target_phase": target_phase,
            "reason": f"Automation guardrails are green for phase {current_phase}.",
        }

    def _maybe_record_outcome_and_tune(
        self,
        *,
        incident_packet: Dict[str, Any],
        current_phase: str,
        auto_action: Dict[str, Any],
        guardrail_status: str,
        signal_type: str,
        capability: str,
        query: str,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        outcome_status = None
        if current_phase == "completed" or auto_action.get("target_phase") == "completed":
            outcome_status = "completed"
        elif current_phase == "rollback" or auto_action.get("target_phase") == "rollback":
            outcome_status = "rolled-back"

        if outcome_status is None:
            return [], []

        record = {
            "incident_id": incident_packet.get("incident_id"),
            "outcome_status": outcome_status,
            "signal_type": signal_type,
            "capability": capability,
            "query": query,
            "guardrail_status": guardrail_status,
            "release_phase": auto_action.get("target_phase") or current_phase,
        }
        saved = save_incident_outcome(record)
        if not saved:
            return [], []
        return self._self_tune_from_outcomes(signal_type=signal_type, capability=capability)

    def _self_tune_from_outcomes(
        self,
        *,
        signal_type: str,
        capability: str,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        outcomes = list_incident_outcomes(limit=40)
        relevant = [
            outcome for outcome in outcomes
            if outcome.get("signal_type") == signal_type or outcome.get("capability") == capability
        ]
        status_counts = Counter(str(item.get("outcome_status", "unknown")) for item in relevant)

        threshold_updates: List[Dict[str, Any]] = []
        policy_updates: List[Dict[str, Any]] = []

        rolled_back = status_counts.get("rolled-back", 0)
        completed = status_counts.get("completed", 0)

        if rolled_back >= 2 and set_manual_approval_capability(capability, True):
            policy_updates.append(
                {
                    "capability": capability,
                    "action": "manual-approval-required",
                    "reason": "Repeated rollback outcomes increased approval strictness.",
                }
            )

        state = get_feedback_state()
        thresholds = state.get("thresholds", {})

        if signal_type == "zero_result_cluster":
            current_threshold = int(thresholds.get("zero_result_repeat_count", 3))
            if rolled_back > completed and current_threshold > 2:
                new_value = current_threshold - 1
                if set_threshold(
                    "zero_result_repeat_count",
                    new_value,
                    "Repeated rollback outcomes made zero-result detection more sensitive.",
                ):
                    threshold_updates.append(
                        {
                            "name": "zero_result_repeat_count",
                            "value": new_value,
                            "reason": "Repeated rollback outcomes made zero-result detection more sensitive.",
                        }
                    )
            elif completed >= 3 and current_threshold < 5:
                new_value = current_threshold + 1
                if set_threshold(
                    "zero_result_repeat_count",
                    new_value,
                    "Repeated successful outcomes reduced zero-result detector sensitivity to cut noise.",
                ):
                    threshold_updates.append(
                        {
                            "name": "zero_result_repeat_count",
                            "value": new_value,
                            "reason": "Repeated successful outcomes reduced detector noise.",
                        }
                    )

        if signal_type == "latency_spike" or capability == "search_api":
            current_latency = int(thresholds.get("request_latency_ms", 1000))
            if rolled_back > completed and current_latency > 500:
                new_latency = current_latency - 100
                if set_threshold(
                    "request_latency_ms",
                    new_latency,
                    "Repeated latency rollback outcomes tightened the request latency detector threshold.",
                ):
                    threshold_updates.append(
                        {
                            "name": "request_latency_ms",
                            "value": new_latency,
                            "reason": "Repeated latency rollback outcomes tightened the request latency detector threshold.",
                        }
                    )

        return threshold_updates, policy_updates
