# Temporal Package

This package owns durable workflow orchestration.

## Files

- [client.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/client.py)
  - Temporal client helpers
- [workflows.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/workflows.py)
  - workflow state machines
- [activities.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/activities.py)
  - workflow activities
- [worker.py](/Users/bhsingh/Documents/Capstone_Demo3/app/temporal/worker.py)
  - worker bootstrap

## Rule

Keep business-policy decisions in services and keep durable orchestration in Temporal.

Good examples:

- phase transitions
- waiting for approval
- canary progression
- rollback state
