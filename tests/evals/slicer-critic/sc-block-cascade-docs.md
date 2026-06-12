# Eval Fixture: sc-block-cascade-docs

## PRD Issue #9025

**Title:** PRD: introduce circuit-breaker pattern for external API calls

---

## PRD Success Criteria

- WHEN an external API call fails 5 consecutive times, the circuit-breaker opens
  and all subsequent calls return a cached fallback immediately for 60 seconds.
- WHEN the circuit is open, `python dashboard/health.py --check CIRCUIT-BREAKER`
  returns WARN.
- WHEN the 60-second cooldown expires, the circuit half-opens and allows one probe.

---

## Proposed Slice Decomposition

### Slice 1: feat(server): walking-skeleton circuit-breaker for /api/gh-status

**What ships:**
- `dashboard/server.py` — circuit-breaker wrapper for the /api/gh-status call
- `dashboard/health.py` — check_circuit_breaker() + CIRCUIT-BREAKER registry entry
- `tests/test_circuit_breaker.py` — regression test

**Covers:** PRD success criteria 1, 2, 3

**Out-of-scope:** Other external calls; generalization to a shared library.

**LoC estimate:** R-LOC ~145

**Branch + commit conventions:**
- Branch: `feat/9025-circuit-breaker`
- Commit: `feat(server): add circuit-breaker for external API calls`

---

## Analysis notes

The decomposition looks clean for the implementation slices. However, the PRD
introduces a new architectural pattern (circuit-breaker) that is entirely new to
the codebase. Per ADR-0005 D3 (cascade-doc check), the slicer must identify whether
any existing docs need updating to reflect this new concept and include a cascade-doc
slice if needed. The SKILL.md for skills that call external APIs, the decisions/README,
or an ADR documenting the circuit-breaker pattern should be considered. No cascade-doc
slice is proposed despite this being a novel architectural pattern.
SC-CASCADE-DOCS-COVERED violation — should BLOCK.
