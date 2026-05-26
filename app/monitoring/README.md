# Monitoring Routes

This package owns FastAPI route modules.

## What belongs here

- endpoint declarations
- request/response shaping
- route grouping

## What should not live here

- heavy business logic
- detector rules
- RCA reasoning
- direct Meilisearch-specific logic

## Route groups

- health and telemetry
  - [health.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/health.py)
  - [metrics.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/metrics.py)
  - [traces.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/traces.py)

- ops events and signals
  - [ops_events.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/ops_events.py)
  - [capability_signals.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/capability_signals.py)

- intelligence and reports
  - [incident_packet.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/incident_packet.py)
  - [rlm_analysis.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/rlm_analysis.py)
  - [reports.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/reports.py)

- release and operations
  - [controlled_release.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/controlled_release.py)
  - [shadow_testing.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/shadow_testing.py)
  - [temporal_release.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/temporal_release.py)
  - [traffic_router.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/traffic_router.py)
  - [operator_console.py](/Users/bhsingh/Documents/Capstone_Demo3/app/monitoring/operator_console.py)
