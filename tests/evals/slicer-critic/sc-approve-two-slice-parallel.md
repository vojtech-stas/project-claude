# Eval Fixture: sc-approve-two-slice-parallel (HOLDOUT)

## PRD Issue #9028

**Title:** PRD: add UNTRACKED-SIZE and LOG-ROTATION health checks

---

## PRD Success Criteria

- WHEN `python dashboard/health.py --check UNTRACKED-SIZE` is run, it returns
  WARN if untracked files under tracked directories exceed 50.
- WHEN `python dashboard/health.py --check LOG-ROTATION` is run, it returns
  WARN if the workflow-events.jsonl log exceeds 5 MB.
- Both checks are registered in CHECK_REGISTRY.

---

## Proposed Slice Decomposition

### Slice 1: feat(dashboard): add UNTRACKED-SIZE health check

**What ships:**
- `dashboard/health.py` — check_untracked_size() + UNTRACKED-SIZE registry entry

**Covers:** PRD success criterion 1

**Out-of-scope:** LOG-ROTATION check; no server.py or frontend changes.

**LoC estimate:** R-LOC ~50

**Depends on:** none (independent of Slice 2)

**Branch + commit conventions:**
- Branch: `feat/9028-untracked-size-check`
- Commit: `feat(dashboard): add UNTRACKED-SIZE health check`

---

### Slice 2: feat(dashboard): add LOG-ROTATION health check

**What ships:**
- `dashboard/health.py` — check_log_rotation() + LOG-ROTATION registry entry

**Covers:** PRD success criterion 2

**Out-of-scope:** UNTRACKED-SIZE check; no server.py or frontend changes.

**LoC estimate:** R-LOC ~45

**Depends on:** none (independent of Slice 1)

**Branch + commit conventions:**
- Branch: `feat/9028-log-rotation-check`
- Commit: `feat(dashboard): add LOG-ROTATION health check`

---

## Analysis notes

HOLDOUT case. Two independent parallel slices — neither depends on the other. Both
can land in either order. Each covers exactly one PRD criterion and has all required
slice-body fields. LoC estimates are well under the 300 cap. No dep cycle. Should
APPROVE for valid parallel decomposition.
