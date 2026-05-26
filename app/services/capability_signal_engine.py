from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

from app.config import settings
from app.kafka_client.producer import publish_signal
from app.models.capability_signal import CapabilitySignalEvent
from app.services.ops_ledger import store_signal
from app.state.feedback import get_threshold


@dataclass(frozen=True)
class CapabilityRule:
    signal_type: str
    summary: str
    threshold_hint: str
    severity: str


RULE_CATALOG: Dict[str, List[CapabilityRule]] = {
    "semantic_search": [
        CapabilityRule(
            signal_type="zero_result_cluster",
            summary="Detect repeated zero-result behavior for the same or equivalent query pattern.",
            threshold_hint=f"repeat_count >= {settings.ZERO_RESULT_THRESHOLD} and results_count == 0",
            severity="high",
        ),
        CapabilityRule(
            signal_type="query_reformulation",
            summary="Detect when users reformulate queries because the first attempt was not satisfactory.",
            threshold_hint="reformulation_count > 0",
            severity="medium",
        ),
    ],
    "catalog": [
        CapabilityRule(
            signal_type="catalog_index_gap",
            summary="Detect when the indexed document count drifts materially from the source catalog.",
            threshold_hint="index_count/source_count < 0.95",
            severity="high",
        ),
        CapabilityRule(
            signal_type="catalog_freshness_breach",
            summary="Detect when catalog freshness exceeds the configured SLA window.",
            threshold_hint="freshness_age_minutes > freshness_sla_minutes",
            severity="high",
        ),
        CapabilityRule(
            signal_type="missing_products_cluster",
            summary="Detect when expected SKUs or products are missing from the search index.",
            threshold_hint="missing_expected_count > 0",
            severity="high",
        ),
    ],
    "autocomplete": [
        CapabilityRule(
            signal_type="autocomplete_zero_suggestions",
            summary="Detect when autocomplete returns no suggestions for a common prefix or synthetic probe.",
            threshold_hint="suggestion_count == 0 and common_prefix == true",
            severity="high",
        ),
        CapabilityRule(
            signal_type="autocomplete_latency_spike",
            summary="Detect when autocomplete latency crosses the interactive experience budget.",
            threshold_hint="latency_ms > 350",
            severity="medium",
        ),
        CapabilityRule(
            signal_type="autocomplete_relevance_regression",
            summary="Detect when autocomplete CTR or acceptance rate regresses versus baseline.",
            threshold_hint="ctr_drop_ratio <= -0.20",
            severity="medium",
        ),
    ],
    "semantic_index": [
        CapabilityRule(
            signal_type="semantic_index_gap",
            summary="Detect when the vector index covers fewer documents than the main search index.",
            threshold_hint="vector_doc_count/index_doc_count < 0.90",
            severity="high",
        ),
        CapabilityRule(
            signal_type="semantic_index_stale",
            summary="Detect when embeddings are older than the semantic freshness SLA.",
            threshold_hint="embedding_age_minutes > embedding_sla_minutes",
            severity="high",
        ),
        CapabilityRule(
            signal_type="semantic_recall_drop",
            summary="Detect when semantic recall falls below the acceptable benchmark floor.",
            threshold_hint="recall_at_10 < 0.60",
            severity="high",
        ),
        CapabilityRule(
            signal_type="vector_search_latency_spike",
            summary="Detect when vector retrieval becomes too slow for live traffic.",
            threshold_hint="vector_latency_ms > 800",
            severity="medium",
        ),
    ],
    "personalization": [
        CapabilityRule(
            signal_type="personalization_fallback_spike",
            summary="Detect when too many eligible requests fall back to generic ranking.",
            threshold_hint="fallback_rate > 0.30",
            severity="high",
        ),
        CapabilityRule(
            signal_type="feature_service_degraded",
            summary="Detect when personalization features or profile services are unavailable.",
            threshold_hint="feature_service_status != healthy",
            severity="critical",
        ),
        CapabilityRule(
            signal_type="personalization_uplift_drop",
            summary="Detect when personalization uplift drops below expectation.",
            threshold_hint="actual_uplift < expected_uplift",
            severity="medium",
        ),
    ],
    "merchandising": [
        CapabilityRule(
            signal_type="pinning_failure",
            summary="Detect when a required pinned or promoted item is missing from the expected slot range.",
            threshold_hint="expected_pinned == true and pinned_present == false",
            severity="high",
        ),
        CapabilityRule(
            signal_type="exclusion_policy_violation",
            summary="Detect when excluded items leak into results.",
            threshold_hint="excluded_item_present == true",
            severity="high",
        ),
        CapabilityRule(
            signal_type="merch_rule_conflict",
            summary="Detect when merchandising rules overlap or conflict.",
            threshold_hint="rule_conflicts > 0",
            severity="medium",
        ),
        CapabilityRule(
            signal_type="campaign_result_miss",
            summary="Detect when a campaign-managed query does not surface the expected campaign result set.",
            threshold_hint="campaign_hit_missing == true",
            severity="medium",
        ),
    ],
}


