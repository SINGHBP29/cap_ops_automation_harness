from pydantic import BaseModel
from typing import Optional
from typing import Dict
from typing import Any


class OpsSignal(BaseModel):
    signal_type: str
    severity: str
    capability: str
    query: Optional[str] = None
    signal_origin: str = "unknown"
    signal_emitter: Optional[str] = None
    source_event_id: Optional[str] = None
    created_at: Optional[str] = None
    evidence: Dict[str, Any]
