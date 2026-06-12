# Eval Fixture: sc-block-dep-cycle

## PRD Issue #9021

**Title:** PRD: add session-level metrics to dashboard API

---

## PRD Success Criteria

- WHEN /api/sessions is called, it returns per-session aggregate metrics.
- WHEN /api/metrics is called, it returns summary statistics derived from session metrics.

---

## Proposed Slice Decomposition

### Slice 1: feat(server): add /api/sessions endpoint

**What ships:**
- `dashboard/server.py` — /api/sessions route
- `dashboard/metrics.py` — session metrics computation

**Depends on:** Slice 2 (needs the metrics aggregation from /api/metrics to compute session data)

**Covers:** Success criterion 1

**LoC estimate:** R-LOC ~90

---

### Slice 2: feat(server): add /api/metrics endpoint

**What ships:**
- `dashboard/server.py` — /api/metrics route
- `dashboard/aggregator.py` — summary statistics

**Depends on:** Slice 1 (needs per-session data from /api/sessions to produce summaries)

**Covers:** Success criterion 2

**LoC estimate:** R-LOC ~80

---

## Analysis notes

Slice 1 depends on Slice 2, AND Slice 2 depends on Slice 1. This is a circular
dependency cycle: Slice 1 → Slice 2 → Slice 1. No valid topological ordering exists.
SC-DEP-ORDERING requires that the dependency graph be a DAG (directed acyclic graph).
This is a textbook cycle — should BLOCK for circular dependency.
