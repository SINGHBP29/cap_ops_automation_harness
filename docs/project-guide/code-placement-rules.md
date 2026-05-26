# Code Placement Rules

Use these rules when adding or refactoring code.

## 1. API route files should stay thin

Files in `app/monitoring/` should:

- parse request input
- call a service
- return a response

They should not:

- contain detector rules
- contain RCA logic
- talk to Meilisearch directly
- talk to PostgreSQL directly unless that route is explicitly a storage API

## 2. Search backend integration belongs behind the adapter

Any code that depends on Meilisearch-specific URLs or payloads should live in:

- `app/ai_search/providers/`

Any code that needs a stable application-facing interface should use:

- `app/ai_search/adapter.py`

This keeps the search backend replaceable.

## 3. Raw event ingestion must be normalized first

When a new source is added, do not scatter custom dict shapes around the app.

Instead:

1. define or reuse a model in `app/models/`
2. normalize it in `app/services/ops_event_ingestion_service.py`
3. store it in `app/services/ops_ledger.py`

## 4. Detector logic should not live in controllers

If a rule decides whether something is a signal, it belongs in:

- `app/detectors/`
- or `app/services/capability_signal_engine.py`

Do not bury those rules in route handlers or UI services.

## 5. Agentic logic should be isolated

RLM or LLM-driven reasoning belongs in the incident-intelligence layer:

- `app/services/rlm_incident_orchestrator.py`
- `app/services/rlm_subtasks.py`
- `app/services/llm_*`

Keep approval, routing, and rollback out of the agentic layer.

## 6. Release control must remain deterministic

Approval, rollout, and rollback logic belongs in:

- `app/services/controlled_release_*`
- `app/services/approval_store.py`
- `app/services/traffic_router_service.py`
- `app/services/temporal_release_service.py`
- `app/temporal/`

Do not let free-form LLM output directly decide release phases.

## 7. Shared shapes should be typed once

If the same data appears in multiple subsystems, add a shared model.

Good candidates:

- ops events
- capability signal payloads
- approval records
- workflow status payloads

## 8. When in doubt, organize by responsibility

Use this order of decision:

1. Is it a route? Put it in `monitoring/`
2. Is it search-backend integration? Put it in `ai_search/`
3. Is it a typed payload? Put it in `models/`
4. Is it a detector or rule? Put it in `detectors/` or signal engine
5. Is it orchestration/business logic? Put it in `services/`
6. Is it durable workflow code? Put it in `temporal/`

## 9. Safe refactor strategy

When reorganizing this repo later:

- first add new modules
- then switch imports to the new modules
- then delete old logic only after runtime checks pass

That matches how the Phase 1 AI-search adapter refactor was done.
