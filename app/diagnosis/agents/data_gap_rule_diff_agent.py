from __future__ import annotations

from app.config import settings
from app.diagnosis.agents.base import BaseRLMSubtask
from app.diagnosis.agents.base import RLMIncidentContext
from app.diagnosis.agents.helpers import classify_data_gap
from app.diagnosis.agents.helpers import data_gap_actions
from app.diagnosis.agents.helpers import diff_index_settings
from app.diagnosis.agents.helpers import fetch_index_analysis
from app.diagnosis.agents.helpers import incident_comparison
from app.diagnosis.agents.helpers import looks_synthetic_query
from app.services.rlm_models import CodeActStep
from app.services.rlm_models import RLMSubtaskResult


class DataGapRuleDiffAgent(BaseRLMSubtask):
    key = "data_gap"
    title = "Data Gap And Rule Diff"
    focus = "Use shadow replay, catalog diffs, and index settings diffs to isolate coverage or rule problems."
    evidence_sources = ("shadow_test", "ai_search_stats", "ai_search_settings", "runbook_eval_dataset")

    async def analyze(self, context: RLMIncidentContext) -> RLMSubtaskResult:
        baseline_index = str(context.shadow_test_report.get("baseline_index", settings.AI_SEARCH_BASELINE_INDEX))
        candidate_index = str(context.shadow_test_report.get("shadow_index", settings.AI_SEARCH_CANDIDATE_INDEX))
        incident_query = context.incident_query
        comparison = incident_comparison(context.shadow_test_report.get("comparisons", []), incident_query)

        baseline_stats, candidate_stats, baseline_settings, candidate_settings = await fetch_index_analysis(
            baseline_index=baseline_index,
            candidate_index=candidate_index,
        )
        setting_diff = diff_index_settings(
            baseline_settings.get("payload") or {},
            candidate_settings.get("payload") or {},
        )

        baseline_docs = int((baseline_stats.get("payload") or {}).get("numberOfDocuments", 0) or 0)
        candidate_docs = int((candidate_stats.get("payload") or {}).get("numberOfDocuments", 0) or 0)
        baseline_results = int(comparison.get("baseline", {}).get("results_count", 0) or 0)
        candidate_results = int(comparison.get("shadow", {}).get("results_count", 0) or 0)

        gap_type, summary, confidence = classify_data_gap(
            incident_query=incident_query,
            baseline_docs=baseline_docs,
            candidate_docs=candidate_docs,
            baseline_results=baseline_results,
            candidate_results=candidate_results,
            shadow_status=str(context.shadow_test_report.get("summary", {}).get("shadow_status", "unknown")),
            setting_diff=setting_diff,
        )

        actions = data_gap_actions(gap_type=gap_type, incident_query=incident_query)
        return self._result(
            status="ok" if gap_type not in {"candidate-index-missing"} else "blocked",
            summary=summary,
            confidence=confidence,
            evidence_window=self._window(
                {
                    "incident_query": incident_query,
                    "baseline_index": baseline_index,
                    "candidate_index": candidate_index,
                    "baseline_docs": baseline_docs,
                    "candidate_docs": candidate_docs,
                    "baseline_results": baseline_results,
                    "candidate_results": candidate_results,
                    "setting_diff_keys": sorted(setting_diff.keys()),
                }
            ),
            codeact_steps=[
                CodeActStep(
                    name="shadow-eval",
                    status="ok",
                    summary="Read the incident query replay from the shadow-test comparison set.",
                    output={
                        "incident_query": incident_query,
                        "baseline_results": baseline_results,
                        "candidate_results": candidate_results,
                        "shadow_status": context.shadow_test_report.get("summary", {}).get("shadow_status"),
                    },
                ),
                CodeActStep(
                    name="catalog-diff",
                    status=baseline_stats["status"],
                    summary="Compared baseline and candidate index document counts.",
                    output={
                        "baseline": baseline_stats,
                        "candidate": candidate_stats,
                    },
                ),
                CodeActStep(
                    name="rule-diff",
                    status=baseline_settings["status"],
                    summary="Compared ranking, synonym, and searchable-attribute settings.",
                    output={
                        "setting_diff": setting_diff,
                    },
                ),
            ],
            findings={
                "gap_type": gap_type,
                "incident_query": incident_query,
                "synthetic_query": looks_synthetic_query(incident_query),
                "baseline_document_count": baseline_docs,
                "candidate_document_count": candidate_docs,
                "incident_query_outcome": comparison.get("delta", {}).get("outcome"),
                "setting_diff": setting_diff,
                "baseline_index_status": baseline_stats["status"],
                "candidate_index_status": candidate_stats["status"],
            },
            recommended_actions=actions,
        )
