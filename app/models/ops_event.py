from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class RawOpsEvent(BaseModel):
    source_type: str
    event_type: str
    capability: Optional[str] = None
    origin: Optional[str] = None
    severity: str = "info"
    query: Optional[str] = None
    session_id: Optional[str] = None
    entity_id: Optional[str] = None
    release_phase: str = "baseline"
    metrics: Dict[str, Any] = Field(default_factory=dict)
    facts: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
