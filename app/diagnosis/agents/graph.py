from __future__ import annotations

from typing import List
from typing import Sequence
from typing import TypedDict

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.base import RLMIncidentContext
from app.services.rlm_models import RLMSubtaskResult


class RLMGraphState(TypedDict, total=False):
    context: RLMIncidentContext
    capability_result: RLMSubtaskResult
    data_gap_result: RLMSubtaskResult
    metric_impact_result: RLMSubtaskResult
    owner_path_result: RLMSubtaskResult
    subtask_results: List[RLMSubtaskResult]


def build_rlm_agent_graph(subtasks: Sequence[BaseRLMSubtask]):
    by_key = {subtask.key: subtask for subtask in subtasks}
    required_keys = {
        "affected_capability": "capability_result",
        "data_gap": "data_gap_result",
        "metric_impact": "metric_impact_result",
        "owner_path": "owner_path_result",
    }
    missing = [key for key in required_keys if key not in by_key]
    if missing:
        raise ValueError(f"Missing required RLM agents for LangGraph orchestration: {', '.join(sorted(missing))}")

    graph = StateGraph(RLMGraphState)
    graph.add_node("capability_agent", _agent_node(by_key["affected_capability"], "capability_result"))
    graph.add_node("data_gap_agent", _agent_node(by_key["data_gap"], "data_gap_result"))
    graph.add_node("metric_impact_agent", _agent_node(by_key["metric_impact"], "metric_impact_result"))
    graph.add_node("owner_path_agent", _agent_node(by_key["owner_path"], "owner_path_result"))
    graph.add_node("parent_agent", _parent_agent)

    graph.add_edge(START, "capability_agent")
    graph.add_edge("capability_agent", "data_gap_agent")
    graph.add_edge("data_gap_agent", "metric_impact_agent")
    graph.add_edge("metric_impact_agent", "owner_path_agent")
    graph.add_edge("owner_path_agent", "parent_agent")
    graph.add_edge("parent_agent", END)
    return graph.compile()


def _agent_node(agent: BaseRLMSubtask, result_key: str):
    async def run(state: RLMGraphState) -> RLMGraphState:
        return {result_key: await agent.analyze(state["context"])}

    return run


async def _parent_agent(state: RLMGraphState) -> RLMGraphState:
    return {
        "subtask_results": [
            state["capability_result"],
            state["data_gap_result"],
            state["metric_impact_result"],
            state["owner_path_result"],
        ]
    }
