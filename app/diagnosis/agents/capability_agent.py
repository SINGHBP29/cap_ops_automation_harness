from __future__ import annotations

from typing import Dict

from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.base import RLMIncidentContext
from app.diagnosis.agents.helpers import capability_family
from app.diagnosis.agents.helpers import infer_capability_from_signal
from app.services.rlm_models import CodeActStep
from app.services.rlm_models import RLMSubtaskResult


class CapabilityImpactAgent(BaseRLMSubtask):
    key = "affected_capability"
    title = "Affected Capability"
    focus = "Correlate the live signal stream to the most affected capability family."
    evidence_sources = ("ops_ledger", "incident_packet", "diagnostics")

    async def analyze(self, context: RLMIncidentContext) -> RLMSubtaskResult:
        signals = [signal for signal in context.recent_signals if (signal.get("signal_type") or signal.get("type")) != "test"]
        capability_votes: Dict[str, int] = {}
        family_votes: Dict[str, int] = {}

        for signal in signals:
            signal_type = str(signal.get("signal_type") or signal.get("type") or "unknown")
            capability = str(signal.get("capability") or infer_capability_from_signal(signal_type))
            family = capability_family(signal_type=signal_type, capability=capability)
            capability_votes[capability] = capability_votes.get(capability, 0) + 1
            family_votes[family] = family_votes.get(family, 0) + 1

        primary_capability = str(context.diagnosis.get("affected_capability", "unknown"))
        primary_family = capability_family(signal_type=context.signal_type, capability=primary_capability)
        incident_shape = "multi-signal" if len(family_votes) > 1 or len(capability_votes) > 1 else "single-signal"
        top_family = max(family_votes, key=family_votes.get) if family_votes else primary_family

        summary = (
            f"{incident_shape.title()} incident. The dominant capability is '{primary_capability}' "
            f"inside the '{top_family}' family."
        )
        if incident_shape == "single-signal":
            summary += " No correlated autocomplete, catalog, or merchandising-control signal is currently stronger."

        return self._result(
            status="ok",
            summary=summary,
            confidence="high" if signals else "medium",
            evidence_window=self._window(
                {
                    "signal_type": context.signal_type,
                    "primary_capability": primary_capability,
                    "health_rating": context.diagnostics_report.get("health_rating"),
                    "signals_seen": len(signals),
                    "family_votes": family_votes,
                    "capability_votes": capability_votes,
                }
            ),
            codeact_steps=[
                CodeActStep(
                    name="signal-correlation",
                    status="ok",
                    summary="Grouped live signals by capability and capability family.",
                    output={
                        "signals_seen": len(signals),
                        "family_votes": family_votes,
                        "capability_votes": capability_votes,
                    },
                ),
            ],
            findings={
                "incident_shape": incident_shape,
                "affected_capability": primary_capability,
                "capability_family": top_family,
                "capability_votes": capability_votes,
                "family_votes": family_votes,
            },
            recommended_actions=[
                f"Keep the primary investigation centered on '{primary_capability}'.",
                "Add more signals before widening the incident to a cross-capability outage.",
            ],
        )
