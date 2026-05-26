from __future__ import annotations

from typing import List

from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.capability_agent import CapabilityImpactAgent
from app.diagnosis.agents.data_gap_rule_diff_agent import DataGapRuleDiffAgent
from app.diagnosis.agents.metric_impact_agent import MetricImpactAgent
from app.diagnosis.agents.owner_path_agent import OwnerPathAgent


def default_rlm_agents() -> List[BaseRLMSubtask]:
    return [
        CapabilityImpactAgent(),
        DataGapRuleDiffAgent(),
        MetricImpactAgent(),
        OwnerPathAgent(),
    ]
