from __future__ import annotations

import asyncio
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List

from app.ai_search import get_ai_search_provider
from app.config import settings

_INDEX_SETTING_KEYS = (
    "searchableAttributes",
    "filterableAttributes",
    "sortableAttributes",
    "rankingRules",
    "synonyms",
    "stopWords",
    "typoTolerance",
)


def looks_synthetic_query(query: str) -> bool:
    normalized = str(query or "").strip().lower()
    if not normalized:
        return False
    markers = (
        "definitelymissing",
        "zzzz",
        "synthetic",
        "dummy",
        "fake",
        "test",
        "nonexistent-control",
    )
    return any(marker in normalized for marker in markers)


def infer_capability_from_signal(signal_type: str) -> str:
    if signal_type == "zero_result_cluster":
        return "semantic_search"
    if signal_type in {"catalog_delta", "catalog_index_gap", "catalog_freshness_breach", "missing_products_cluster"}:
        return "catalog"
    if signal_type in {"autocomplete_fail", "autocomplete_zero_suggestions", "autocomplete_latency_spike", "autocomplete_relevance_regression"}:
        return "autocomplete"
    if signal_type in {"semantic_index_gap", "semantic_index_stale", "semantic_recall_drop", "vector_search_latency_spike"}:
        return "semantic_index"
    if signal_type in {"personalization_fallback_spike", "feature_service_degraded", "personalization_uplift_drop"}:
        return "personalization"
    if signal_type in {"rule_diff", "rule_conflict", "policy_violation"}:
        return "merchandising_controls"
    if signal_type in {"pinning_failure", "exclusion_policy_violation", "merch_rule_conflict", "campaign_result_miss"}:
        return "merchandising_controls"
    if signal_type == "latency_spike":
        return "search_api"
    return "unknown"


def capability_family(signal_type: str, capability: str) -> str:
    if capability in {"semantic_search", "ranking"} or signal_type in {"zero_result_cluster", "query_reformulation"}:
        return "semantic_retrieval"
    if capability == "catalog" or signal_type in {"catalog_delta", "catalog_index_gap", "catalog_freshness_breach", "missing_products_cluster"}:
        return "catalog"
    if capability == "autocomplete" or signal_type in {"autocomplete_fail", "autocomplete_zero_suggestions", "autocomplete_latency_spike", "autocomplete_relevance_regression"}:
        return "autocomplete"
    if capability == "semantic_index" or signal_type in {"semantic_index_gap", "semantic_index_stale", "semantic_recall_drop", "vector_search_latency_spike"}:
        return "semantic_retrieval"
    if capability == "personalization" or signal_type in {"personalization_fallback_spike", "feature_service_degraded", "personalization_uplift_drop"}:
        return "personalization"
    if capability in {"merchandising_controls", "rule_engine"} or signal_type in {"rule_diff", "rule_conflict", "policy_violation", "pinning_failure", "exclusion_policy_violation", "merch_rule_conflict", "campaign_result_miss"}:
        return "merchandising_controls"
    return capability or "unknown"


