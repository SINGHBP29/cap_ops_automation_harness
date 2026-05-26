from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any
from typing import Dict
from typing import List

from sqlalchemy import JSON
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy import select

from app.config import settings

CONTROLLED_RELEASE_AUDIT_LOG: List[Dict[str, Any]] = []
CONTROLLED_RELEASE_AUDIT_LIMIT = 200
_ledger_lock = Lock()
_engine = None
_tables_ready = False

metadata = MetaData()
controlled_release_audit_table = Table(
    "controlled_release_audit_log",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", String(64), nullable=False),
    Column("source_signal", String(128), nullable=False),
    Column("runbook_version", String(32), nullable=False),
    Column("eval_report", String(64), nullable=False),
    Column("approver", String(255), nullable=False),
    Column("rollout_timeline", JSON, nullable=False),
    Column("rollback_events", JSON, nullable=False),
    Column("record_json", JSON, nullable=False),
)


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            future=True,
            pool_pre_ping=True,
        )
    return _engine


def _ensure_tables() -> None:
    global _tables_ready

    if _tables_ready:
        return

    with _ledger_lock:
        if _tables_ready:
            return
        metadata.create_all(_get_engine())
        _tables_ready = True


def append_controlled_release_record(record: Dict[str, Any]) -> None:
    CONTROLLED_RELEASE_AUDIT_LOG.append(deepcopy(record))
    if len(CONTROLLED_RELEASE_AUDIT_LOG) > CONTROLLED_RELEASE_AUDIT_LIMIT:
        CONTROLLED_RELEASE_AUDIT_LOG.pop(0)

    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            connection.execute(
                controlled_release_audit_table.insert().values(
                    created_at=record.get("created_at", ""),
                    source_signal=record.get("source_signal", "unknown"),
                    runbook_version=record.get("runbook_version", "v1"),
                    eval_report=record.get("eval_report", "unknown"),
                    approver=record.get("approver", "unknown"),
                    rollout_timeline=record.get("rollout_timeline", []),
                    rollback_events=record.get("rollback_events", []),
                    record_json=deepcopy(record),
                )
            )
    except Exception:
        # Fall back to the in-memory ledger if the database is unavailable.
        return


def list_controlled_release_records() -> List[Dict[str, Any]]:
    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            rows = connection.execute(
                select(controlled_release_audit_table.c.record_json)
                .order_by(controlled_release_audit_table.c.id.desc())
                .limit(CONTROLLED_RELEASE_AUDIT_LIMIT)
            ).scalars().all()

        return [deepcopy(record) for record in reversed(rows)]
    except Exception:
        return deepcopy(CONTROLLED_RELEASE_AUDIT_LOG)


def get_controlled_release_audit_backend() -> str:
    try:
        _ensure_tables()
        return "postgres"
    except Exception:
        return "memory"
