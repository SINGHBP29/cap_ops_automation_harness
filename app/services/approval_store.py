from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text
from sqlalchemy import create_engine
from sqlalchemy import desc
from sqlalchemy import select

from app.config import settings

APPROVAL_MEMORY_LOG: List[Dict[str, Any]] = []
APPROVAL_MEMORY_LIMIT = 200
_approval_lock = Lock()
_approval_engine = None
_approval_tables_ready = False

approval_metadata = MetaData()
approval_table = Table(
    "controlled_release_approval_log",
    approval_metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("incident_id", String(255), nullable=False, index=True),
    Column("reviewer", String(255), nullable=False),
    Column("decision", String(64), nullable=False),
    Column("rationale", Text, nullable=False, default=""),
    Column("reviewed_business_impact", Boolean, nullable=False, default=False),
    Column("reviewed_business_guardrails", Boolean, nullable=False, default=False),
    Column("created_at", String(64), nullable=False),
)


def _get_engine():
    global _approval_engine
    if _approval_engine is None:
        _approval_engine = create_engine(
            settings.DATABASE_URL,
            future=True,
            pool_pre_ping=True,
        )
    return _approval_engine


def _ensure_tables() -> None:
    global _approval_tables_ready

    if _approval_tables_ready:
        return

    with _approval_lock:
        if _approval_tables_ready:
            return
        approval_metadata.create_all(_get_engine())
        _approval_tables_ready = True


def save_approval_decision(record: Dict[str, Any]) -> Dict[str, Any]:
    APPROVAL_MEMORY_LOG.append(deepcopy(record))
    if len(APPROVAL_MEMORY_LOG) > APPROVAL_MEMORY_LIMIT:
        APPROVAL_MEMORY_LOG.pop(0)

    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            connection.execute(
                approval_table.insert().values(
                    incident_id=record.get("incident_id", ""),
                    reviewer=record.get("reviewer", ""),
                    decision=record.get("decision", ""),
                    rationale=record.get("rationale", ""),
                    reviewed_business_impact=record.get("reviewed_business_impact", False),
                    reviewed_business_guardrails=record.get("reviewed_business_guardrails", False),
                    created_at=record.get("created_at", ""),
                )
            )
    except Exception:
        return record

    return record


def get_latest_approval(incident_id: str) -> Optional[Dict[str, Any]]:
    try:
        _ensure_tables()
        with _get_engine().begin() as connection:
            row = connection.execute(
                select(
                    approval_table.c.incident_id,
                    approval_table.c.reviewer,
                    approval_table.c.decision,
                    approval_table.c.rationale,
                    approval_table.c.reviewed_business_impact,
                    approval_table.c.reviewed_business_guardrails,
                    approval_table.c.created_at,
                )
                .where(approval_table.c.incident_id == incident_id)
                .order_by(desc(approval_table.c.id))
                .limit(1)
            ).mappings().first()

        if row:
            return dict(row)
    except Exception:
        pass

    for record in reversed(APPROVAL_MEMORY_LOG):
        if record.get("incident_id") == incident_id:
            return deepcopy(record)

    return None


def get_approval_backend() -> str:
    try:
        _ensure_tables()
        return "postgres"
    except Exception:
        return "memory"
