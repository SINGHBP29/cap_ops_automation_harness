# Durable State

This package represents the durable state and ledger boxes in the architecture:

- PostgreSQL approval state
- release audit history
- in-memory ops ledger views used by the operator UI

Use it for code that:

- stores or reads approvals
- stores or reads release audit records
- exposes the current raw-event and signal ledgers

Current entry points:

- [approval.py](/Users/bhsingh/Documents/Capstone_Demo3/app/state/approval.py)
- [audit.py](/Users/bhsingh/Documents/Capstone_Demo3/app/state/audit.py)
- [ops_ledger.py](/Users/bhsingh/Documents/Capstone_Demo3/app/state/ops_ledger.py)
