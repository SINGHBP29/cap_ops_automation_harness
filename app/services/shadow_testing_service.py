from __future__ import annotations

import asyncio
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from typing import Sequence

from app.ai_search import get_ai_search_adapter
from app.services.candidate_index_service import ensure_shadow_index_ready
from app.services.incident_packet_service import build_incident_packet
from app.services.search_service import execute_search_against_index


def _dedupe_queries(queries: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for query in queries:
        normalized = str(query or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)

    return ordered


def _default_queries(incident_packet: Dict[str, Any]) -> list[str]:
    dataset = incident_packet.get("runbook", {}).get("eval_dataset", {})
    return _dedupe_queries(
        list(dataset.get("incident_queries", []))
        + list(dataset.get("positive_queries", []))
        + list(dataset.get("negative_controls", []))
    )


def _extract_error_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    for key in ("message", "error", "detail", "body"):
        value = payload.get(key)
        if value:
            return str(value)

    return None


def _preview_hits(payload: Any, limit: int = 3) -> list[str]:
    if not isinstance(payload, dict):
        return []

    hits = payload.get("hits")
    if not isinstance(hits, list):
        return []

    previews: list[str] = []
    for hit in hits[:limit]:
        if not isinstance(hit, dict):
            previews.append(str(hit))
            continue

        label = (
            hit.get("title")
            or hit.get("name")
            or hit.get("book_title")
            or hit.get("slug")
            or hit.get("id")
        )
        if label is None:
            previews.append(str(hit))
        else:
            previews.append(str(label))

    return previews


def _classify_result(result: Dict[str, Any]) -> Dict[str, Any]:
    status_code = int(result.get("status_code", 0) or 0)
    error_message = _extract_error_message(result.get("raw_response"))

    if status_code == 200:
        status = "ok"
    elif status_code == 404 and error_message and "not found" in error_message.lower():
        status = "index-missing"
    elif status_code in {502, 503, 504}:
        status = "backend-unavailable"
    elif status_code >= 400:
        status = "error"
    else:
        status = "unknown"

    return {
        "status": status,
        "error": error_message,
    }


def _outcome(
    baseline_status: str,
    shadow_status: str,
    baseline_results: int,
    shadow_results: int,
) -> str:
    if baseline_status != "ok":
        return "baseline-unavailable"
    if shadow_status != "ok":
        return "candidate-unavailable"
    if shadow_results > baseline_results:
        return "improved"
    if shadow_results < baseline_results:
        return "regressed"
    if shadow_results == 0:
        return "still-zero"
    return "matched"


async def _compare_query(query: str, baseline_index: str, shadow_index: str) -> Dict[str, Any]:
    baseline_result, shadow_result = await asyncio.gather(
        execute_search_against_index(query, baseline_index, limit=10, search_mode="shadow-baseline"),
        execute_search_against_index(query, shadow_index, limit=10, search_mode="shadow-candidate"),
    )

    baseline_state = _classify_result(baseline_result)
    shadow_state = _classify_result(shadow_result)
    baseline_results = int(baseline_result.get("results_count", 0) or 0)
    shadow_results = int(shadow_result.get("results_count", 0) or 0)
    outcome = _outcome(
        baseline_status=baseline_state["status"],
        shadow_status=shadow_state["status"],
        baseline_results=baseline_results,
        shadow_results=shadow_results,
    )

    return {
        "query": query,
        "baseline": {
            "index": baseline_index,
            "status": baseline_state["status"],
            "http_status": baseline_result.get("status_code"),
            "results_count": baseline_results,
            "latency_ms": round(float(baseline_result.get("latency_ms", 0.0) or 0.0), 2),
            "top_hits": _preview_hits(baseline_result.get("raw_response")),
            "error": baseline_state["error"],
        },
        "shadow": {
            "index": shadow_index,
            "status": shadow_state["status"],
            "http_status": shadow_result.get("status_code"),
            "results_count": shadow_results,
            "latency_ms": round(float(shadow_result.get("latency_ms", 0.0) or 0.0), 2),
            "top_hits": _preview_hits(shadow_result.get("raw_response")),
            "error": shadow_state["error"],
        },
        "delta": {
            "results_count": shadow_results - baseline_results,
            "latency_ms": round(
                float(shadow_result.get("latency_ms", 0.0) or 0.0)
                - float(baseline_result.get("latency_ms", 0.0) or 0.0),
                2,
            ),
            "outcome": outcome,
        },
    }


def _build_summary(
    comparisons: list[Dict[str, Any]],
    baseline_index: str,
    shadow_index: str,
) -> Dict[str, Any]:
    outcomes = [item["delta"]["outcome"] for item in comparisons]
    shadow_statuses = [item["shadow"]["status"] for item in comparisons]
    baseline_statuses = [item["baseline"]["status"] for item in comparisons]

    improved_queries = outcomes.count("improved")
    regressed_queries = outcomes.count("regressed")
    still_zero_queries = outcomes.count("still-zero")
    candidate_unavailable_queries = outcomes.count("candidate-unavailable")

    if shadow_index == baseline_index:
        shadow_status = "same-as-baseline"
    elif "index-missing" in shadow_statuses:
        shadow_status = "candidate-index-missing"
    elif any(status != "ok" for status in shadow_statuses):
        shadow_status = "candidate-errors"
    else:
        shadow_status = "ready"

    baseline_ready = all(status == "ok" for status in baseline_statuses)
    shadow_ready = shadow_status == "ready"

    if shadow_status == "same-as-baseline":
        recommendation = (
            "Point AI_SEARCH_CANDIDATE_INDEX at a separate candidate index before using shadow replay."
        )
    elif shadow_status == "candidate-index-missing":
        recommendation = (
            "Create or populate the candidate index first, then rerun shadow replay against the eval dataset."
        )
    elif shadow_status == "candidate-errors":
        recommendation = "Fix candidate search path errors before promotion."
    elif regressed_queries > 0:
        recommendation = "Keep the change in shadow only. The candidate regressed on at least one eval query."
    elif improved_queries > 0:
        recommendation = (
            "The candidate looks stronger on result coverage. Review relevance and latency, then consider a 5% canary."
        )
    else:
        recommendation = (
            "The candidate matches baseline on this dataset. Expand the eval set or apply a more meaningful candidate change."
        )

    return {
        "baseline_ready": baseline_ready,
        "shadow_ready": shadow_ready,
        "shadow_status": shadow_status,
        "improved_queries": improved_queries,
        "regressed_queries": regressed_queries,
        "still_zero_queries": still_zero_queries,
        "candidate_unavailable_queries": candidate_unavailable_queries,
        "baseline_zero_result_queries": sum(
            1 for item in comparisons if item["baseline"]["results_count"] == 0
        ),
        "shadow_zero_result_queries": sum(
            1 for item in comparisons if item["shadow"]["results_count"] == 0
        ),
        "ready_for_canary": baseline_ready and shadow_ready and regressed_queries == 0,
        "recommendation": recommendation,
    }


async def build_shadow_test_report(
    queries: Sequence[str] | None = None,
    incident_packet: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    packet = incident_packet or await build_incident_packet()
    selected_queries = _dedupe_queries(queries or _default_queries(packet))
    if not selected_queries:
        raise ValueError("No shadow-test queries available. Build an incident packet with an eval dataset first.")

    adapter = get_ai_search_adapter()
    baseline_index = adapter.baseline_index
    shadow_index = adapter.candidate_index
    shadow_index_state = await ensure_shadow_index_ready(force=False)
    comparisons = await asyncio.gather(
        *[_compare_query(query, baseline_index, shadow_index) for query in selected_queries]
    )
    summary = _build_summary(comparisons, baseline_index, shadow_index)

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "mode": "single_query" if queries else "incident_eval_dataset",
        "baseline_index": baseline_index,
        "shadow_index": shadow_index,
        "shadow_index_state": shadow_index_state,
        "incident_context": {
            "incident_id": packet.get("incident_id"),
            "signal_type": packet.get("diagnosis", {}).get("signal_type"),
            "affected_capability": packet.get("diagnosis", {}).get("affected_capability"),
            "risk_level": packet.get("runbook", {}).get("risk_level"),
        },
        "summary": summary,
        "comparisons": comparisons,
        "recommended_next_step": summary["recommendation"],
    }
