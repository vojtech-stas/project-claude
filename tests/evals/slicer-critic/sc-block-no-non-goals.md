# Eval Fixture: sc-block-no-non-goals

## PRD Issue #9023

**Title:** PRD: add log rotation health check

---

## PRD Success Criteria

- WHEN `python dashboard/health.py --check LOG-ROTATION` is run, it returns WARN
  if the workflow-events.jsonl log exceeds 5 MB.

---

## Proposed Slice Decomposition

### Slice 1: feat(dashboard): add LOG-ROTATION health check

**What ships:**
- `dashboard/health.py` — check_log_rotation() function + CHECK_REGISTRY entry

**Covers:** PRD success criterion 1

**LoC estimate:** R-LOC ~45

**Branch + commit conventions:**
- Branch: `feat/9023-log-rotation-check`
- Commit: `feat(dashboard): add LOG-ROTATION health check`

**Acceptance criteria:**
- `python dashboard/health.py --check LOG-ROTATION` exits 0 (PASS or WARN)
- CHECK_REGISTRY contains "LOG-ROTATION" key

---

## Analysis notes

The slice body has no "Out-of-scope" section. SC-NO-NON-GOALS requires every slice
body to include explicit Out-of-scope / non-goals to prevent scope drift during
implementation. Without this section, the implementer has no guidance on what NOT
to touch. For example: should the implementer also add rotation to server.py? Should
they update the log writer? Without Out-of-scope, this is ambiguous.
Should BLOCK for missing Out-of-scope section in the slice body.
