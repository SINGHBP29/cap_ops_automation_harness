from __future__ import annotations

from typing import Dict

from app.models.ops_event import RawOpsEvent


def _scenario_catalog_delta_gap() -> RawOpsEvent:
    return RawOpsEvent(
        source_type="catalog_delta",
        event_type="freshness_change",
        capability="catalog",
        origin="mock_data",
        metrics={
            "source_count": 1000,
            "index_count": 850,
            "freshness_age_minutes": 180,
            "freshness_sla_minutes": 60,
            "missing_expected_count": 12,
        },
        facts={
            "missing_examples": ["sku-1", "sku-2"],
            "index_name": "books",
        },
        metadata={"event_origin": "mock_data", "scenario": "catalog_delta_gap"},
    )


def _scenario_autocomplete_failure() -> RawOpsEvent:
    return RawOpsEvent(
        source_type="autocomplete_probe",
        event_type="probe_result",
        capability="autocomplete",
        origin="mock_data",
        query="iph",
        metrics={
            "suggestion_count": 0,
            "latency_ms": 420,
        },
        facts={
            "common_prefix": True,
            "probe_name": "top-prefix-check",
        },
        metadata={"event_origin": "mock_data", "scenario": "autocomplete_failure"},
    )


def _scenario_semantic_index_stale() -> RawOpsEvent:
    return RawOpsEvent(
        source_type="voice_search_failure",
        event_type="semantic_refresh_probe",
        capability="semantic_index",
        origin="mock_data",
        metrics={
            "index_doc_count": 1000,
            "vector_doc_count": 820,
            "embedding_age_minutes": 720,
            "embedding_sla_minutes": 240,
            "recall_at_10": 0.42,
            "vector_latency_ms": 910,
        },
        facts={
            "modality": "voice",
            "failure_reason": "stale_embeddings",
        },
        metadata={"event_origin": "mock_data", "scenario": "semantic_index_stale"},
    )


def _scenario_personalization_fallback() -> RawOpsEvent:
    return RawOpsEvent(
        source_type="personalization_event",
        event_type="ranking_uplift_check",
        capability="personalization",
        origin="mock_data",
        query="running shoes",
        metrics={
            "fallback_rate": 0.45,
            "actual_uplift": 0.02,
            "expected_uplift": 0.12,
        },
        facts={
            "feature_service_status": "degraded",
        },
        metadata={"event_origin": "mock_data", "scenario": "personalization_fallback"},
    )


def _scenario_mxp_rule_conflict() -> RawOpsEvent:
    return RawOpsEvent(
        source_type="mxp_rule_diff",
        event_type="rule_evaluation",
        capability="merchandising",
        origin="mock_data",
        query="summer sale shoes",
        metrics={
            "rule_conflicts": 2,
        },
        facts={
            "expected_pinned": True,
            "pinned_present": False,
            "excluded_item_present": False,
            "campaign_hit_missing": True,
            "expected_item_id": "sku-999",
        },
        metadata={"event_origin": "mock_data", "scenario": "mxp_rule_conflict"},
    )


SCENARIO_BUILDERS = {
    "catalog_delta_gap": _scenario_catalog_delta_gap,
    "autocomplete_failure": _scenario_autocomplete_failure,
    "semantic_index_stale": _scenario_semantic_index_stale,
    "personalization_fallback": _scenario_personalization_fallback,
    "mxp_rule_conflict": _scenario_mxp_rule_conflict,
}


def scenario_names() -> list[str]:
    return sorted(SCENARIO_BUILDERS.keys())


def scenario_payload(name: str) -> RawOpsEvent:
    builder = SCENARIO_BUILDERS.get(name)
    if builder is None:
        raise KeyError(name)
    return builder()
