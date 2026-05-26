# Services Package

This package contains most of the underlying application logic.

For day-to-day navigation, start with the diagram-aligned entry-point packages:

- `app/ai_search/`
- `app/observability/`
- `app/signal_detection/`
- `app/diagnosis/`
- `app/release_control/`
- `app/operator_ui/`
- `app/state/`
- `app/operating_model/`

Then use `app/services/` when you need the lower-level implementation details.

It is easiest to treat `services/` as five sub-areas.

## 1. Search Serving

- [search_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/search_service.py)
- [candidate_index_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/candidate_index_service.py)
- [traffic_router_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/traffic_router_service.py)

## 2. Ops Signals

- [search_ops_event_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/search_ops_event_service.py)
- [ops_event_ingestion_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ops_event_ingestion_service.py)
- [ops_ledger.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ops_ledger.py)
- [signal_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/signal_service.py)
- [capability_signal_engine.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/capability_signal_engine.py)

## 3. Incident Intelligence

- [ai_search_ops_harness_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ai_search_ops_harness_service.py)
- [incident_packet_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/incident_packet_service.py)
- [intelligence_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/intelligence_pipeline.py)
- [rca_engine.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rca_engine.py)
- [rlm_incident_orchestrator.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_incident_orchestrator.py)
- [rlm_models.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_models.py)
- [rlm_subtasks.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_subtasks.py)

The four specialized RLM agents now live under:

- [app/diagnosis/agents/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/README.md)

## 4. Release Control

- [shadow_testing_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/shadow_testing_service.py)
- [controlled_release_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/controlled_release_service.py)
- [controlled_release_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/controlled_release_pipeline.py)
- [approval_store.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/approval_store.py)
- [release_audit_ledger.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/release_audit_ledger.py)
- [temporal_release_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/temporal_release_service.py)

## 5. Presentation And Enrichment

- [operator_console_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/operator_console_service.py)
- [report_renderer.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/report_renderer.py)
- [llm_client.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/llm_client.py)
- [llm_intelligence_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/llm_intelligence_pipeline.py)
- [llm_controlled_release_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/llm_controlled_release_pipeline.py)

## Rule

If a file starts doing two unrelated jobs, split it before adding more features.

The long-term cleanup target is:

```text
app/services/
  search/
  signals/
  incident_intelligence/
  release_control/
  reporting/
```