def metric_value(metric_map: Dict[str, Dict[str, Any]], key: str) -> float | None:
    value = metric_map.get(key, {}).get("value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def incident_comparison(comparisons: Iterable[Dict[str, Any]], incident_query: str) -> Dict[str, Any]:
    for comparison in comparisons:
        if str(comparison.get("query")) == incident_query:
            return comparison
    return {
        "query": incident_query,
        "baseline": {"results_count": 0},
        "shadow": {"results_count": 0},
        "delta": {"outcome": "unknown"},
    }


async def fetch_index_analysis(
    baseline_index: str,
    candidate_index: str,
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    provider = get_ai_search_provider()
    baseline_stats, candidate_stats, baseline_settings, candidate_settings = await asyncio.gather(
        provider.fetch_index_stats(baseline_index),
        provider.fetch_index_stats(candidate_index),
        provider.fetch_index_settings(baseline_index),
        provider.fetch_index_settings(candidate_index),
    )
    return baseline_stats, candidate_stats, baseline_settings, candidate_settings


def diff_index_settings(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    for key in _INDEX_SETTING_KEYS:
        if baseline.get(key) != candidate.get(key):
            diff[key] = {
                "baseline": compact_value(baseline.get(key)),
                "candidate": compact_value(candidate.get(key)),
            }
    return diff


def compact_value(value: Any) -> Any:
    if isinstance(value, list):
        if len(value) <= 8:
            return value
        return value[:8] + [f"... +{len(value) - 8} more"]
    if isinstance(value, dict):
        compact: Dict[str, Any] = {}
        for index, (key, item) in enumerate(sorted(value.items())):
            if index >= 6:
                compact["..."] = f"+{len(value) - 6} more"
                break
            compact[key] = item
        return compact
    return value


def classify_data_gap(
    *,
    incident_query: str,
    baseline_docs: int,
    candidate_docs: int,
    baseline_results: int,
    candidate_results: int,
    shadow_status: str,
    setting_diff: Dict[str, Any],
) -> tuple[str, str, str]:
    if looks_synthetic_query(incident_query):
        return (
            "synthetic_test_query",
            f"The incident query '{incident_query}' looks synthetic, so the zero-result cluster is likely expected test traffic.",
            "high",
        )
    if shadow_status == "candidate-index-missing":
        return (
            "candidate-index-missing",
            "The candidate index is missing, so shadow replay cannot prove the fix path yet.",
            "high",
        )
    if baseline_docs == 0:
        return (
            "baseline_index_empty",
            "The baseline index has no documents, so the failure is caused by an empty or unseeded catalog.",
            "high",
        )
    if baseline_results == 0 and candidate_results == 0 and baseline_docs > 0:
        return (
            "query_vocabulary_gap",
            "Both baseline and candidate stay at zero hits even though the catalog has documents, which points to vocabulary, synonym, or coverage gaps.",
            "high",
        )
    if candidate_docs < baseline_docs:
        return (
            "candidate_catalog_delta",
            "The candidate index contains fewer documents than baseline, so the candidate catalog is incomplete.",
            "medium",
        )
    if setting_diff:
        return (
            "rule_configuration_diff",
            "Ranking, synonym, or searchable-attribute settings differ between baseline and candidate indexes.",
            "medium",
        )
    return (
        "no_material_catalog_gap_detected",
        "No major catalog or rule diff stands out from the current replay and index comparison.",
        "medium",
    )


def data_gap_actions(*, gap_type: str, incident_query: str) -> List[str]:
    if gap_type == "synthetic_test_query":
        return [
            "Mark the signal as expected test traffic or suppress it in the detector.",
            "Keep the query out of customer-impact dashboards and promotion gates.",
        ]
    if gap_type == "candidate-index-missing":
        return [
            "Sync or create the candidate index before any canary decision.",
            "Re-run the shadow eval dataset after the candidate index is seeded.",
        ]
    if gap_type == "baseline_index_empty":
        return [
            "Backfill the baseline index from the source catalog immediately.",
            "Verify indexing jobs and ingestion credentials before reopening traffic.",
        ]
    if gap_type == "query_vocabulary_gap":
        return [
            f"Check whether expected documents for '{incident_query}' exist in the source catalog and index.",
            "Add synonyms, aliases, stemming, or query normalization if the documents exist but do not match.",
        ]
    if gap_type == "candidate_catalog_delta":
        return [
            "Backfill missing candidate documents before evaluating relevance changes.",
            "Compare ingestion jobs and recent catalog patches between baseline and candidate indexes.",
        ]
    if gap_type == "rule_configuration_diff":
        return [
            "Review the changed ranking, synonym, and searchable-attribute settings.",
            "Promote only after the rule diff is intentional and shadow replay stays stable.",
        ]
    return [
        "Expand the eval dataset with more real customer queries before changing production traffic.",
        "Keep collecting evidence until a stronger catalog or rule gap appears.",
    ]
