# Current RAIR-RAG Documentation Index

This repository keeps historical planning notes, stage tutorials, and legacy
HSC-RAG-DE material for implementation traceability. They are not the current
paper or reproduction authority unless explicitly listed below.

## Canonical Current Documents

- `docs/RAIR_RAG_routing_reproduction.md`
- `docs/RAIR_RAG_downstream_reproduction.md`
- `models/README.md`
- `models/llm/README.md`

## Current Scope

- RAIR-RAG is the current paper line.
- `bert-multilabel` refers to the real `bert-base-chinese` MultiLabel routing
  baseline documented in `docs/RAIR_RAG_routing_reproduction.md`.
- `qwen-plus` is a strong reference generator for downstream generation
  evaluation, not the edge-local deployed model.
- DE is a routing policy calibration/search tool, not the current main
  contribution by itself.

## Historical Or Non-Canonical Material

Documents marked `OBSOLETE / HISTORICAL` are retained only as project history.
Do not use them for current claims, paper tables, model positioning, or
reproduction instructions.

This includes:

- old HSC-RAG-DE / HSC-DisasterBench-v2 paper plans;
- stage-by-stage implementation tutorials;
- old final_v2 fill guides;
- placeholder manuscript drafts;
- historical DE-as-primary-contribution planning notes.

Tracked HTML/PDF/Word paper deliverables are not part of the current canonical
paper source. The current working paper material lives under `paper/` and should
be interpreted together with the canonical reproduction documents above.
