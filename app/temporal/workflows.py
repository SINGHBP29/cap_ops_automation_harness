from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any
from typing import Dict

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities import collect_release_context_activity


@workflow.defn
class ControlledReleaseWorkflow:
    def __init__(self) -> None:
        self._incident_packet: Dict[str, Any] = {}
        self._approval: Dict[str, Any] | None = None
        self._release_phase = "shadow"
        self._auto_refresh_seconds = 20.0
        self._rollback_reason: str | None = None
        self._refresh_requested = True
        self._terminal = False
        self._snapshot: Dict[str, Any] = {}
        self._history: list[Dict[str, str]] = []

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._incident_packet = dict(payload["incident_packet"])
        self._release_phase = payload.get("initial_phase", "shadow")
        self._auto_refresh_seconds = float(payload.get("auto_refresh_seconds", 20.0) or 20.0)
        self._approval = payload.get("initial_approval")
        self._append_history(
            "workflow-started",
            f"Temporal workflow created for incident {self._incident_packet['incident_id']}.",
        )

        while True:
            if self._refresh_requested:
                self._refresh_requested = False
                await self._refresh_snapshot()
                if self._terminal:
                    self._append_history("workflow-completed", self._snapshot["workflow_status"])
                    self._snapshot["history"] = list(self._history)
                    self._snapshot["updated_at"] = self._timestamp()
                    return self._snapshot

            try:
                await workflow.wait_condition(
                    lambda: self._refresh_requested,
                    timeout=self._auto_refresh_seconds,
                    timeout_summary="controlled-release-auto-refresh",
                )
            except asyncio.TimeoutError:
                self._append_history(
                    "auto-refresh-requested",
                    "Periodic workflow refresh requested for feedback automation and rollout guardrails.",
                )
                self._refresh_requested = True

    @workflow.signal
    def record_approval(self, approval: Dict[str, Any]) -> None:
        self._approval = dict(approval)
        self._append_history(
            "approval-recorded",
            f"{approval.get('decision', 'unknown')} by {approval.get('reviewer', 'unknown')}.",
        )
        self._refresh_requested = True

    @workflow.signal
    def advance_release(self, payload: Dict[str, Any]) -> None:
        phase = str(payload.get("phase", "") or "").strip()
        note = str(payload.get("note", "") or "").strip()
        if phase:
            self._release_phase = phase
        detail = note or f"Release phase moved to {self._release_phase}."
        self._append_history("release-advanced", detail)
        self._refresh_requested = True

    @workflow.signal
    def trigger_rollback(self, reason: str) -> None:
        self._rollback_reason = reason.strip() or "Rollback requested by operator."
        self._release_phase = "rollback"
        self._append_history("rollback-triggered", self._rollback_reason)
        self._refresh_requested = True

    @workflow.signal
    def request_refresh(self, note: str = "") -> None:
        detail = note.strip() or "Workflow refresh requested."
        self._append_history("refresh-requested", detail)
        self._refresh_requested = True

    @workflow.query
    def snapshot(self) -> Dict[str, Any]:
        return dict(self._snapshot)

    async def _refresh_snapshot(self) -> None:
        context = await workflow.execute_activity(
            collect_release_context_activity,
            {
                "incident_packet": self._incident_packet,
                "current_phase": self._release_phase,
                "approval": self._approval,
            },
            start_to_close_timeout=timedelta(seconds=90),
        )

        shadow_test = context["shadow_test"]
        automation = context.get("automation", {})
        auto_action = automation.get("auto_action", {})
        if auto_action.get("type") == "rollback" and not self._rollback_reason:
            self._rollback_reason = str(auto_action.get("reason") or "Feedback automation requested rollback.")
            self._release_phase = "rollback"
            self._append_history("auto-rollback-triggered", self._rollback_reason)
        elif auto_action.get("type") == "advance-release":
            target_phase = str(auto_action.get("target_phase") or "").strip()
            if target_phase and target_phase != self._release_phase:
                self._release_phase = target_phase
                self._append_history(
                    "auto-release-advanced",
                    str(auto_action.get("reason") or f"Automatically advanced to {target_phase}."),
                )

        shadow_summary = shadow_test.get("summary", {})
        workflow_status = self._determine_workflow_status(shadow_summary)

        self._append_history(
            "context-refreshed",
            f"Shadow status is {shadow_summary.get('shadow_status', 'unknown')} and release phase is {self._release_phase}.",
        )

        self._snapshot = {
            "available": True,
            "incident_id": self._incident_packet["incident_id"],
            "workflow_status": workflow_status,
            "release_phase": self._release_phase,
            "approval": self._approval,
            "shadow_ready": shadow_summary.get("shadow_ready", False),
            "shadow_status": shadow_summary.get("shadow_status", "unknown"),
            "ready_for_canary": shadow_summary.get("ready_for_canary", False),
            "recommended_next_step": shadow_test.get("recommended_next_step"),
            "automation": automation,
            "history": list(self._history),
            "updated_at": self._timestamp(),
        }

    def _determine_workflow_status(self, shadow_summary: Dict[str, Any]) -> str:
        if self._rollback_reason:
            self._terminal = True
            return "rolled-back"

        if self._release_phase == "completed":
            self._terminal = True
            return "completed"

        if self._approval is None:
            return "awaiting-human-approval"

        decision = self._approval.get("decision", "pending")
        if decision == "rejected":
            return "rejected"
        if decision == "changes-requested":
            return "changes-requested"
        if decision != "approved":
            return "awaiting-human-approval"

        if not shadow_summary.get("shadow_ready", False):
            return "approved-blocked-shadow"
        if self._release_phase == "shadow":
            return "approved-ready-for-canary"
        return f"in-{self._release_phase}"

    def _append_history(self, event: str, detail: str) -> None:
        self._history.append(
            {
                "at": self._timestamp(),
                "event": event,
                "detail": detail,
            }
        )
        if len(self._history) > 40:
            self._history = self._history[-40:]

    def _timestamp(self) -> str:
        return workflow.now().isoformat()
