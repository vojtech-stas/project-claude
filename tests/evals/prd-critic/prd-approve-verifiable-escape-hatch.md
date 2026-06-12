# Eval Fixture: prd-approve-verifiable-escape-hatch (HOLDOUT)

## PRD Issue #9017

**Title:** PRD: add dead-route detection to health checks

---

## PRD Body

### 1. Problem

The dashboard server.py registers Flask routes but occasionally a route is removed
from the frontend without removing the corresponding backend route. Dead routes
accumulate silently. A health check that detects routes with no recent callers would
surface this drift.

### 2. Success criteria

- WHEN `python dashboard/health.py --check DEAD-ROUTES` is run on a repo with
  routes that have had zero calls in the last 30 days, it returns WARN with a list
  of the dead routes.
- WHEN all registered routes have had at least one call in the last 30 days, the
  check returns PASS.
- WHEN no call log data is available (new install, empty log), the check returns
  PASS (honest no-baseline, not false alarm).

  Note on Verifiable: the "30 days of call data" criterion is not immediately
  testable on a fresh repo. The honest-no-baseline PASS path is the testable
  proxy for the first 30 days.

### 3. Non-goals

- We will not instrument every route call with a separate log entry.
- We will not alert on dead routes; dashboard WARN is sufficient.
- We will not auto-remove dead routes.

### 4. Appetite

1 slice, ~1 day.

### 5. Slice sketch

- Slice 1: check_dead_routes() + CHECK_REGISTRY entry

### 6. Rabbit-holes

- Do not attempt to parse Flask source code to enumerate routes programmatically.
  Use the existing route registry in server.py.

### 7. Production verification

qa-tester will run `python dashboard/health.py --check DEAD-ROUTES` on the live
repo and confirm PASS or WARN (not ERROR) on a fresh install.

---

## Analysis notes

HOLDOUT case. The PRD explicitly acknowledges a verifiability escape-hatch in
section 2 ("Note on Verifiable: the '30 days of call data' criterion is not
immediately testable...") and explains the honest-no-baseline proxy. This is a
principled approach — the escape hatch is documented and the honest-PASS fallback
is the testable proxy. The prd-critic should accept this as a valid EARS pattern
with an acknowledged escape hatch. Should APPROVE.
