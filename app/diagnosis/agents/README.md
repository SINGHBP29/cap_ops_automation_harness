# RLM Agents

This folder contains the four specialized RLM agents and the parent LangGraph workflow.

Agents:

- [capability_agent.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/capability_agent.py)
- [data_gap_rule_diff_agent.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/data_gap_rule_diff_agent.py)
- [metric_impact_agent.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/metric_impact_agent.py)
- [owner_path_agent.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/owner_path_agent.py)

Parent workflow:

- [graph.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/graph.py)

The graph uses `LangGraph` so the system follows a standard agent-orchestration framework while keeping the evidence-gathering logic deterministic.
