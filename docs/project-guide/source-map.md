# Source Map

This repo is best understood as an enterprise **AI Search Ops control plane** around an existing search platform.

For the demo:

- `Meilisearch` is the current mock AI Search Engine
- the code in this repo is the control plane around it

## Top-Level Layout

```text
app/
  ai_search/        replaceable adapter for the search platform
  diagnosis/        incident packet, RCA, and RLM entry points
  detectors/        event-to-signal detector rules
  kafka_client/     Kafka connectivity
  middleware/       request middleware
  models/           shared data models
  monitoring/       FastAPI routes and operator-facing endpoints
  observability/    telemetry and observation entry points
  operating_model/  top-level phase map for Magellan ops
  operator_ui/      operator console assembly and UI-facing services
  release_control/  controlled release, temporal, and rollout entry points
  services/         business logic and orchestration
  signal_detection/ signal ingestion and derivation entry points
  state/            approval, audit, and ledger state access
  temporal/         Temporal workflows, worker, and client code
  utils/            small helpers

docs/
  architecture/     architecture writeups and deck outputs
  project-guide/    repo organization and phased delivery guide
```

## Folder Responsibilities

### `app/ai_search`
Owns the adapter boundary between the app and the current search backend.

Put code here when it does one of these:

- connect to Meilisearch or another future AI Search Engine
- normalize search responses
- fetch index stats/settings
- manage baseline/candidate index behavior

Current key files:

- [adapter.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/adapter.py)
- [factory.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/factory.py)
- [providers/base.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/providers/base.py)
- [providers/meilisearch.py](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/providers/meilisearch.py)

### `app/detectors`
Owns low-level detector rules that examine search events and emit signals.

Put code here when it does one of these:

- detect zero-result clusters
- detect latency spikes
- detect failures
- detect drift or reformulation behavior

Current key files:

- [zero_result.py](/Users/bhsingh/Documents/Capstone_Demo3/app/detectors/zero_result.py)
- [latency_detector.py](/Users/bhsingh/Documents/Capstone_Demo3/app/detectors/latency_detector.py)
- [error_detector.py](/Users/bhsingh/Documents/Capstone_Demo3/app/detectors/error_detector.py)

### `app/models`
Owns typed shared data objects used across ingestion, workflows, and UI APIs.

Put code here when it defines:

- raw ops events
- approval payloads
- capability signal payloads
- Temporal release state models

Current key files:

- [ops_event.py](/Users/bhsingh/Documents/Capstone_Demo3/app/models/ops_event.py)
- [capability_signal.py](/Users/bhsingh/Documents/Capstone_Demo3/app/models/capability_signal.py)
- [approval.py](/Users/bhsingh/Documents/Capstone_Demo3/app/models/approval.py)

### `app/monitoring`
Owns FastAPI routes only.

Put code here when it does one of these:

- expose a REST endpoint
- translate request/response shapes
- mount operator-console endpoints

Do not put heavy business logic here.

Current key files:

- [health.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/health.py)
- [ops_events.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/ops_events.py)
- [operator_console.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/operator_console.py)
- [controlled_release.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/controlled_release.py)

### `app/operator_ui`
Owns operator-facing console assembly and UI payload shaping.

Current key files:

- [console_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/operator_ui/console_service.py)

### `app/observability`
Owns diagram-aligned telemetry entry points for metrics and release-time observation.

Current key files:

- [telemetry.py](/Users/bhsingh/Documents/Capstone_Demo3/app/observability/telemetry.py)

### `app/signal_detection`
Owns the diagram-aligned entry points for signal capture and derivation.

Current key files:

- [capture.py](/Users/bhsingh/Documents/Capstone_Demo3/app/signal_detection/capture.py)
- [engine.py](/Users/bhsingh/Documents/Capstone_Demo3/app/signal_detection/engine.py)
- [api_detectors.py](/Users/bhsingh/Documents/Capstone_Demo3/app/signal_detection/api_detectors.py)

### `app/diagnosis`
Owns diagram-aligned entry points for incident diagnosis and RLM analysis.

Current key files:

- [incident.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/incident.py)
- [rca.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/rca.py)
- [rlm.py](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/rlm.py)
- [agents/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/agents/README.md)

### `app/release_control`
Owns diagram-aligned entry points for Temporal, rollout planning, router policy, and search-change application.

Current key files:

- [plan.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/plan.py)
- [temporal_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/temporal_service.py)
- [router_policy.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/router_policy.py)
- [change_adapter.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/change_adapter.py)

### `app/state`
Owns state access for approvals, audit history, and the raw-event/signal ledgers.

Current key files:

- [approval.py](/Users/bhsingh/Documents/Capstone_Demo3/app/state/approval.py)
- [audit.py](/Users/bhsingh/Documents/Capstone_Demo3/app/state/audit.py)
- [ops_ledger.py](/Users/bhsingh/Documents/Capstone_Demo3/app/state/ops_ledger.py)

### `app/operating_model`
Owns the top-level phase map used to explain how the control plane fits together.

Current key files:

- [service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/operating_model/service.py)

### `app/services`
Owns the underlying implementation modules.

This is currently the biggest folder because it contains multiple logical subsystems:

- search serving
- event ingestion
- signal generation
- incident intelligence
- release control
- reporting

Use these logical groupings when working inside `services/`:

- **Search serving**
  - [search_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/search_service.py)
  - [candidate_index_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/candidate_index_service.py)
  - [traffic_router_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/traffic_router_service.py)

- **Ops signals and ledger**
  - [signal_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/signal_service.py)
  - [ops_ledger.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ops_ledger.py)
  - [ops_event_ingestion_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ops_event_ingestion_service.py)
  - [capability_signal_engine.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/capability_signal_engine.py)
  - [search_ops_event_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/search_ops_event_service.py)

- **Incident intelligence**
  - [incident_packet_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/incident_packet_service.py)
  - [intelligence_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/intelligence_pipeline.py)
  - [rlm_incident_orchestrator.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_incident_orchestrator.py)
  - [rlm_models.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_models.py)
  - [rlm_subtasks.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_subtasks.py)
  - [rca_engine.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rca_engine.py)
  - `LangGraph` now orchestrates the four split RLM agents through `app/diagnosis/agents/`

- **Release control**
  - [shadow_testing_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/shadow_testing_service.py)
  - [controlled_release_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/controlled_release_service.py)
  - [controlled_release_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/controlled_release_pipeline.py)
  - [approval_store.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/approval_store.py)
  - [release_audit_ledger.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/release_audit_ledger.py)
  - [temporal_release_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/temporal_release_service.py)

- **LLM enrichment**
  - [llm_client.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/llm_client.py)
  - [llm_intelligence_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/llm_intelligence_pipeline.py)
  - [llm_controlled_release_pipeline.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/llm_controlled_release_pipeline.py)

- **Reporting and console**
  - [operator_console_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/operator_console_service.py)
  - [report_renderer.py](/Users/bhsingh/Documents/Capstone_Demo3/app/services/report_renderer.py)

### `app/temporal`
Owns the durable workflow runtime.

Put code here when it defines:

- workflow state machines
- Temporal activities
- worker bootstrap
- Temporal client helpers

Current key files:

- [workflows.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/workflows.py)
- [activities.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/activities.py)
- [worker.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/worker.py)

## Quick “Where Do I Put This?” Guide

| If you are changing... | Put code in... |
|---|---|
| search provider integration | `app/ai_search/` |
| raw query or catalog event ingestion | `app/services/ops_event_ingestion_service.py` or a sibling service |
| a detector rule | `app/detectors/` or `app/services/capability_signal_engine.py` |
| an API route | `app/monitoring/` |
| RCA, RLM, runbook logic | `app/services/` incident intelligence files |
| approval or rollout orchestration | `app/services/` release files or `app/temporal/` |
| database-backed workflow history | `app/services/release_audit_ledger.py` or `app/services/approval_store.py` |
| docs or architecture explanations | `docs/architecture/` or `docs/project-guide/` |

The new diagram-aligned packages above are the preferred places to start reading the system. `app/services/` remains the implementation layer behind them.
