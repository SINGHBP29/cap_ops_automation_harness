from __future__ import annotations

from copy import deepcopy
from datetime import UTC
from datetime import datetime
from threading import Lock
from typing import Any
from typing import Dict
from typing import List

from sqlalchemy import JSON
from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy import delete
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy import update

from app.config import settings

_lock = Lock()
_engine = None
_tables_ready = False
_state_cache: Dict[str, Any] | None = None
_incident_override_cache: Dict[str, Dict[str, Any]] = {}

metadata = MetaData()
feedback_state_table = Table(
    "feedback_control_state",
    metadata,
    Column("key", String(128), primary_key=True),
    Column("state_json", JSON, nullable=False),
    Column("updated_at", String(64), nullable=False),
)
feedback_outcome_table = Table(
    "feedback_incident_outcome",
    metadata,
    Column("incident_id", String(255), primary_key=True),
    Column("outcome_status", String(64), nullable=False),
    Column("capability", String(128), nullable=False),
    Column("signal_type", String(128), nullable=False),
    Column("query", String(255), nullable=False),
    Column("updated_at", String(64), nullable=False),
    Column("record_json", JSON, nullable=False),
)
feedback_incident_override_table = Table(
    "feedback_incident_automation_override",
    metadata,
    Column("incident_id", String(255), primary_key=True),
    Column("override_json", JSON, nullable=False),
    Column("updated_at", String(64), nullable=False),
)

DEFAULT_FEEDBACK_STATE: Dict[str, Any] = {
    "thresholds": {
        "zero_result_repeat_count": 3,
        "request_latency_ms": 1000,
        "catalog_coverage_ratio": 0.95,
        "autocomplete_latency_ms": 350,
        "autocomplete_ctr_drop_ratio": -0.20,
        "semantic_index_coverage_ratio": 0.90,
        "semantic_embedding_sla_minutes": 240,
        "semantic_recall_floor": 0.60,
        "vector_latency_ms": 800,
        "personalization_fallback_rate": 0.30,
        "search_p95_latency_seconds_ceiling": 15.0,
        "max_active_signals": 10,
        "max_shadow_regressions": 0,
        "max_zero_result_total": 3,
    },
    "watchlists": {
        "queries": [],
        "synthetic_queries": [],
    },
    "approval_policy": {
        "auto_approval_max_severity": "low",
        "auto_approval_max_risk": "low",
        "manual_approval_capabilities": [],
        "updated_at": None,
    },
    "automation": {
        "enabled": True,
        "auto_promote_enabled": True,
        "auto_rollback_enabled": True,
        "last_evaluated_at": None,
        "last_guardrail_status": None,
        "last_action": None,
        "threshold_updates": [],
        "policy_updates": [],
    },
}


def _timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            future=True,
            pool_pre_ping=True,
        )
    return _engine


def _default_sections() -> Dict[str, Any]:
    return deepcopy(DEFAULT_FEEDBACK_STATE)


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return

    with _lock:
        if _tables_ready:
            return
        metadata.create_all(_get_engine())
        _tables_ready = True


def _merge_state(raw_rows: Dict[str, Any]) -> Dict[str, Any]:
    state = _default_sections()
    for key, payload in raw_rows.items():
        if isinstance(payload, dict) and isinstance(state.get(key), dict):
            state[key].update(deepcopy(payload))
        else:
            state[key] = deepcopy(payload)
    return state


def _load_state_from_storage() -> Dict[str, Any]:
    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            rows = connection.execute(
                select(feedback_state_table.c.key, feedback_state_table.c.state_json)
            ).mappings().all()
            existing = {str(row["key"]): deepcopy(row["state_json"]) for row in rows}
            defaults = _default_sections()
            for key, payload in defaults.items():
                if key not in existing:
                    connection.execute(
                        feedback_state_table.insert().values(
                            key=key,
                            state_json=deepcopy(payload),
                            updated_at=_timestamp(),
                        )
                    )
                    existing[key] = deepcopy(payload)
        return _merge_state(existing)
    except Exception:
        return _default_sections()


def _save_section(section: str, payload: Dict[str, Any]) -> None:
    global _state_cache
    now = _timestamp()
    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            existing = connection.execute(
                select(feedback_state_table.c.key).where(feedback_state_table.c.key == section)
            ).first()
            if existing:
                connection.execute(
                    update(feedback_state_table)
                    .where(feedback_state_table.c.key == section)
                    .values(state_json=deepcopy(payload), updated_at=now)
                )
            else:
                connection.execute(
                    feedback_state_table.insert().values(
                        key=section,
                        state_json=deepcopy(payload),
                        updated_at=now,
                    )
                )
    except Exception:
        pass

    state = get_feedback_state(force_refresh=False)
    state[section] = deepcopy(payload)
    _state_cache = state


