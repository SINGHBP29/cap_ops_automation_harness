from __future__ import annotations

from typing import Any
from typing import Dict

from app.models.approval import ApprovalSubmission
from app.models.feedback import FeedbackIncidentAutomationSubmission
from app.operator_ui.console_service import OperatorConsoleService

_service = OperatorConsoleService()


async def build_operator_console_data(use_llm: bool = True, operator_query: str | None = None) -> Dict[str, Any]:
    return await _service.build_console_data(use_llm=use_llm, operator_query=operator_query)


def record_human_approval(submission: ApprovalSubmission) -> Dict[str, Any]:
    return _service.record_human_approval(submission)


def get_feedback_state_view(incident_id: str | None = None) -> Dict[str, Any]:
    return _service.feedback_state_view(incident_id)


def get_feedback_outcomes_view(limit: int = 50) -> Dict[str, Any]:
    return _service.feedback_outcomes_view(limit)


def update_incident_automation_controls(
    submission: FeedbackIncidentAutomationSubmission,
) -> Dict[str, Any]:
    return _service.update_incident_automation_controls(submission)
