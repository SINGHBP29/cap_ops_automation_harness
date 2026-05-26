from __future__ import annotations

from pydantic import BaseModel


class FeedbackIncidentAutomationSubmission(BaseModel):
    incident_id: str
    enabled: bool | None = None
    auto_promote_enabled: bool | None = None
    auto_rollback_enabled: bool | None = None
    note: str = ""
    clear_override: bool = False