def get_feedback_state(force_refresh: bool = False) -> Dict[str, Any]:
    global _state_cache
    if _state_cache is None or force_refresh:
        _state_cache = _load_state_from_storage()
    return deepcopy(_state_cache)


def get_threshold(name: str, default: Any = None) -> Any:
    state = get_feedback_state()
    return state.get("thresholds", {}).get(name, default)


def get_watchlists() -> Dict[str, List[Dict[str, Any]]]:
    state = get_feedback_state()
    watchlists = state.get("watchlists", {})
    return {
        "queries": deepcopy(watchlists.get("queries", [])),
        "synthetic_queries": deepcopy(watchlists.get("synthetic_queries", [])),
    }


def get_approval_policy() -> Dict[str, Any]:
    state = get_feedback_state()
    return deepcopy(state.get("approval_policy", {}))


def get_automation_policy() -> Dict[str, Any]:
    state = get_feedback_state()
    return deepcopy(state.get("automation", {}))


def get_incident_automation_override(incident_id: str) -> Dict[str, Any] | None:
    normalized = str(incident_id or "").strip()
    if not normalized:
        return None

    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            record = connection.execute(
                select(feedback_incident_override_table.c.override_json).where(
                    feedback_incident_override_table.c.incident_id == normalized
                )
            ).scalar_one_or_none()
        if record is None:
            _incident_override_cache.pop(normalized, None)
            return None
        override = deepcopy(record)
        _incident_override_cache[normalized] = deepcopy(override)
        return override
    except Exception:
        cached = _incident_override_cache.get(normalized)
        return deepcopy(cached) if cached else None


def get_effective_automation_policy(incident_id: str | None = None) -> Dict[str, Any]:
    effective = get_automation_policy()
    override = get_incident_automation_override(incident_id or "")
    if override:
        for key in ("enabled", "auto_promote_enabled", "auto_rollback_enabled"):
            if key in override and override[key] is not None:
                effective[key] = bool(override[key])
        effective["scope"] = "incident-override"
        effective["incident_id"] = incident_id
        effective["override_present"] = True
        effective["override_updated_at"] = override.get("updated_at")
        effective["override_note"] = override.get("note")
    else:
        effective["scope"] = "global-default"
        effective["incident_id"] = incident_id
        effective["override_present"] = False
        effective["override_updated_at"] = None
        effective["override_note"] = None
    return deepcopy(effective)


def set_incident_automation_override(
    incident_id: str,
    *,
    enabled: bool | None = None,
    auto_promote_enabled: bool | None = None,
    auto_rollback_enabled: bool | None = None,
    note: str = "",
    clear_override: bool = False,
) -> Dict[str, Any] | None:
    normalized = str(incident_id or "").strip()
    if not normalized:
        return None

    now = _timestamp()
    if clear_override:
        try:
            _ensure_tables()
            with _get_engine().begin() as connection:
                connection.execute(
                    delete(feedback_incident_override_table).where(
                        feedback_incident_override_table.c.incident_id == normalized
                    )
                )
        except Exception:
            pass
        _incident_override_cache.pop(normalized, None)
        return None

    existing = get_incident_automation_override(normalized) or {
        "incident_id": normalized,
        "enabled": None,
        "auto_promote_enabled": None,
        "auto_rollback_enabled": None,
        "note": "",
        "updated_at": None,
    }

    if enabled is not None:
        existing["enabled"] = bool(enabled)
    if auto_promote_enabled is not None:
        existing["auto_promote_enabled"] = bool(auto_promote_enabled)
    if auto_rollback_enabled is not None:
        existing["auto_rollback_enabled"] = bool(auto_rollback_enabled)
    if note.strip():
        existing["note"] = note.strip()
    existing["updated_at"] = now

    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            present = connection.execute(
                select(feedback_incident_override_table.c.incident_id).where(
                    feedback_incident_override_table.c.incident_id == normalized
                )
            ).first()
            if present:
                connection.execute(
                    update(feedback_incident_override_table)
                    .where(feedback_incident_override_table.c.incident_id == normalized)
                    .values(override_json=deepcopy(existing), updated_at=now)
                )
            else:
                connection.execute(
                    feedback_incident_override_table.insert().values(
                        incident_id=normalized,
                        override_json=deepcopy(existing),
                        updated_at=now,
                    )
                )
    except Exception:
        pass

    _incident_override_cache[normalized] = deepcopy(existing)
    return deepcopy(existing)


