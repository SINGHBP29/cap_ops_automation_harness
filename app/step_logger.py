import datetime
from typing import List, Dict, Any

# In‑memory list of step dicts (kept lightweight for dev)
_steps: List[Dict[str, Any]] = []

def record(step: str, details: Dict[str, Any] | None = None) -> None:
    """Append a new step record.
    * ``step`` – short name of the step (e.g. "search_start", "detector_run").
    * ``details`` – optional dict with extra context (query, latency, etc.).
    The list is trimmed to the most recent 200 entries.
    """
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "step": step,
        "details": details or {}
    }
    _steps.append(entry)
    if len(_steps) > 200:
        _steps.pop(0)

def get_steps() -> List[Dict[str, Any]]:
    """Return a shallow copy of the stored steps for API exposure."""
    return list(_steps)
