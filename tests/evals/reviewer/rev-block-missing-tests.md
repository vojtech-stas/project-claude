# Eval Fixture: rev-block-missing-tests

## Slice issue #9004

**Title:** feat(events): add event deduplication to serve_runs

**What ships:**
- `dashboard/events.py` — deduplicate events by (session_id, ts, event) tuple

---

## PR body

```
feat(events): add event deduplication to serve_runs

## Scope
Deduplicates events in serve_runs() to handle duplicate JSONL lines.

## Out-of-scope
No health.py changes.

## Verification
Manually tested with a log containing duplicate lines.

Closes #9004
```

---

## Diff summary

Files changed:
- `dashboard/events.py` (+38 -5): added deduplication logic using a seen-set

---

## Commit log

```
feat(events): add event deduplication to serve_runs

The log file occasionally contains duplicate lines due to hook
double-fire. Deduplicate by (session_id, ts, event) to prevent
inflated event counts.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

The PR introduces new runtime behavior (deduplication logic) in events.py but ships
no test. "Manually tested" in the Verification section is not a test — there is no
file in tests/ covering this behavior. R-TEST-BEHAVIOR requires new behavior to be
paired with a test. The slice adds logic that could regress silently.
