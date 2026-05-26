import logging
from copy import deepcopy
from typing import Any
from typing import Dict
from typing import List

from app.monitoring.metrics import ACTIVE_SIGNALS
from app.monitoring.metrics import SIGNALS_TOTAL

logger = logging.getLogger(__name__)

# Temporary in-memory storage for raw ops events and derived signals.
recent_events: List[Dict[str, Any]] = []
RECENT_EVENT_LIMIT = 500
recent_signals: List[Dict[str, Any]] = []
RECENT_SIGNAL_LIMIT = 100

ACTIVE_SIGNALS.set(0)


async def store_event(event: Dict[str, Any]) -> None:
    logger.info(
        "ops_event_ingested",
        extra={
            "event": event
        }
    )

    recent_events.append(deepcopy(event))
    if len(recent_events) > RECENT_EVENT_LIMIT:
        recent_events.pop(0)


async def store_signal(signal: Dict[str, Any]) -> None:

    logger.info(
        "ops_signal_generated",
        extra={
            "signal": signal
        }
    )

    print("\n===== OPS SIGNAL =====")
    print(signal)
    
    signal_type = signal.get("signal_type") or signal.get("type") or "unknown"
    severity = signal.get("severity") or "info"
    SIGNALS_TOTAL.labels(signal_type=signal_type, severity=severity).inc()

    # Store in temporary list, keeping only the last 100
    recent_signals.append(deepcopy(signal))
    if len(recent_signals) > RECENT_SIGNAL_LIMIT:
        recent_signals.pop(0)

    ACTIVE_SIGNALS.set(len(recent_signals))


def ledger_snapshot() -> Dict[str, Any]:
    signal_counts_by_origin: Dict[str, int] = {}
    event_counts_by_origin: Dict[str, int] = {}

    for event in recent_events:
        origin = str(event.get("event_origin") or event.get("metadata", {}).get("event_origin") or "unknown")
        event_counts_by_origin[origin] = event_counts_by_origin.get(origin, 0) + 1

    for signal in recent_signals:
        origin = str(signal.get("signal_origin") or "unknown")
        signal_counts_by_origin[origin] = signal_counts_by_origin.get(origin, 0) + 1

    return {
        "recent_events": deepcopy(recent_events),
        "recent_signals": deepcopy(recent_signals),
        "event_count": len(recent_events),
        "signal_count": len(recent_signals),
        "event_counts_by_origin": event_counts_by_origin,
        "signal_counts_by_origin": signal_counts_by_origin,
    }


def list_signals(signal_origin: str | None = None) -> List[Dict[str, Any]]:
    if signal_origin is None:
        return deepcopy(recent_signals)
    return [
        deepcopy(signal)
        for signal in recent_signals
        if str(signal.get("signal_origin") or "unknown") == signal_origin
    ]
