# Current vs Missing Next

This document shows what is already implemented in the Magellan AI Search Ops control plane, what is only partial today, and what should be built next.

It is especially useful for:

- supervisor or stakeholder reviews
- presentation slides
- backlog planning
- deciding whether a feature is already live or still planned

## Executive View

The current system already supports:

- AI-search-backed request serving through a replaceable adapter
- raw ops-event ingestion into one normalized ledger
- signal detection for search incidents
- incident packet generation and RLM-assisted diagnosis
- operator review and approval
- Temporal-backed release workflow state
- search-traffic rollout between baseline and candidate indexes

The main gaps are:

- automatic closed-loop feedback updates
- automatic guardrail-driven promotion and rollback
- persistent, self-updating watchlists and thresholds
- policy learning from previous incident outcomes

## Status Table

| Area | Status | What is live now | What is missing next | Main code |
|---|---|---|---|---|
| AI Search Adapter | Implemented | Replaceable search adapter with current `Meilisearch` provider | Additional enterprise providers such as Grid AI Search | `app/ai_search/`, `app/services/search_service.py` |
| Raw Ops Ledger | Implemented | One normalized ledger for raw ops events and derived signals | Durable persistence for all raw events instead of in-memory only | `app/models/ops_event.py`, `app/services/ops_event_ingestion_service.py`, `app/services/ops_ledger.py` |
| Signal Detection | Implemented | API detectors and capability signal rules generate structured signals | More mature capability-specific rules for every modality and business flow | `app/services/signal_service.py`, `app/services/capability_signal_engine.py`, `app/detectors/` |
| Incident Diagnosis | Implemented | Incident packet, RCA, and LangGraph-based specialist agents are live | More evidence adapters and deeper capability-specific RCA | `app/services/incident_packet_service.py`, `app/services/intelligence_pipeline.py`, `app/services/rlm_incident_orchestrator.py`, `app/diagnosis/agents/` |
| Runbook + Eval Planning | Implemented | Candidate fixes, owner path, eval dataset, and rollback plan are produced | Richer runbook generation for more capability types and production scenarios | `app/services/intelligence_pipeline.py`, `app/services/controlled_release_pipeline.py` |
| Operator UI | Implemented | Supervisor console, query override, incident feed, Temporal link, and query inspector are live | More saved filters, historical drill-down, and richer trend views | `app/monitoring/operator_console.py`, `app/operator_ui/console_service.py` |
| Human Approval | Implemented | Approval is captured, stored, and linked to release progression | Stronger RBAC and multi-step approval policies | `app/services/approval_store.py`, `app/state/approval.py` |
| Temporal Workflow | Implemented | Workflow start, refresh, approval, release phase changes, and rollback signals are wired | Broader workflow policy coverage and more automated transitions | `app/services/temporal_release_service.py`, `app/temporal/workflows.py` |
| Shadow Testing | Implemented | Baseline vs candidate query comparison and readiness checks exist | Larger replay datasets and deeper query-segment reporting | `app/services/shadow_testing_service.py` |
| Canary Rollout | Implemented | Search traffic can move through `shadow`, `5%`, `25%`, and `100%` routing between baseline and candidate indexes | Stronger automatic promotion/rollback based on live guardrails | `app/services/traffic_router_service.py` |
| Release Guardrails | Partially implemented | Approval and candidate-readiness checks block unsafe promotion | Full automatic guardrail enforcement across latency, quality, and business metrics | `app/services/traffic_router_service.py`, `app/services/controlled_release_pipeline.py` |
| Observe Layer | Partially implemented | Observe packet, live watchlist, and promotion-gate guidance are generated | Persistent observe policies and automatic follow-up actions | `app/services/controlled_release_pipeline.py` |
| Feedback / Learning | Partially implemented | Learning actions, watchlist suggestions, and runbook-improvement suggestions are produced | Automatic threshold tuning, persistent watchlists, approval-policy updates, and closed-loop learning | `app/services/controlled_release_pipeline.py`, `app/services/release_audit_ledger.py` |
| Audit Trail | Implemented | Release evidence and approval/release history are recorded | Richer history queries and incident-to-release timeline analysis | `app/services/release_audit_ledger.py`, `app/state/audit.py` |

## Supervisor-Friendly Summary

If someone asks, "What is truly working today?", the shortest correct answer is:

- the system can ingest search ops events
- detect incidents
- diagnose likely root cause
- build a runbook
- run shadow comparisons
- collect approval
- manage a Temporal-backed rollout
- route search traffic between baseline and candidate indexes

If someone asks, "What is still not fully automated?", the shortest correct answer is:

- promotion decisions are still mostly operator-driven
- feedback does not yet write back into thresholds or watchlists automatically
- approval policy does not self-tune from past incidents
- rollout guardrails are not yet a fully autonomous closed loop

## Search Rollout Status

### Implemented now

- baseline serving through the active search engine
- candidate index readiness checks
- shadow mirroring
- `5%` canary traffic
- `25%` canary traffic
- `100%` promotion path
- fallback to baseline if candidate search errors
- Temporal phase tracking

### Missing next

- automatic promotion when guardrails stay green
- automatic rollback when live guardrails fail
- broader business-metric gating, not just readiness and approval
- historical rollout scoring across many incidents

## Feedback Engine Status

### Implemented now

- observe packet generation
- live watchlist generation
- promotion-gate recommendations
- learning-action suggestions
- audit history storage

### Missing next

- automatic threshold updates
- automatic watchlist persistence
- automatic approval-policy updates
- automatic self-tuning based on incident outcomes

## Recommended Next Build Order

If the goal is to move from the current prototype into a stronger enterprise operating loop, the next steps should be:

1. Persist raw ops events and watchlists durably instead of relying on in-memory-only paths.
2. Make rollout guardrails enforce promotion and rollback automatically.
3. Store threshold, watchlist, and approval-policy configuration outside code.
4. Feed audit outcomes back into those policies through a reviewed learning loop.
5. Expand capability-specific detection and RCA for personalization, multimodal, and merchandising controls.

## One-Line Status

Magellan already functions as an AI Search Ops control plane with real search-traffic rollout and operator workflows, but its feedback and rollout automation are still only partially closed-loop.
