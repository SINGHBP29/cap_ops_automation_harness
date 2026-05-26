"""Compatibility exports for the split RLM agents package."""

from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.base import RLMIncidentContext
from app.diagnosis.agents.capability_agent import CapabilityImpactAgent
from app.diagnosis.agents.data_gap_rule_diff_agent import DataGapRuleDiffAgent
from app.diagnosis.agents.helpers import looks_synthetic_query
from app.diagnosis.agents.metric_impact_agent import MetricImpactAgent
from app.diagnosis.agents.owner_path_agent import OwnerPathAgent
from app.diagnosis.agents.registry import default_rlm_agents

CapabilityImpactSubtask = CapabilityImpactAgent
DataGapSubtask = DataGapRuleDiffAgent
MetricImpactSubtask = MetricImpactAgent
OwnerPathSubtask = OwnerPathAgent


def default_rlm_subtasks():
    return default_rlm_agents()


__all__ = [
    "BaseRLMSubtask",
    "CapabilityImpactAgent",
    "CapabilityImpactSubtask",
    "DataGapRuleDiffAgent",
    "DataGapSubtask",
    "MetricImpactAgent",
    "MetricImpactSubtask",
    "OwnerPathAgent",
    "OwnerPathSubtask",
    "RLMIncidentContext",
    "default_rlm_agents",
    "default_rlm_subtasks",
    "looks_synthetic_query",
]
