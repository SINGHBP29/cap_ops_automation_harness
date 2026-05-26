from __future__ import annotations

from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.base import RLMIncidentContext
from app.services.intelligence_pipeline import CAPABILITY_OWNERS
from app.services.rlm_models import CodeActStep
from app.services.rlm_models import RLMSubtaskResult


class OwnerPathAgent(BaseRLMSubtask):
    key = "owner_path"
    title = "Owner Path"
    focus = "Map the incident to an owner chain, approval route, and current rollout gate."
    evidence_sources = ("runbook", "evaluation", "approval_state", "temporal_release")

    async def analyze(self, context: RLMIncidentContext) -> RLMSubtaskResult:
        capability = str(context.diagnosis.get("affected_capability", "unknown"))
        runbook_owner = context.runbook.get("owner", {})
        owner_defaults = CAPABILITY_OWNERS.get(
            capability,
            {
                "primary_owner": runbook_owner.get("primary_owner", "Application owner"),
                "secondary_owner": runbook_owner.get("secondary_owner", "Platform owner"),
                "approver": runbook_owner.get("approver", "Engineering lead"),
            },
        )

        primary_owner = str(runbook_owner.get("primary_owner") or owner_defaults["primary_owner"])
        secondary_owner = str(runbook_owner.get("secondary_owner") or owner_defaults["secondary_owner"])
        approver = str(runbook_owner.get("approver") or owner_defaults["approver"])

        approval_workflow = context.evaluation.get("approval_workflow", {})
        release_phase = str(context.traffic_router_status.get("release_phase", "shadow"))
        blocked_reason = context.traffic_router_status.get("blocked_reason")
        escalation_path = [primary_owner, secondary_owner, approver]
        if blocked_reason:
            escalation_path.append("Release operator")

        summary = (
            f"{primary_owner} owns the fix path, {secondary_owner} validates the service side, "
            f"and {approver} is the human approval route."
        )
        if blocked_reason:
            summary += f" Current rollout gate is blocked: {blocked_reason}"

        return self._result(
            status="ok" if not blocked_reason else "blocked",
            summary=summary,
            confidence="high",
            evidence_window=self._window(
                {
                    "capability": capability,
                    "release_phase": release_phase,
                    "approval_route": approval_workflow.get("route_for_approval"),
                    "approval_state": approval_workflow.get("approval_state"),
                    "blocked_reason": blocked_reason,
                }
            ),
            codeact_steps=[
                CodeActStep(
                    name="owner-resolution",
                    status="ok",
                    summary="Resolved the owner chain from the runbook capability mapping.",
                    output={
                        "primary_owner": primary_owner,
                        "secondary_owner": secondary_owner,
                        "approver": approver,
                    },
                ),
                CodeActStep(
                    name="release-gate-read",
                    status="ok" if not blocked_reason else "warning",
                    summary="Read the current release phase and approval gate from the traffic router state.",
                    output={
                        "release_phase": release_phase,
                        "blocked_reason": blocked_reason,
                    },
                ),
            ],
            findings={
                "primary_owner": primary_owner,
                "secondary_owner": secondary_owner,
                "approver": approver,
                "approval_route": approval_workflow.get("route_for_approval"),
                "release_phase": release_phase,
                "blocked_reason": blocked_reason,
                "escalation_path": escalation_path,
            },
            recommended_actions=[
                f"{primary_owner} should confirm whether '{context.incident_query}' is a real customer query or synthetic traffic.",
                f"{secondary_owner} should validate traces, indexing health, and the shadow candidate path.",
                f"{approver} should review business impact only after the eval dataset and shadow checks pass.",
            ],
        )
