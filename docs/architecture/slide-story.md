# Search Incident Control System Slide Story

## Slide 1 — What This System Is

**Title**  
Search Incident Control System

**Message**  
This project is not the search engine itself. It is the control room around the search engine.

**Speaking points**

- In the demo, Meilisearch acts as the mock search engine.
- The project watches search behavior, detects issues, explains what is wrong, and controls rollout safely.
- The same control plane can sit around a real enterprise AI Search Engine later.

## Slide 2 — Current Demo Architecture

**Title**  
Current Demo Architecture

**Message**  
Today, the system serves search through Meilisearch and wraps it with observability, diagnosis, approval, and release control.

**Visual structure**

- top row: user -> FastAPI -> traffic router -> baseline/candidate Meilisearch
- middle row: observability and signal detection
- bottom row: RCA, runbook, approval, Temporal, PostgreSQL

**Speaking points**

- Meilisearch is the mock search engine in the serving path.
- Prometheus, Grafana, and Jaeger are only evidence sources.
- The operator console is the control-plane surface for diagnosis and rollout.

## Slide 3 — Low-Level Runtime Flow

**Title**  
How One Incident Moves Through The System

**Message**  
A single bad search result can turn into a signal, then a diagnosis, then a controlled rollout decision.

**Visual structure**

- numbered flow:
  1. `/search`
  2. traffic router
  3. Meilisearch result
  4. detector pipeline
  5. ops ledger
  6. RLM analysis
  7. approval
  8. Temporal rollout

**Speaking points**

- Search response drives the detector pipeline.
- Signals and telemetry are assembled into incident intelligence.
- Temporal enforces approval and staged promotion.

## Slide 4 — Endpoint And Connection Map

**Title**  
Endpoint And Connection Map

**Message**  
This is the real low-level integration surface: public API endpoints, internal service calls, ports, and protocols.

**Visual structure**

- left column: public API endpoints on `FastAPI :8000`
- right column: internal connections to:
  - `meilisearch:7700`
  - `prometheus:9090`
  - `jaeger:4318`
  - `temporal:7233`
  - `postgres:5432`
  - `kafka:29092`
- bottom callout: Ollama is optional and used only for enrichment

**Speaking points**

- `/search` is the serving-plane entry point.
- `/operator-console-data`, `/incident-packet`, `/controlled-release-packet`, and `/temporal-release-*` are control-plane endpoints.
- Internal service calls are explicit and code-driven.

## Slide 5 — Target Enterprise Architecture

**Title**  
Target Enterprise Architecture

**Message**  
The control plane remains the same, but the mock search engine is replaced by the real enterprise AI Search Engine.

**Visual structure**

- user -> Search Experience API -> Existing AI Search Engine
- observability feeding signal detection and incident intelligence
- Search Change Adapter between Temporal-driven release control and the enterprise engine

**Speaking points**

- The search engine already exists in the target state.
- This project becomes the AI Ops layer around it.
- Observability, diagnosis, approval, and rollout remain the same core value.

## Slide 6 — Current To Target Evolution

**Title**  
What Changes From Demo To Enterprise

**Message**  
Only the serving engine changes. The control-plane logic is reusable.

**Visual structure**

- left column: current demo
- right column: target enterprise
- center row: what stays constant

**Speaking points**

- Replace Meilisearch with the enterprise AI Search Engine.
- Keep detectors, RCA, Temporal workflow, approval, audit, and rollout logic.
- This lowers migration risk because the control plane already exists.

## Slide 7 — Ownership And Operating Model

**Title**  
Who Owns What

**Message**  
Each layer has a clear operating owner so incident resolution does not become ambiguous.

**Visual structure**

- team cards by layer:
  - Search Platform Team
  - Backend/API Team
  - AI Ops / Incident Intelligence Team
  - Platform / SRE Team
  - Product / Business Approver

**Speaking points**

- Search Platform owns search quality and engine behavior.
- Backend/API owns orchestration and console APIs.
- AI Ops owns diagnosis and runbook intelligence.
- Platform/SRE owns workflow runtime, telemetry, and release safety.
- Business approver owns risky change signoff.
