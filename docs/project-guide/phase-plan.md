# Phase Plan

This project is easier to build and maintain when each capability is delivered in clear phases.

## Phase 1: AI Search Adapter And Ops Signal Foundation

Goal:

- connect the app to a replaceable search backend
- ingest raw operational events
- store them in one normalized ops ledger

Primary folders:

- `app/ai_search/`
- `app/models/`
- `app/services/ops_event_ingestion_service.py`
- `app/services/ops_ledger.py`
- `app/services/search_ops_event_service.py`
- `app/monitoring/ops_events.py`

Main outputs:

- `AI Search Adapter`
- raw ops events
- normalized ops ledger
- capability-signal rules endpoint

Examples of events:

- query logs
- catalog deltas
- zero-result sessions
- voice/image failures
- reviews and UGC signals
- inventory shifts
- MXP rule diffs and overrides

## Phase 2: Observability And Signal Detection

Goal:

- turn telemetry and events into operational signals

Primary folders:

- `app/detectors/`
- `app/monitoring/metrics.py`
- `app/monitoring/traces.py`
- `app/services/signal_service.py`
- `app/services/capability_signal_engine.py`
- `app/kafka_client/`

Main outputs:

- zero-result detector
- latency detector
- failure detector
- capability-specific signal engine
- Kafka-published signals

Signals at this phase:

- semantic search issues
- catalog issues
- autocomplete issues
- semantic index issues
- personalization issues
- merchandising issues

## Phase 3: Incident Intelligence And RCA

Goal:

- explain what broke
- identify the affected capability
- create an evidence-backed runbook

Primary folders:

- `app/services/intelligence_pipeline.py`
- `app/services/incident_packet_service.py`
- `app/services/rca_engine.py`
- `app/services/rlm_incident_orchestrator.py`
- `app/services/rlm_models.py`
- `app/services/rlm_subtasks.py`
- `app/monitoring/incident_packet.py`
- `app/monitoring/rlm_analysis.py`

Main outputs:

- incident packet
- capability diagnosis
- evidence pack
- owner path
- runbook draft

This is the first strongly agentic phase.

## Phase 4: Approval, Release, And Rollback

Goal:

- safely test and release changes

Primary folders:

- `app/services/shadow_testing_service.py`
- `app/services/controlled_release_service.py`
- `app/services/controlled_release_pipeline.py`
- `app/services/approval_store.py`
- `app/services/release_audit_ledger.py`
- `app/services/temporal_release_service.py`
- `app/services/traffic_router_service.py`
- `app/temporal/`
- `app/monitoring/controlled_release.py`
- `app/monitoring/temporal_release.py`
- `app/monitoring/traffic_router.py`

Main outputs:

- shadow replay
- canary planning
- approval storage
- durable Temporal workflow state
- rollback control

This phase must stay mostly deterministic.

## Phase 5: Operator Experience, Reports, And Learning

Goal:

- give operators one place to review, approve, and learn from incidents

Primary folders:

- `app/monitoring/operator_console.py`
- `app/services/operator_console_service.py`
- `app/monitoring/reports.py`
- `app/services/report_renderer.py`
- `docs/architecture/`

Main outputs:

- operator console
- markdown reports
- architecture docs
- feedback and learning guidance

## Phase Ownership Summary

| Phase | Focus | Main owners |
|---|---|---|
| Phase 1 | adapter + raw events | backend, search platform |
| Phase 2 | telemetry + detection | backend, SRE, observability |
| Phase 3 | incident intelligence | AI/RLM, search relevance |
| Phase 4 | release safety | platform, SRE, approvers |
| Phase 5 | operator UX + learning | backend, product, AI ops |

## Recommended Build Order For New Work

When adding a new capability such as personalization or MXP:

1. add its raw ops events in Phase 1 style
2. add its detector rules in Phase 2 style
3. add its RCA reasoning in Phase 3 style
4. add its release safety logic in Phase 4 style
5. add its operator-console and reporting coverage in Phase 5 style
