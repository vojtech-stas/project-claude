# Eval Fixture: sc-approve-single-trivial (HOLDOUT)

## PRD Issue #9027

**Title:** PRD: add REQUIRED-LABELS health check

---

## PRD Success Criteria

- WHEN `python dashboard/health.py --check REQUIRED-LABELS` is run, it returns
  WARN if any label in the bootstrap LABELS array is missing from the GitHub repo.
- WHEN all required labels exist, it returns PASS.

---

## Proposed Slice Decomposition

### Slice 1: feat(dashboard): add REQUIRED-LABELS health check

**What ships:**
- `dashboard/health.py` — check_required_labels() function + CHECK_REGISTRY entry

**Covers:** PRD success criteria 1, 2

**Out-of-scope:** No changes to server.py, frontend, or tests/ beyond
health.py itself.

**LoC estimate:** R-LOC ~55

**Depends on:** none

**Branch + commit conventions:**
- Branch: `feat/9027-required-labels-check`
- Commit: `feat(dashboard): add REQUIRED-LABELS health check`

**Acceptance criteria:**
- `python dashboard/health.py --check REQUIRED-LABELS` exits 0
- CHECK_REGISTRY["REQUIRED-LABELS"] exists

---

## Analysis notes

HOLDOUT case. Single-slice PRD: Slice 1 is the entire PRD. The walking-skeleton
IS the complete feature. The slice covers both PRD criteria, has Covers:, Out-of-scope,
LoC (under 300 cap), Depends-on, and branch/commit conventions. This is the minimal
valid single-slice case. Should APPROVE.