def set_threshold(name: str, value: Any, reason: str) -> bool:
    state = get_feedback_state()
    thresholds = deepcopy(state.get("thresholds", {}))
    previous = thresholds.get(name)
    if previous == value:
        return False
    thresholds[name] = value
    _save_section("thresholds", thresholds)

    automation = deepcopy(state.get("automation", {}))
    updates = list(automation.get("threshold_updates", []))
    updates.append(
        {
            "name": name,
            "previous": previous,
            "value": value,
            "reason": reason,
            "updated_at": _timestamp(),
        }
    )
    automation["threshold_updates"] = updates[-20:]
    automation["last_action"] = f"threshold:{name}"
    automation["last_evaluated_at"] = _timestamp()
    _save_section("automation", automation)
    return True


def add_watchlist_query(
    query: str,
    *,
    capability: str,
    severity: str,
    synthetic: bool = False,
    source: str = "feedback-automation",
) -> bool:
    normalized = str(query or "").strip()
    if not normalized or normalized == "unknown-query":
        return False

    state = get_feedback_state()
    watchlists = deepcopy(state.get("watchlists", {}))
    key = "synthetic_queries" if synthetic else "queries"
    existing = list(watchlists.get(key, []))
    if any(str(item.get("query", "")).strip().lower() == normalized.lower() for item in existing):
        return False

    existing.append(
        {
            "query": normalized,
            "capability": capability,
            "severity": severity,
            "source": source,
            "added_at": _timestamp(),
        }
    )
    watchlists[key] = existing[-100:]
    _save_section("watchlists", watchlists)
    return True


def set_manual_approval_capability(capability: str, required: bool = True) -> bool:
    normalized = str(capability or "").strip()
    if not normalized:
        return False

    state = get_feedback_state()
    policy = deepcopy(state.get("approval_policy", {}))
    capabilities = list(policy.get("manual_approval_capabilities", []))
    has_capability = normalized in capabilities

    if required and has_capability:
        return False
    if not required and not has_capability:
        return False

    if required:
        capabilities.append(normalized)
    else:
        capabilities = [item for item in capabilities if item != normalized]

    policy["manual_approval_capabilities"] = sorted(set(capabilities))
    policy["updated_at"] = _timestamp()
    _save_section("approval_policy", policy)

    state = get_feedback_state()
    automation = deepcopy(state.get("automation", {}))
    updates = list(automation.get("policy_updates", []))
    updates.append(
        {
            "capability": normalized,
            "required": required,
            "updated_at": _timestamp(),
        }
    )
    automation["policy_updates"] = updates[-20:]
    automation["last_action"] = f"approval-policy:{normalized}"
    automation["last_evaluated_at"] = _timestamp()
    _save_section("automation", automation)
    return True


def update_automation_metadata(**metadata_updates: Any) -> None:
    state = get_feedback_state()
    automation = deepcopy(state.get("automation", {}))
    automation.update(metadata_updates)
    automation["last_evaluated_at"] = _timestamp()
    _save_section("automation", automation)


def save_incident_outcome(record: Dict[str, Any]) -> bool:
    normalized = deepcopy(record)
    normalized.setdefault("updated_at", _timestamp())
    incident_id = str(normalized.get("incident_id") or "").strip()
    if not incident_id:
        return False

    existing_record: Dict[str, Any] | None = None
    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            existing = connection.execute(
                select(feedback_outcome_table.c.record_json).where(
                    feedback_outcome_table.c.incident_id == incident_id
                )
            ).scalar_one_or_none()
            if existing:
                existing_record = deepcopy(existing)
                connection.execute(
                    update(feedback_outcome_table)
                    .where(feedback_outcome_table.c.incident_id == incident_id)
                    .values(
                        outcome_status=normalized.get("outcome_status", "unknown"),
                        capability=normalized.get("capability", "unknown"),
                        signal_type=normalized.get("signal_type", "unknown"),
                        query=normalized.get("query", "unknown-query"),
                        updated_at=normalized["updated_at"],
                        record_json=deepcopy(normalized),
                    )
                )
            else:
                connection.execute(
                    feedback_outcome_table.insert().values(
                        incident_id=incident_id,
                        outcome_status=normalized.get("outcome_status", "unknown"),
                        capability=normalized.get("capability", "unknown"),
                        signal_type=normalized.get("signal_type", "unknown"),
                        query=normalized.get("query", "unknown-query"),
                        updated_at=normalized["updated_at"],
                        record_json=deepcopy(normalized),
                    )
                )
    except Exception:
        existing_record = None

    if existing_record == normalized:
        return False
    return True


def list_incident_outcomes(limit: int = 100) -> List[Dict[str, Any]]:
    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            rows = connection.execute(
                select(feedback_outcome_table.c.record_json)
                .order_by(desc(feedback_outcome_table.c.updated_at))
                .limit(limit)
            ).scalars().all()
        return [deepcopy(row) for row in rows]
    except Exception:
        return []
