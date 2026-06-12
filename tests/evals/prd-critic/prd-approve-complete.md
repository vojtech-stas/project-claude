# Eval Fixture: prd-approve-complete

## PRD Issue #9016

**Title:** PRD: add QUARANTINE-SLA health check for stale quarantined tests

---

## PRD Body

### 1. Problem

Quarantined tests in tests/quarantine/ accumulate without a deadline. Without a
staleness check, tests can sit in quarantine indefinitely, silently masking real
failures. Engineers need a dashboard signal when quarantined tests have been
sitting too long.

### 2. Success criteria

- WHEN `python dashboard/health.py --check QUARANTINE-SLA` is run, it returns
  WARN if any test in tests/quarantine/ has been there longer than 14 days.
- WHEN no files are in tests/quarantine/, the check returns PASS.
- WHEN tests/quarantine/ does not exist, the check returns PASS (bootstrap-safe).
- The check is registered in CHECK_REGISTRY under ID "QUARANTINE-SLA".
- The dashboard substrateMeta group displays the check result.

### 3. Non-goals

- We will not auto-remove quarantined tests automatically.
- We will not send notifications; the dashboard signal is sufficient.
- We will not track quarantine history beyond the file mtime.

### 4. Appetite

1 slice, ~half a day.

### 5. Slice sketch

- Slice 1: check_quarantine_sla() + CHECK_REGISTRY entry + substrateMeta row

### 6. Rabbit-holes

- Do not attempt to parse test contents to determine why they were quarantined.
- Use file mtime as the quarantine date — do not require a metadata sidecar.

### 7. Production verification

qa-tester will run `python dashboard/health.py --check QUARANTINE-SLA` against the
real repo and confirm it exits 0 with a PASS or WARN result (not ERROR).

---

## Analysis notes

Well-formed PRD. All sections present. Success criteria are in EARS format with
explicit triggers. Non-goals are enumerated and specific. Appetite (1 slice, half day)
is coherent with scope. Slice sketch is a single walking-skeleton slice. Rabbit-holes
are specific. Production verification names qa-tester with a concrete command.
Should APPROVE.
