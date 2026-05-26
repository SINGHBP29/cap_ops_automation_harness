# Signal Engine

This project now includes a standard local observability stack:

- FastAPI app on `http://localhost:8000`
- Kafka on `localhost:9092`
- Meilisearch on `http://localhost:7701`
- Prometheus on `http://localhost:9090`
- Grafana on `http://localhost:3001`
- Jaeger on `http://localhost:16686`

## What This Repo Does

This repo is an **AI Search Ops control plane**.

For the current demo:

- `Meilisearch` is the mock AI Search Engine
- this app captures raw ops events
- detects search and platform signals
- builds incident diagnosis and runbooks
- controls shadow, canary, approval, and rollback flow
- gives operators one UI for supervision and release decisions

## Start Everything

```bash
docker compose up -d --build
```

## Smoke Check

```bash
./check_stack.sh
```

## Grafana

- URL: `http://localhost:3001`
- Dashboard: `http://localhost:3001/d/signal-engine-overview/signal-engine-overview`
- Username: `admin`
- Password: `admin`

Grafana is provisioned with:

- A Prometheus datasource
- A Jaeger datasource
- A `Signal Engine Overview` dashboard

## Notes

- Prometheus is a query UI, so its landing page is expected to look empty until you run a query such as `sum(rate(signal_engine_http_requests_total[5m]))`.
- Jaeger is a trace search UI, so choose service `signal-engine` and a recent lookback such as `1h` to see traces.

## Architecture Package

Architecture deliverables for the current demo and target enterprise model live in:

- `docs/architecture/search-incident-control-system-architecture.md`
- `docs/architecture/enterprise-low-level-architecture.md`
- `docs/architecture/enterprise-control-plane-diagram.md`
- `docs/architecture/enterprise-executive-architecture.md`
- `docs/architecture/slide-story.md`

## Project Guide

For code organization, folder ownership, and the phase-by-phase build plan, use:

- `docs/project-guide/README.md`
- `docs/project-guide/run-and-phases.md`
- `docs/project-guide/source-map.md`
- `docs/project-guide/phase-plan.md`
- `docs/project-guide/current-vs-missing-next.md`
- `docs/project-guide/code-placement-rules.md`

## Best Starting Point

If you want one file that explains both:

- how to run the project locally
- how the code is split by phases

start here:

- `docs/project-guide/run-and-phases.md`

Diagram-aligned code entry points now live in:

- `app/ai_search/`
- `app/observability/`
- `app/signal_detection/`
- `app/diagnosis/`
- `app/release_control/`
- `app/operator_ui/`
- `app/state/`
- `app/operating_model/`
