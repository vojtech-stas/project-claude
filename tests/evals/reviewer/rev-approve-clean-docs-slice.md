# Eval Fixture: rev-approve-clean-docs-slice

## Slice issue #9006

**Title:** docs(adr): add ADR-0100 eval runner cadence decision

**What ships:**
- New ADR file under decisions/ (fictional ADR for eval fixture, not a real path)

---

## PR body

```
docs(adr): add ADR-0100 eval runner cadence decision

## Scope
Adds ADR-0100 formalizing the on-demand-only cadence for eval runner
(not wired into CI). Single new file under decisions/.

## Out-of-scope
No code changes. No changes to health.py, server.py, or tests/.

## Verification
grep count=1 for "ADR-0100" in the new ADR file

Closes #9006
```

---

## Diff summary

Files changed:
- New ADR file under decisions/ (+42 -0): new decision record (fictional for eval)

---

## Commit log

```
docs(adr): add ADR-0100 eval runner cadence decision

Formalizes that the eval runner is on-demand only and not wired into
CI, preserving fast CI cycles.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

Clean docs-only slice. Branch name follows feat/9006-... convention. PR body has all
three required sections. Commit subject is well under 72 chars, lowercase after colon,
has Co-Authored-By trailer. No behavior change. Closes #9006 present in body. Single
file matches What ships. Should APPROVE.
