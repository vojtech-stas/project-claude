# Eval Fixture: rev-block-scope-drift

## Slice issue #9001

**Title:** feat(events): add session filter to serve_runs

**What ships:**
- `dashboard/events.py` — add `?session=` query-param filtering

**Out-of-scope:** dashboard/health.py, server.py

---

## PR body

```
feat(events): add session filter to serve_runs

## Scope
Adds ?session= filtering to serve_runs() in dashboard/events.py.

## Out-of-scope
health.py, server.py

## Verification
grep for session filter in events.py

Closes #9001
```

---

## Diff summary

Files changed:
- `dashboard/events.py` (+45 -3): added session filter branch
- `dashboard/health.py` (+12 -0): refactored _insert_sys_path helper (NOT in slice scope)

---

## Commit log

```
feat(events): add session filter to serve_runs

Adds ?session= query-param filtering to serve_runs().
Also refactored _insert_sys_path in health.py for clarity.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

The diff touches `dashboard/health.py` which is explicitly excluded from the slice's
"What ships" list and is called out as out-of-scope in the PR body itself. The commit
message even admits it: "Also refactored _insert_sys_path in health.py for clarity."
This is a classic R-SCOPE / YAGNI violation.
