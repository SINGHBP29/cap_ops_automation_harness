# Operating Model Classes

This document maps the AI Search operating model to the actual class structure in code.

## 00 — Operating Model

Business idea:

- Grid Dynamics AI Search provides discovery capabilities
- Magellan automates the operational work around those capabilities

Main class:

- [AISearchOpsHarnessService](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ai_search_ops_harness_service.py:17)

Why it exists:

- provides one top-level class that explains the lifecycle
- makes the phases visible in one place
- ties signal capture, diagnosis, runbook, and release together

API:

- `GET /operating-model`

## EV — Every anomaly becomes an ops task

Business idea:

- zero-result clusters
- stale catalog attributes
- weak autocomplete
- rule conflicts

Main class:

- [OpsSignalCaptureService](/Users/bhsingh/Documents/Capstone_Demo3/app/services/ops_event_ingestion_service.py:15)

Supporting classes:

- [CapabilitySignalEngine](/Users/bhsingh/Documents/Capstone_Demo3/app/services/capability_signal_engine.py:134)
- [RawOpsEvent](/Users/bhsingh/Documents/Capstone_Demo3/app/models/ops_event.py:8)
- [CapabilitySignalEvent](/Users/bhsingh/Documents/Capstone_Demo3/app/models/capability_signal.py:17)

Responsibility:

- normalize raw events
- infer capability
- store event in ops ledger
- derive structured signals

Examples of sources already wired:

- query logs
- zero-result sessions
- catalog deltas
- inventory shifts
- voice/image failures
- reviews and UGC
- personalization events
- MXP rule diffs and overrides

## QA — Runbooks generate candidate fixes

Business idea:

- propose catalog enrichment
- synonym packs
- index refreshes
- personalization guardrails
- MXP rule changes

Main classes:

- [IncidentPacketService](/Users/bhsingh/Documents/Capstone_Demo3/app/services/incident_packet_service.py:12)
- [IntelligencePipeline](/Users/bhsingh/Documents/Capstone_Demo3/app/services/intelligence_pipeline.py:111)

Supporting diagnosis classes:

- [RCAEngine](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rca_engine.py:14)
- [RLMIncidentOrchestrator](/Users/bhsingh/Documents/Capstone_Demo3/app/services/rlm_incident_orchestrator.py:1)

Responsibility:

- collect current signals
- collect diagnostics
- identify capability and root cause
- build incident packet
- generate runbook and eval plan

## AB — Every release is measured and reversible

Business idea:

- Temporal drives evals
- shadow tests
- approvals
- canaries
- rollback conditions
- audit history

Main classes:

- [ControlledReleaseService](/Users/bhsingh/Documents/Capstone_Demo3/app/services/controlled_release_service.py:19)
- [ControlledReleasePipeline](/Users/bhsingh/Documents/Capstone_Demo3/app/services/controlled_release_pipeline.py:120)

Supporting rollout classes:

- [Temporal release services](/Users/bhsingh/Documents/Capstone_Demo3/app/services/temporal_release_service.py:1)
- [Traffic router service](/Users/bhsingh/Documents/Capstone_Demo3/app/services/traffic_router_service.py:1)
- [Shadow testing service](/Users/bhsingh/Documents/Capstone_Demo3/app/services/shadow_testing_service.py:1)

Responsibility:

- build telemetry snapshot
- build approval decision context
- build staged release plan
- build audit and learning payloads
- keep release reversible

## Recommended Class Ownership

| Section | Main class | What it should own |
|---|---|---|
| Operating model | `AISearchOpsHarnessService` | overall lifecycle and phase map |
| Signal capture | `OpsSignalCaptureService` | raw event normalization and signal derivation |
| Capability diagnosis | `IncidentPacketService` | signal selection, diagnostics, incident packet assembly |
| Runbook proposal | `IntelligencePipeline` | candidate fix, eval set, owner, rollback plan |
| Safe release | `ControlledReleaseService` | telemetry, approval/release packet assembly |

## Class Rule

Use classes for:

- orchestration
- lifecycle ownership
- configuration-heavy services
- phase-level business responsibilities

Keep simple helpers as plain functions when they are small and local.