OWNER_BY_CAPABILITY = {
    "semantic_search": "Search / Relevance owner",
    "catalog": "Catalog / Indexing owner",
    "autocomplete": "Search UX / Autocomplete owner",
    "semantic_index": "Semantic Search / ML owner",
    "personalization": "Personalization owner",
    "merchandising": "Merchandising / Search Rules owner",
}


class CapabilitySignalEngine:
    def _threshold(self, name: str, default: Any) -> Any:
        return get_threshold(name, default)

    def describe_rules(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            capability: [
                {
                    "signal_type": rule.signal_type,
                    "summary": rule.summary,
                    "threshold_hint": self._dynamic_threshold_hint(capability, rule.signal_type, rule.threshold_hint),
                    "severity": rule.severity,
                }
                for rule in rules
            ]
            for capability, rules in RULE_CATALOG.items()
        }

    def evaluate(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        detectors = {
            "semantic_search": self._detect_semantic_search,
            "catalog": self._detect_catalog,
            "autocomplete": self._detect_autocomplete,
            "semantic_index": self._detect_semantic_index,
            "personalization": self._detect_personalization,
            "merchandising": self._detect_merchandising,
        }
        detector = detectors[event.capability]
        return detector(event)

    def _detect_semantic_search(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        results_count = self._number(event, "results_count")
        repeat_count = self._number(event, "repeat_count") or self._number(event, "session_zero_result_count") or 1.0
        reformulation_count = self._number(event, "reformulation_count") or 0.0
        zero_result_threshold = int(
            self._threshold("zero_result_repeat_count", settings.ZERO_RESULT_THRESHOLD) or settings.ZERO_RESULT_THRESHOLD
        )

        if results_count == 0 and repeat_count >= zero_result_threshold:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="zero_result_cluster",
                    severity="high",
                    capability="semantic_search",
                    summary="Repeated zero-result behavior suggests a semantic search relevance or coverage issue.",
                    evidence={
                        "results_count": results_count,
                        "repeat_count": repeat_count,
                    },
                )
            )

        if reformulation_count > 0:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="query_reformulation",
                    severity="medium",
                    capability="ranking",
                    summary="Users reformulated their query, which suggests weak semantic relevance or ranking.",
                    evidence={
                        "reformulation_count": reformulation_count,
                        "previous_query": event.facts.get("previous_query"),
                        "new_query": event.query,
                    },
                )
            )

        return signals

    def _detect_catalog(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        source_count = self._number(event, "source_count")
        index_count = self._number(event, "index_count")
        freshness_age = self._number(event, "freshness_age_minutes")
        freshness_sla = self._number(event, "freshness_sla_minutes") or 60.0
        missing_expected = self._number(event, "missing_expected_count")
        coverage_threshold = float(self._threshold("catalog_coverage_ratio", 0.95) or 0.95)

        if source_count and source_count > 0 and index_count is not None:
            coverage = index_count / source_count
            if coverage < coverage_threshold:
                signals.append(
                    self._signal(
                        event=event,
                        signal_type="catalog_index_gap",
                        severity="high",
                        capability="catalog",
                        summary="Indexed document coverage dropped below the catalog completeness threshold.",
                        evidence={
                            "source_count": source_count,
                            "index_count": index_count,
                            "coverage_ratio": round(coverage, 4),
                        },
                    )
                )

        if freshness_age is not None and freshness_age > freshness_sla:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="catalog_freshness_breach",
                    severity="high",
                    capability="catalog",
                    summary="Catalog freshness exceeded the configured SLA window.",
                    evidence={
                        "freshness_age_minutes": freshness_age,
                        "freshness_sla_minutes": freshness_sla,
                    },
                )
            )

        if missing_expected and missing_expected > 0:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="missing_products_cluster",
                    severity="high",
                    capability="catalog",
                    summary="Known products or SKUs are missing from the search-serving catalog.",
                    evidence={
                        "missing_expected_count": missing_expected,
                        "missing_examples": event.facts.get("missing_examples", []),
                    },
                )
            )

        return signals

    def _detect_autocomplete(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        suggestion_count = self._number(event, "suggestion_count")
        latency_ms = self._number(event, "latency_ms")
        ctr_drop_ratio = self._number(event, "ctr_drop_ratio")
        common_prefix = self._bool(event, "common_prefix")
        latency_threshold = float(self._threshold("autocomplete_latency_ms", 350) or 350)
        ctr_drop_threshold = float(self._threshold("autocomplete_ctr_drop_ratio", -0.20) or -0.20)

        if suggestion_count == 0 and common_prefix:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="autocomplete_zero_suggestions",
                    severity="high",
                    capability="autocomplete",
                    summary="Autocomplete returned no suggestions for a common prefix or scheduled probe.",
                    evidence={
                        "suggestion_count": suggestion_count,
                        "common_prefix": common_prefix,
                    },
                )
            )

        if latency_ms is not None and latency_ms > latency_threshold:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="autocomplete_latency_spike",
                    severity="medium",
                    capability="autocomplete",
                    summary="Autocomplete latency crossed the interactive experience threshold.",
                    evidence={"latency_ms": latency_ms},
                )
            )

        if ctr_drop_ratio is not None and ctr_drop_ratio <= ctr_drop_threshold:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="autocomplete_relevance_regression",
                    severity="medium",
                    capability="autocomplete",
                    summary="Autocomplete acceptance or click-through regressed materially versus baseline.",
                    evidence={"ctr_drop_ratio": ctr_drop_ratio},
                )
            )

        return signals

    def _detect_semantic_index(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        index_doc_count = self._number(event, "index_doc_count")
        vector_doc_count = self._number(event, "vector_doc_count")
        embedding_age = self._number(event, "embedding_age_minutes")
        embedding_sla = self._number(event, "embedding_sla_minutes") or float(
            self._threshold("semantic_embedding_sla_minutes", 240.0) or 240.0
        )
        recall_at_10 = self._number(event, "recall_at_10")
        vector_latency_ms = self._number(event, "vector_latency_ms")
        coverage_threshold = float(self._threshold("semantic_index_coverage_ratio", 0.90) or 0.90)
        recall_floor = float(self._threshold("semantic_recall_floor", 0.60) or 0.60)
        vector_latency_threshold = float(self._threshold("vector_latency_ms", 800) or 800)

        if index_doc_count and index_doc_count > 0 and vector_doc_count is not None:
            coverage = vector_doc_count / index_doc_count
            if coverage < coverage_threshold:
                signals.append(
                    self._signal(
                        event=event,
                        signal_type="semantic_index_gap",
                        severity="high",
                        capability="semantic_index",
                        summary="Vector index coverage is lower than the main search index coverage.",
                        evidence={
                            "index_doc_count": index_doc_count,
                            "vector_doc_count": vector_doc_count,
                            "coverage_ratio": round(coverage, 4),
                        },
                    )
                )

        if embedding_age is not None and embedding_age > embedding_sla:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="semantic_index_stale",
                    severity="high",
                    capability="semantic_index",
                    summary="Semantic embeddings are older than the freshness budget.",
                    evidence={
                        "embedding_age_minutes": embedding_age,
                        "embedding_sla_minutes": embedding_sla,
                    },
                )
            )

        if recall_at_10 is not None and recall_at_10 < recall_floor:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="semantic_recall_drop",
                    severity="high",
                    capability="semantic_index",
                    summary="Semantic recall dropped below the benchmark floor.",
                    evidence={"recall_at_10": recall_at_10},
                )
            )

        if vector_latency_ms is not None and vector_latency_ms > vector_latency_threshold:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="vector_search_latency_spike",
                    severity="medium",
                    capability="semantic_index",
                    summary="Vector retrieval latency is too high for live traffic.",
                    evidence={"vector_latency_ms": vector_latency_ms},
                )
            )

        return signals

    def _detect_personalization(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        fallback_rate = self._number(event, "fallback_rate")
        feature_service_status = str(event.facts.get("feature_service_status", "healthy")).lower()
        actual_uplift = self._number(event, "actual_uplift")
        expected_uplift = self._number(event, "expected_uplift")
        fallback_threshold = float(self._threshold("personalization_fallback_rate", 0.30) or 0.30)

        if fallback_rate is not None and fallback_rate > fallback_threshold:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="personalization_fallback_spike",
                    severity="high",
                    capability="personalization",
                    summary="Too many eligible requests fell back to non-personalized ranking.",
                    evidence={"fallback_rate": fallback_rate},
                )
            )

        if feature_service_status not in {"healthy", "ok", "up"}:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="feature_service_degraded",
                    severity="critical",
                    capability="personalization",
                    summary="The personalization feature or profile service is degraded.",
                    evidence={"feature_service_status": feature_service_status},
                )
            )

        if (
            actual_uplift is not None
            and expected_uplift is not None
            and actual_uplift < expected_uplift
        ):
            signals.append(
                self._signal(
                    event=event,
                    signal_type="personalization_uplift_drop",
                    severity="medium",
                    capability="personalization",
                    summary="Observed personalization uplift is lower than expected.",
                    evidence={
                        "actual_uplift": actual_uplift,
                        "expected_uplift": expected_uplift,
                    },
                )
            )

        return signals

    def _detect_merchandising(self, event: CapabilitySignalEvent) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        pinned_present = self._bool(event, "pinned_present")
        expected_pinned = self._bool(event, "expected_pinned")
        excluded_item_present = self._bool(event, "excluded_item_present")
        rule_conflicts = self._number(event, "rule_conflicts")
        campaign_hit_missing = self._bool(event, "campaign_hit_missing")

        if expected_pinned and not pinned_present:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="pinning_failure",
                    severity="high",
                    capability="merchandising_controls",
                    summary="A pinned or promoted item is missing from the expected result window.",
                    evidence={
                        "expected_pinned": expected_pinned,
                        "pinned_present": pinned_present,
                        "expected_item_id": event.facts.get("expected_item_id"),
                    },
                )
            )

        if excluded_item_present:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="exclusion_policy_violation",
                    severity="high",
                    capability="merchandising_controls",
                    summary="An excluded item leaked into results.",
                    evidence={"excluded_item_present": excluded_item_present},
                )
            )

        if rule_conflicts is not None and rule_conflicts > 0:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="merch_rule_conflict",
                    severity="medium",
                    capability="merchandising_controls",
                    summary="Merchandising rules overlap or conflict for the same request scope.",
                    evidence={"rule_conflicts": rule_conflicts},
                )
            )

        if campaign_hit_missing:
            signals.append(
                self._signal(
                    event=event,
                    signal_type="campaign_result_miss",
                    severity="medium",
                    capability="merchandising_controls",
                    summary="A campaign-managed query did not return the expected campaign result set.",
                    evidence={"campaign_hit_missing": campaign_hit_missing},
                )
            )

        return signals

    def _signal(
        self,
        *,
        event: CapabilitySignalEvent,
        signal_type: str,
        severity: str,
        capability: str,
        summary: str,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "signal_type": signal_type,
            "severity": severity,
            "capability": capability,
            "query": event.query,
            "owner": OWNER_BY_CAPABILITY.get(event.capability, "Search operations owner"),
            "event_type": event.event_type,
            "release_phase": event.release_phase,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "summary": summary,
            "evidence": {
                "request_id": event.request_id,
                "trace_id": event.trace_id,
                "metrics": dict(event.metrics),
                "facts": dict(event.facts),
                "metadata": dict(event.metadata),
                "rule_evidence": evidence,
            },
        }

    def _number(self, event: CapabilitySignalEvent, key: str) -> float | None:
        value = event.metrics.get(key, event.facts.get(key))
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _bool(self, event: CapabilitySignalEvent, key: str) -> bool:
        value = event.metrics.get(key, event.facts.get(key))
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _dynamic_threshold_hint(self, capability: str, signal_type: str, fallback: str) -> str:
        dynamic_hints = {
            ("semantic_search", "zero_result_cluster"): (
                f"repeat_count >= {int(self._threshold('zero_result_repeat_count', settings.ZERO_RESULT_THRESHOLD) or settings.ZERO_RESULT_THRESHOLD)} and results_count == 0"
            ),
            ("catalog", "catalog_index_gap"): (
                f"index_count/source_count < {float(self._threshold('catalog_coverage_ratio', 0.95) or 0.95):.2f}"
            ),
            ("autocomplete", "autocomplete_latency_spike"): (
                f"latency_ms > {float(self._threshold('autocomplete_latency_ms', 350) or 350):.0f}"
            ),
            ("autocomplete", "autocomplete_relevance_regression"): (
                f"ctr_drop_ratio <= {float(self._threshold('autocomplete_ctr_drop_ratio', -0.20) or -0.20):.2f}"
            ),
            ("semantic_index", "semantic_index_gap"): (
                f"vector_doc_count/index_doc_count < {float(self._threshold('semantic_index_coverage_ratio', 0.90) or 0.90):.2f}"
            ),
            ("semantic_index", "semantic_index_stale"): (
                f"embedding_age_minutes > {float(self._threshold('semantic_embedding_sla_minutes', 240.0) or 240.0):.0f}"
            ),
            ("semantic_index", "semantic_recall_drop"): (
                f"recall_at_10 < {float(self._threshold('semantic_recall_floor', 0.60) or 0.60):.2f}"
            ),
            ("semantic_index", "vector_search_latency_spike"): (
                f"vector_latency_ms > {float(self._threshold('vector_latency_ms', 800) or 800):.0f}"
            ),
            ("personalization", "personalization_fallback_spike"): (
                f"fallback_rate > {float(self._threshold('personalization_fallback_rate', 0.30) or 0.30):.2f}"
            ),
        }
        return dynamic_hints.get((capability, signal_type), fallback)


async def evaluate_capability_signal_event(event: CapabilitySignalEvent) -> Dict[str, Any]:
    engine = CapabilitySignalEngine()
    signals = engine.evaluate(event)

    for signal in signals:
        publish_signal(signal)
        await store_signal(signal)

    return {
        "evaluated_at": datetime.now(tz=UTC).isoformat(),
        "capability": event.capability,
        "event_type": event.event_type,
        "signal_count": len(signals),
        "signals": signals,
    }


def capability_signal_rules() -> Dict[str, Any]:
    engine = CapabilitySignalEngine()
    return {
        "capabilities": list(RULE_CATALOG.keys()),
        "rules": engine.describe_rules(),
    }
