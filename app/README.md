# App Package Guide

This folder contains the running application.

Use this simple mental model:

- `ai_search/` = search platform adapter
- `observability/` = telemetry entry points
- `signal_detection/` = raw-event capture and signal derivation
- `diagnosis/` = incident packet, RCA, and RLM analysis
- `release_control/` = release planning, Temporal, router policy, and shadow replay
- `operator_ui/` = operator console payload assembly
- `state/` = approvals, audit, and ledger state access
- `operating_model/` = top-level phase map for the Magellan harness
- `detectors/` = low-level signal rules
- `models/` = shared payloads
- `monitoring/` = FastAPI routes
- `services/` = lower-level implementation modules behind the layer entry points
- `temporal/` = workflow runtime

If you are new to the repo, start with:

1. [main.py](/Users/bhsingh/Documents/Capstone_Demo3/app/main.py)
2. [ai_search/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/ai_search/README.md)
3. [operator_ui/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/operator_ui/README.md)
4. [release_control/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/README.md)
5. [diagnosis/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/diagnosis/README.md)
6. [services/README.md](/Users/bhsingh/Documents/Capstone_Demo3/app/services/README.md)
