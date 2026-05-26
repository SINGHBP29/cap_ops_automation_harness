from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List


@dataclass
class FocusedEvidenceWindow:
    focus: str
    sources: List[str]
    snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeActStep:
    name: str
    status: str
    summary: str
    output: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RLMSubtaskResult:
    key: str
    title: str
    status: str
    summary: str
    confidence: str
    evidence_window: FocusedEvidenceWindow
    codeact_steps: List[CodeActStep] = field(default_factory=list)
    findings: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)


@dataclass
class OwnerPath:
    primary_owner: str
    secondary_owner: str
    approver: str
    escalation_path: List[str] = field(default_factory=list)


@dataclass
class RLMParentSynthesis:
    incident_shape: str
    affected_capability: str
    capability_family: str
    data_gap: str
    metric_impact: List[str]
    owner_path: OwnerPath
    likely_root_cause: str
    recommended_fix_path: List[str]
    rollout_readiness: str
    business_impact: str
    confidence: str
    narrative: str | None = None


@dataclass
class RLMIncidentAnalysis:
    generated_at: str
    incident_id: str
    mode: str
    active_signal_types: List[str]
    signals_considered: int
    evidence_sources: List[str]
    subtasks: List[RLMSubtaskResult]
    synthesis: RLMParentSynthesis
    llm_enrichment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
