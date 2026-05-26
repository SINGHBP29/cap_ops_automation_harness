# Run And Phase Guide

This guide explains two things in one place:

1. how to run the project locally
2. how the codebase is organized by project phase

Use this file when you are:

- starting the project for the first time
- onboarding a teammate
- trying to understand which code belongs to which phase
- deciding where new work should be added

## What This Project Is

This repo is an **AI Search Ops control plane** around an existing search platform.

For the current demo:

- `Meilisearch` is the mock AI Search Engine
- this repo provides:
  - signal capture
  - signal detection
  - diagnosis and RCA
  - runbook generation
  - controlled release
  - operator UI
  - feedback and learning

## Local Run Options

There are two normal ways to run the project:

1. `Recommended`: run everything in Docker
2. `Advanced`: run infra in Docker and the app locally

## Option 1: Run Everything In Docker

From the repo root:

```bash
cd /Users/bhsingh/Documents/Capstone_Demo3
docker compose up -d --build
./check_stack.sh
```

### Main URLs

- App: `http://localhost:8000`
- Operator Console: `http://localhost:8000/operator-console`
- Temporal UI: `http://localhost:8088`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`
- Jaeger: `http://localhost:16686`
- Meilisearch: `http://localhost:7701`

### Quick Smoke Checks

```bash
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/search?query=python"
curl -s http://localhost:8000/signals
curl -s http://localhost:8000/ops-ledger
curl -s "http://localhost:8000/operator-console-data?use_llm=false&query=python"
```

### Generate Demo Data

```bash
curl -s -X POST http://localhost:8000/mock-signals/generate/catalog_delta_gap
curl -s -X POST http://localhost:8000/mock-signals/generate/autocomplete_failure
curl -s -X POST http://localhost:8000/mock-signals/generate/semantic_index_stale
curl -s http://localhost:8000/signals
```

### Stop The Stack

```bash
docker compose down
```

### Full Reset

```bash
docker compose down -v
docker compose up -d --build
```

## Option 2: Run Infra In Docker And App Locally

Start the infrastructure:

```bash
cd /Users/bhsingh/Documents/Capstone_Demo3
docker compose up -d zookeeper kafka meilisearch jaeger postgres temporal-postgresql temporal temporal-ui prometheus grafana
```

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Export environment variables:

```bash
export AI_SEARCH_PROVIDER=meilisearch
export AI_SEARCH_BASE_URL=http://localhost:7701
export AI_SEARCH_BASELINE_INDEX=books
export AI_SEARCH_CANDIDATE_INDEX=books_shadow
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export DATABASE_URL=postgresql://ops:ops@localhost:5435/magellan
export PROMETHEUS_URL=http://localhost:9090
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=signal-engine
export LLM_PROVIDER=none
export TEMPORAL_ENABLED=true
export TEMPORAL_ADDRESS=localhost:7233
export TEMPORAL_NAMESPACE=default
export TEMPORAL_TASK_QUEUE=controlled-release-task-queue
export TEMPORAL_UI_URL=http://localhost:8088
```

Run the app:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Run the Temporal worker in another terminal:

```bash
cd /Users/bhsingh/Documents/Capstone_Demo3
source .venv/bin/activate
export AI_SEARCH_PROVIDER=meilisearch
export AI_SEARCH_BASE_URL=http://localhost:7701
export AI_SEARCH_BASELINE_INDEX=books
export AI_SEARCH_CANDIDATE_INDEX=books_shadow
export DATABASE_URL=postgresql://ops:ops@localhost:5435/magellan
export PROMETHEUS_URL=http://localhost:9090
export TEMPORAL_ENABLED=true
export TEMPORAL_ADDRESS=localhost:7233
export TEMPORAL_NAMESPACE=default
export TEMPORAL_TASK_QUEUE=controlled-release-task-queue
python -m app.temporal.worker
```

## Runtime Entry Point

The runtime starts at:

- `app/main.py`

The most important request path is:

1. `GET /search`
2. traffic router chooses baseline or candidate index
3. AI Search Adapter calls the current provider
4. raw query-log event is recorded
5. live detectors run
6. raw events and signals land in the ops ledger
7. later phases consume those signals

## Phase Overview

The project is easiest to understand in 5 phases.

### Phase 1: AI Search Adapter And Ops Signal Foundation

Goal:

- connect the app to a replaceable search backend
- capture raw operational events
- normalize them into one ops ledger

Main code:

- `app/ai_search/`
- `app/models/ops_event.py`
- `app/services/search_service.py`
- `app/services/search_ops_event_service.py`
- `app/services/ops_event_ingestion_service.py`
- `app/services/ops_ledger.py`
- `app/monitoring/ops_events.py`

What this phase produces:

