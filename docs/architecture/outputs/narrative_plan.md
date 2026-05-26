# Narrative Plan — Search Incident Control System Architecture

## Audience

Engineering-focused review audience that still needs plain, human-readable framing.

## Objective

Explain the system as a realistic control plane around search:

- what exists today in the demo
- how it works internally
- how it evolves into an enterprise architecture
- who owns each part

## Narrative Arc

1. explain what the system is in simple language
2. show the current demo architecture
3. show how one incident flows through the system
4. show the real endpoint and service connection map
5. show the target enterprise model
6. show what changes and what stays constant
7. end with ownership and operating model

## Slide List

1. What this system is
2. Current demo architecture
3. Low-level runtime flow
4. Endpoint and connection map
5. Target enterprise architecture
6. Current-to-target evolution
7. Ownership and operating model

## Source Plan

- `README.md`
- `docs/architecture/slide-story.md`
- `docs/architecture/search-incident-control-system-architecture.md`
- current application modules in `app/`

## Visual System

- light editorial background
- dark ink text
- green for serving plane
- blue for observability
- orange for diagnosis / runbook
- purple for Temporal / release control
- simple cards, swimlanes, and numbered flow blocks

## Imagegen Plan

No generated art plates are required. The deck is diagram-first and uses native editable shapes and text throughout.

## Asset Needs

- editable architecture swimlanes
- editable component cards
- editable comparison matrix
- editable ownership cards

## Editability Plan

All visible content will be built with editable PowerPoint text boxes and shapes.  
No screenshot-only diagrams.  
No rasterized architecture labels.
