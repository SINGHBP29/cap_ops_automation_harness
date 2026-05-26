# Release Control

This package represents the release side of the architecture:

- `Runbook + Eval Plan`
- `Temporal Workflow`
- `Release Controller`
- `Search Change Adapter`

Use it for code that:

- builds controlled-release packets
- runs shadow replay
- coordinates Temporal workflow state
- syncs or switches candidate search artifacts
- applies router policy for baseline, shadow, and canary traffic

Current entry points:

- [plan.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/plan.py)
- [shadow.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/shadow.py)
- [temporal_service.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/temporal_service.py)
- [router_policy.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/router_policy.py)
- [change_adapter.py](/Users/bhsingh/Documents/Capstone_Demo3/app/release_control/change_adapter.py)
