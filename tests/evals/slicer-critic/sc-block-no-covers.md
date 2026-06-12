# Eval Fixture: sc-block-no-covers

## PRD Issue #9022

**Title:** PRD: add health check for CI green-main status

---

## PRD Success Criteria

- WHEN `python dashboard/health.py --check GREEN-MAIN` is run, it returns PASS if
  the last CI run on main was green, WARN if CI data is unavailable.
- The check is registered in CHECK_REGISTRY.

---

## Proposed Slice Decomposition

### Slice 1: feat(dashboard): add GREEN-MAIN health check

**What ships:**
- `dashboard/health.py` — check_green_main() function + CHECK_REGISTRY entry

**LoC estimate:** R-LOC ~60

**Branch + commit conventions:**
- Branch: `feat/9022-green-main-check`
- Commit: `feat(dashboard): add GREEN-MAIN health check`

---

## Analysis notes

The slice body has no "Covers:" lines tracing it back to specific PRD success
criteria. SC-COVERAGE requires every slice body to include explicit "Covers: <success
criteria N>" lines so a reviewer can confirm the decomposition is complete and every
success criterion is covered. This slice covers both PRD criteria but does not say so.
Without Covers: lines, there is no machine-verifiable completeness guarantee.
Should BLOCK for missing Covers: coverage lines.