- AI Search Adapter
- raw query logs
- raw catalog and MXP events
- one normalized raw ops ledger

Examples:

- `query_log`
- `catalog_delta`
- `inventory_shift`
- `voice_search_failure`
- `ugc_signal`
- `mxp_override`

### Phase 2: Observability And Signal Detection

Goal:

- turn raw events and live traffic into operational signals

Main code:

- `app/detectors/`
- `app/services/signal_service.py`
- `app/services/signal_envelope_service.py`
- `app/services/capability_signal_engine.py`
- `app/kafka_client/`
- `app/monitoring/metrics.py`
- `app/monitoring/signals.py`
- `app/monitoring/capability_signals.py`

What this phase produces:

- zero-result signals
- latency signals
- API failure signals
- catalog signals
- autocomplete signals
- semantic index signals
- personalization signals
- merchandising signals

Important note:

- `app/detectors/drift_detector.py` exists but is currently empty
- `app/detectors/reformulation_detector.py` has code, but it is not wired into the active live detector list

### Phase 3: Incident Intelligence And RCA

Goal:

- explain what broke
- identify the affected capability
- build an evidence-backed runbook

Main code:

- `app/services/incident_packet_service.py`
- `app/services/intelligence_pipeline.py`
- `app/services/rca_engine.py`
- `app/services/rlm_incident_orchestrator.py`
- `app/services/rlm_models.py`
- `app/services/rlm_subtasks.py`
- `app/diagnosis/`
- `app/monitoring/incident_packet.py`
- `app/monitoring/rlm_analysis.py`

What this phase produces:

- incident packet
- diagnosis summary
- capability mapping
- owner path
- runbook draft
- RLM agent analysis

### Phase 4: Approval, Release, And Rollback

Goal:

- safely test and release changes

Main code:

- `app/services/shadow_testing_service.py`
- `app/services/controlled_release_service.py`
- `app/services/controlled_release_pipeline.py`
- `app/services/approval_store.py`
- `app/services/release_audit_ledger.py`
- `app/services/temporal_release_service.py`
- `app/services/traffic_router_service.py`
- `app/temporal/`
- `app/release_control/`

What this phase produces:

- shadow replay
- canary traffic control
- approval state
- Temporal workflow state
- rollback path

### Phase 5: Operator Experience, Feedback, And Learning

Goal:

- give supervisors one place to observe, approve, control, and learn

Main code:

- `app/operator_ui/console_service.py`
- `app/monitoring/operator_console.py`
- `app/services/operator_console_service.py`
- `app/services/feedback_state_store.py`
- `app/services/feedback_automation_service.py`
- `app/monitoring/feedback.py`
- `app/services/report_renderer.py`
- `app/monitoring/reports.py`

What this phase produces:

- operator console
- supervisor query inspector
- approval UI
- incident-level automation controls
- feedback state APIs
- markdown reports

## Core API Groups

### Search And Serving

- `GET /search?query=...`
- `GET /traffic-router-status`
- `POST /shadow-index-sync`

### Raw Events And Signals

- `GET /ops-events`
- `GET /ops-ledger`
- `POST /ops-events/ingest`
- `GET /signals`
- `GET /capability-signals/rules`
- `POST /capability-signals/evaluate`

### Diagnosis

- `GET /incident-packet`
- `GET /rlm-incident-analysis`
- `GET /diagnostics`

### Release Control

- `GET /controlled-release-packet`
- `GET /shadow-test`
- `GET /temporal-release-status`
- `POST /temporal-release-refresh`
- `POST /temporal-release-phase`
- `POST /temporal-release-rollback`

### Operator And Feedback

- `GET /operator-console`
- `GET /operator-console-data`
- `POST /operator-approval`
- `GET /feedback-state`
- `GET /feedback-outcomes`
- `POST /feedback-incident-controls`

## Recommended Reading Order For New Developers

1. `README.md`
2. `docs/project-guide/source-map.md`
3. `docs/project-guide/phase-plan.md`
4. `docs/project-guide/run-and-phases.md`
5. `app/main.py`
6. `app/ai_search/adapter.py`
7. `app/services/traffic_router_service.py`
8. `app/services/ops_event_ingestion_service.py`
9. `app/services/signal_service.py`
10. `app/services/capability_signal_engine.py`
11. `app/services/intelligence_pipeline.py`
12. `app/services/controlled_release_pipeline.py`
13. `app/operator_ui/console_service.py`

## Best Rule For Adding New Features

If you add a new capability such as:

- personalization
- MXP
- voice search
- image search

then build it in this order:

1. add raw events in Phase 1
2. add detector rules in Phase 2
3. add diagnosis reasoning in Phase 3
4. add release guardrails in Phase 4
5. add operator visibility in Phase 5
