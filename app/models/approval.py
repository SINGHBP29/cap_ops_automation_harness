from typing import Literal

from pydantic import BaseModel


class ApprovalSubmission(BaseModel):
    incident_id: str
    reviewer: str
    decision: Literal["approved", "changes-requested", "rejected"]
    rationale: str = ""
    reviewed_business_impact: bool = False
    reviewed_business_guardrails: bool = False
