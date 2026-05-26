from __future__ import annotations

from typing import List

from app.config import settings
from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.base import RLMIncidentContext
from app.diagnosis.agents.helpers import metric_value
from app.services.rlm_models import CodeActStep
from app.services.rlm_models import RLMSubtaskResult


class MetricImpactAgent(BaseRLMSubtask):
    key = "metric_impact"
    title = "Metric Impact"
    focus = "Quantify business and technical impact through counters, latency, and rollout guardrails."
    evidence_sources = ("controlled_release_packet", "prometheus_snapshot", "shadow_test", "traffic_router")

    async def analyze(self, context: RLMIncidentContext) -> RLMSubtaskResult:
        observation = context.controlled_release_packet.get("observation", {})
        metrics = observation.get("baseline_metrics", [])
        metric_map = {
            str(metric.get("name")): metric
            for metric in metrics
        }

        zero_total = metric_value(metric_map, "zero_result_queries_total")
        latency_seconds = metric_value(metric_map, "search_p95_latency_seconds")
        signal_total = metric_value(metric_map, "signals_total")
        latency_threshold_seconds = settings.LATENCY_THRESHOLD_MS / 1000.0

        impacts: List[str] = []
        if zero_total is not None and zero_total > 0:
            impacts.append(f"Zero-result queries are currently elevated at {zero_total:.0f} total observations.")
        else:
            impacts.append("Zero-result evidence is not elevated in the current counter snapshot.")

        if latency_seconds is None:
            impacts.append("Latency evidence is unavailable, so rollout should rely on guardrail checks before promotion.")
        elif latency_seconds > latency_threshold_seconds:
            impacts.append(
                f"P95 latency is above threshold at {latency_seconds:.2f}s versus the {latency_threshold_seconds:.2f}s budget."
            )
        else:
            impacts.append(
                f"P95 latency is currently within threshold at {latency_seconds:.2f}s."
            )

        if signal_total is not None:
            impacts.append(f"The detector pipeline has emitted {signal_total:.0f} total signals in this process lifetime.")

        shadow_summary = context.shadow_test_report.get("summary", {})
        guardrail_status = "pass"
        if not shadow_summary.get("shadow_ready"):
            guardrail_status = "caution"
        if int(shadow_summary.get("regressed_queries", 0) or 0) > 0:
            guardrail_status = "fail"

        summary = (
            f"Primary metric pressure is on zero-result behavior for '{context.incident_query}'. "
            f"Rollout guardrail status is '{guardrail_status}'."
        )

        return self._result(
            status="ok" if guardrail_status != "fail" else "warning",
            summary=summary,
            confidence="high" if metrics else "medium",
            evidence_window=self._window(
                {
                    "incident_query": context.incident_query,
                    "guardrail_status": guardrail_status,
                    "shadow_summary": {
                        "shadow_ready": shadow_summary.get("shadow_ready"),
                        "ready_for_canary": shadow_summary.get("ready_for_canary"),
                        "regressed_queries": shadow_summary.get("regressed_queries"),
                    },
                    "metrics_seen": sorted(metric_map.keys()),
                }
            ),
            codeact_steps=[
                CodeActStep(
                    name="telemetry-scan",
                    status="ok" if metrics else "warning",
                    summary="Read Prometheus-backed and in-process telemetry metrics from the controlled release packet.",
                    output={
                        "metric_names": sorted(metric_map.keys()),
                        "guardrail_status": guardrail_status,
                    },
                ),
                CodeActStep(
                    name="shadow-guardrails",
                    status="ok",
                    summary="Compared shadow replay readiness with canary guardrails.",
                    output={
                        "shadow_summary": shadow_summary,
                        "traffic_router": {
                            "release_phase": context.traffic_router_status.get("release_phase"),
                            "live_candidate_percent": context.traffic_router_status.get("live_candidate_percent"),
                            "blocked_reason": context.traffic_router_status.get("blocked_reason"),
                        },
                    },
                ),
            ],
            findings={
                "guardrail_status": guardrail_status,
                "metric_impact": impacts,
                "zero_result_queries_total": zero_total,
                "search_p95_latency_seconds": latency_seconds,
                "signals_total": signal_total,
                "traffic_blocked_reason": context.traffic_router_status.get("blocked_reason"),
            },
            recommended_actions=[
                "Keep zero-result rate as the first business guardrail before any promotion.",
                "Do not promote if shadow replay shows regressed queries or if latency crosses the threshold.",
            ],
        )
