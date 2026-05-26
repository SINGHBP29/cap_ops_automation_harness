from __future__ import annotations

from typing import Any
from typing import Dict

from temporalio import activity

from app.services.feedback_automation_service import FeedbackAutomationService
from app.services.controlled_release_service import build_controlled_release_packet_from_incident
from app.services.shadow_testing_service import build_shadow_test_report


@activity.defn
async def collect_release_context_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    incident_packet = payload["incident_packet"]
    current_phase = str(payload.get("current_phase", "shadow"))
    approval = payload.get("approval")
    controlled_release_packet = await build_controlled_release_packet_from_incident(
        incident_packet=incident_packet,
        record_audit=False,
    )
    shadow_test = await build_shadow_test_report(incident_packet=incident_packet)
    automation = FeedbackAutomationService().evaluate(
        incident_packet=incident_packet,
        controlled_release_packet=controlled_release_packet,
        shadow_test=shadow_test,
        current_phase=current_phase,
        approval=approval,
    )
    return {
        "controlled_release_packet": controlled_release_packet,
        "shadow_test": shadow_test,
        "automation": automation,
    }
