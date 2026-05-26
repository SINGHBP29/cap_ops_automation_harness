from typing import Any
from typing import Dict
from typing import Literal
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


CapabilityName = Literal[
    "catalog",
    "autocomplete",
    "semantic_search",
    "semantic_index",
    "personalization",
    "merchandising",
]


class CapabilitySignalEvent(BaseModel):
    capability: CapabilityName
    event_type: str = "live_telemetry"
    query: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    release_phase: str = "baseline"
    metrics: Dict[str, Any] = Field(default_factory=dict)
    facts: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
