from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException

from app.models.feedback import FeedbackIncidentAutomationSubmission
from app.services.operator_console_service import get_feedback_outcomes_view
from app.services.operator_console_service import get_feedback_state_view
from app.services.operator_console_service import update_incident_automation_controls

router = APIRouter()


@router.get("/feedback-state")
async def feedback_state(incident_id: str | None = None):
    return get_feedback_state_view(incident_id)


@router.get("/feedback-outcomes")
async def feedback_outcomes(limit: int = 50):
    return get_feedback_outcomes_view(limit)


@router.post("/feedback-incident-controls")
async def feedback_incident_controls(submission: FeedbackIncidentAutomationSubmission):
    try:
        return update_incident_automation_controls(submission)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
