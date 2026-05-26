from typing import Literal

from pydantic import BaseModel


class TemporalRefreshSubmission(BaseModel):
    incident_id: str
    note: str = ""


class TemporalPhaseSubmission(BaseModel):
    incident_id: str
    phase: Literal["shadow", "canary-5", "canary-25", "promote-100", "completed"]
    note: str = ""


class TemporalRollbackSubmission(BaseModel):
    incident_id: str
    reason: str
