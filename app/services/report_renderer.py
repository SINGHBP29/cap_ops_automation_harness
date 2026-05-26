from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List


def _bullet_list(items: List[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def render_incident_packet_markdown(packet: Dict[str, Any]) -> str:
    diagnosis = packet["diagnosis"]
    runbook = packet["runbook"]
    evaluation = packet["evaluation"]
    llm_enrichment = packet.get("llm_enrichment", {})

    lines = [
        f"# Incident Report: {packet['incident_id']}",
        "",
        "## Summary",
        f"- Health rating: `{packet['health_rating']}`",
        f"- Signal type: `{diagnosis['signal_type']}`",
        f"- Severity: `{diagnosis['severity']}`",
        f"- Affected capability: `{diagnosis['affected_capability']}`",
        f"- Confidence: `{diagnosis['confidence']}`",
        "",
        "## Root Cause",
        diagnosis["root_cause"],
        "",
        "## Impact",
        diagnosis["impact_summary"],
        "",
        "## Candidate Fix",
        _bullet_list(runbook["candidate_fix"]),
        "",
        "## Owner",
        f"- Primary owner: {runbook['owner']['primary_owner']}",
        f"- Secondary owner: {runbook['owner']['secondary_owner']}",
        f"- Approver: {runbook['owner']['approver']}",
        "",
        "## Evaluation Dataset",
        f"- Positive queries: {', '.join(runbook['eval_dataset']['positive_queries'])}",
        f"- Incident queries: {', '.join(runbook['eval_dataset']['incident_queries'])}",
        f"- Negative controls: {', '.join(runbook['eval_dataset']['negative_controls'])}",
        "",
        "## Success Criteria",
        _bullet_list(runbook["eval_dataset"]["success_criteria"]),
        "",
        "## Rollback Plan",
        _bullet_list(runbook["rollback_plan"]),
        "",
        "## Approval Workflow",
        f"- Status: `{evaluation['approval_workflow']['approval_state']}`",
        f"- Route for approval: {evaluation['approval_workflow']['route_for_approval']}",
        f"- Auto-approval eligible: `{evaluation['approval_workflow']['auto_approval_eligible']}`",
        f"- Release window: {evaluation['approval_workflow']['release_window']}",
    ]

    if llm_enrichment.get("used") and llm_enrichment.get("content"):
        content = llm_enrichment["content"]
        lines.extend(
            [
                "",
                "## LLM Enrichment",
                f"- Provider: `{llm_enrichment['provider']}`",
                f"- Model: `{llm_enrichment['model']}`",
                "",
                content.get("executive_summary", ""),
                "",
                "### Release Recommendation",
                content.get("release_recommendation", ""),
            ]
        )

    return "\n".join(lines).strip() + "\n"


def render_controlled_release_markdown(packet: Dict[str, Any]) -> str:
    source_incident = packet["source_incident"]
    approval = packet["approval"]
    release = packet["release"]
    observation = packet["observation"]
    audit_record = packet["audit_record"]
    learning = packet["learning"]
    llm_enrichment = packet.get("llm_enrichment", {})

    lines = [
        f"# Controlled Release Report: {packet['release_id']}",
        "",
        "## Source Incident",
        f"- Incident ID: `{source_incident['incident_id']}`",
        f"- Signal type: `{source_incident['signal_type']}`",
        f"- Severity: `{source_incident['severity']}`",
        f"- Capability: `{source_incident['affected_capability']}`",
        f"- Risk level: `{source_incident['risk_level']}`",
        "",
        "## Approval",
        f"- Status: `{approval['status']}`",
        f"- Approver: {approval['approver']}",
        f"- Auto-approval eligible: `{approval['auto_approval_eligible']}`",
        f"- Rationale: {approval['rationale']}",
        "",
        "## Required Actions",
        _bullet_list(approval["required_actions"]),
        "",
        "## Release Plan",
        f"- Current phase: `{release['current_phase']}`",
        "",
        "### Adapter Actions",
        _bullet_list(release["adapter_actions"]),
        "",
        "### Promotion Checks",
        _bullet_list(release["promotion_checks"]),
        "",
        "### Rollout Timeline",
        _bullet_list(
            [
                f"{stage['name']} ({stage['traffic_percent']}): {stage['promotion_check']}"
                for stage in release["traffic_router"]
            ]
        ),
        "",
        "## Observation",
        f"- Baseline collected at: {observation['baseline_collected_at']}",
        "",
        "### Live Watchlist",
        _bullet_list(observation["live_watchlist"]),
        "",
        "### Promotion Gates",
        _bullet_list(observation["promotion_gates"]),
        "",
        "## Audit Record",
        f"- Created at: {audit_record['created_at']}",
        f"- Source signal: `{audit_record['source_signal']}`",
        f"- Runbook version: `{audit_record['runbook_version']}`",
        f"- Eval report: `{audit_record['eval_report']}`",
        "",
        "## Learning Actions",
        _bullet_list(
            [
                f"{item['category']} ({item['priority']}): {item['action']}"
                for item in learning["learning_actions"]
            ]
        ),
    ]

    if llm_enrichment.get("used") and llm_enrichment.get("content"):
        content = llm_enrichment["content"]
        lines.extend(
            [
                "",
                "## LLM Enrichment",
                f"- Provider: `{llm_enrichment['provider']}`",
                f"- Model: `{llm_enrichment['model']}`",
                f"- Approval summary: {content.get('approval_summary', '')}",
                f"- Rollout strategy: {content.get('rollout_strategy', '')}",
            ]
        )

    return "\n".join(lines).strip() + "\n"
