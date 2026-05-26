# Signal Detection

This package represents the `Signal Detection` stage from the architecture diagram.

Use it for code that:

- ingests raw ops events into the ledger
- evaluates live API traffic after `/search`
- derives capability signals such as catalog, autocomplete, semantic, and MXP issues

Current entry points:

- [capture.py](/Users/bhsingh/Documents/Capstone_Demo3/app/signal_detection/capture.py)
- [api_detectors.py](/Users/bhsingh/Documents/Capstone_Demo3/app/signal_detection/api_detectors.py)
- [engine.py](/Users/bhsingh/Documents/Capstone_Demo3/app/signal_detection/engine.py)
