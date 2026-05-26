from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

from app.ai_search import get_ai_search_adapter
from app.services.approval_store import get_latest_approval
from app.services.candidate_index_service import ensure_shadow_index_ready
from app.services.candidate_index_service import get_shadow_index_cached_state
from app.services.ops_ledger import recent_signals
from app.services.search_service import execute_search_against_index
from app.services.temporal_release_service import get_controlled_release_workflow_state

_POLICY_TTL_SECONDS = 2.0
_policy_lock = asyncio.Lock()
_policy_cache: Dict[str, Any] = {
    "expires_at": 0.0,
    "value": None,
}

_shadow_replay_lock = asyncio.Lock()
_shadow_replay_log: List[Dict[str, Any]] = []
_shadow_replay_limit = 100

_PHASE_PERCENT = {
    "shadow": 0,
    "canary-5": 5,
    "canary-25": 25,
    "promote-100": 100,
    "completed": 100,
    "rollback": 0,
}


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()


def _active_incident_id() -> str | None:
    for signal in reversed(recent_signals):
        signal_type = signal.get("signal_type") or signal.get("type")
        if not signal_type or signal_type == "test":
            continue
        query = signal.get("query") or "unknown-query"
        return f"{signal_type}:{query}"
    return None


def _bucket_for_key(routing_key: str) -> int:
    digest = hashlib.sha256(routing_key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


async def get_traffic_router_status(force_refresh: bool = False) -> Dict[str, Any]:
    adapter = get_ai_search_adapter()
    loop = asyncio.get_running_loop()
    if not force_refresh and _policy_cache["value"] is not None and loop.time() < _policy_cache["expires_at"]:
        return deepcopy(_policy_cache["value"])

    async with _policy_lock:
        if not force_refresh and _policy_cache["value"] is not None and loop.time() < _policy_cache["expires_at"]:
            return deepcopy(_policy_cache["value"])

        incident_id = _active_incident_id()
        if incident_id is None:
            policy = {
                "available": True,
                "incident_id": None,
                "workflow_status": "no-active-incident",
                "release_phase": "baseline",
                "live_candidate_percent": 0,
                "shadow_mirror_enabled": False,
                "candidate_ready": False,
                "blocked_reason": "No active incident is currently driving controlled release.",
                "baseline_index": adapter.baseline_index,
                "candidate_index": adapter.candidate_index,
                "shadow_index": get_shadow_index_cached_state(),
                "recent_shadow_replays": list(_shadow_replay_log[-10:]),
                "updated_at": _timestamp(),
            }
        else:
            workflow_state = await get_controlled_release_workflow_state(incident_id)
            shadow_index_state = await ensure_shadow_index_ready(force=False)
            workflow_status = workflow_state.get("workflow_status", "unavailable")
            release_phase = workflow_state.get("release_phase", "shadow")
            candidate_ready = bool(shadow_index_state.get("ready"))
            live_candidate_percent = _PHASE_PERCENT.get(release_phase, 0)
            blocked_reason = None

            if release_phase in {"canary-5", "canary-25", "promote-100", "completed"}:
                latest_approval = get_latest_approval(incident_id)
                if latest_approval is None or latest_approval.get("decision") != "approved":
                    blocked_reason = "Human approval has not been recorded yet."
                    live_candidate_percent = 0
                elif not candidate_ready:
                    blocked_reason = "Candidate index is not ready, so live traffic stays on baseline."
                    live_candidate_percent = 0

            if workflow_status in {"rejected", "changes-requested"}:
                blocked_reason = f"Workflow status is '{workflow_status}', so promotion is blocked."
                live_candidate_percent = 0

            policy = {
                "available": True,
                "incident_id": incident_id,
                "workflow_status": workflow_status,
                "release_phase": release_phase,
                "live_candidate_percent": live_candidate_percent,
                "shadow_mirror_enabled": release_phase == "shadow" and candidate_ready,
                "candidate_ready": candidate_ready,
                "blocked_reason": blocked_reason,
                "baseline_index": adapter.baseline_index,
                "candidate_index": adapter.candidate_index,
                "workflow_id": workflow_state.get("workflow_id"),
                "shadow_index": shadow_index_state,
                "recent_shadow_replays": list(_shadow_replay_log[-10:]),
                "updated_at": _timestamp(),
            }

        _policy_cache["value"] = deepcopy(policy)
        _policy_cache["expires_at"] = loop.time() + _POLICY_TTL_SECONDS
        return deepcopy(policy)


async def validate_release_phase_transition(incident_id: str, phase: str) -> str | None:
    if phase == "shadow":
        return None

    latest_approval = get_latest_approval(incident_id)
    if latest_approval is None or latest_approval.get("decision") != "approved":
        return "Human approval is required before canary or full promotion."

    shadow_index_state = await ensure_shadow_index_ready(force=False)
    if not shadow_index_state.get("ready"):
        return "Candidate index is not ready yet. Sync the candidate index before promoting traffic."

    return None


async def sync_candidate_index(force: bool = True) -> Dict[str, Any]:
    policy = await ensure_shadow_index_ready(force=force)
    await get_traffic_router_status(force_refresh=True)
    return policy


async def route_search(query_text: str, routing_key: str) -> Dict[str, Any]:
    policy = await get_traffic_router_status(force_refresh=False)
    bucket = _bucket_for_key(routing_key)
    route_to_candidate = (
        policy["candidate_ready"]
        and policy["live_candidate_percent"] > 0
        and bucket < policy["live_candidate_percent"]
    )

    selected_index = policy["candidate_index"] if route_to_candidate else policy["baseline_index"]
    selected_mode = "candidate-live" if route_to_candidate else "baseline-live"
    visible_result = await execute_search_against_index(
        query_text=query_text,
        index_name=selected_index,
        limit=20,
        search_mode=selected_mode,
    )

    fallback_to_baseline = False
    fallback_reason = None
    if route_to_candidate and int(visible_result.get("status_code", 0) or 0) >= 400:
        fallback_to_baseline = True
        fallback_reason = "Candidate search returned an error, so the request fell back to baseline."
        visible_result = await execute_search_against_index(
            query_text=query_text,
            index_name=policy["baseline_index"],
            limit=20,
            search_mode="candidate-fallback",
        )
        selected_index = policy["baseline_index"]
        route_to_candidate = False

    if policy["shadow_mirror_enabled"]:
        asyncio.create_task(
            _record_shadow_replay(
                query_text=query_text,
                routing_key=routing_key,
                baseline_result=deepcopy(visible_result),
                policy=deepcopy(policy),
            )
        )

    return {
        "search_event": visible_result,
        "routing": {
            "release_phase": policy["release_phase"],
            "workflow_status": policy["workflow_status"],
            "selected_index": selected_index,
            "routed_to_candidate": route_to_candidate,
            "live_candidate_percent": policy["live_candidate_percent"],
            "shadow_mirror_enabled": policy["shadow_mirror_enabled"],
            "candidate_ready": policy["candidate_ready"],
            "routing_bucket": bucket,
            "routing_key": routing_key,
            "fallback_to_baseline": fallback_to_baseline,
            "fallback_reason": fallback_reason,
            "blocked_reason": policy["blocked_reason"],
        },
    }


async def _record_shadow_replay(
    query_text: str,
    routing_key: str,
    baseline_result: Dict[str, Any],
    policy: Dict[str, Any],
) -> None:
    try:
        candidate_result = await execute_search_against_index(
            query_text=query_text,
            index_name=policy["candidate_index"],
            limit=20,
            search_mode="shadow-mirror",
        )
        entry = {
            "at": _timestamp(),
            "query": query_text,
            "routing_key": routing_key,
            "release_phase": policy["release_phase"],
            "baseline_index": policy["baseline_index"],
            "candidate_index": policy["candidate_index"],
            "baseline_results_count": baseline_result.get("results_count", 0),
            "candidate_results_count": candidate_result.get("results_count", 0),
            "baseline_latency_ms": round(float(baseline_result.get("latency_ms", 0.0) or 0.0), 2),
            "candidate_latency_ms": round(float(candidate_result.get("latency_ms", 0.0) or 0.0), 2),
            "candidate_status_code": candidate_result.get("status_code"),
            "delta_results_count": int(candidate_result.get("results_count", 0) or 0)
            - int(baseline_result.get("results_count", 0) or 0),
        }
    except Exception as exc:
        entry = {
            "at": _timestamp(),
            "query": query_text,
            "routing_key": routing_key,
            "release_phase": policy["release_phase"],
            "baseline_index": policy["baseline_index"],
            "candidate_index": policy["candidate_index"],
            "error": str(exc),
        }

    async with _shadow_replay_lock:
        _shadow_replay_log.append(entry)
        if len(_shadow_replay_log) > _shadow_replay_limit:
            del _shadow_replay_log[: len(_shadow_replay_log) - _shadow_replay_limit]
