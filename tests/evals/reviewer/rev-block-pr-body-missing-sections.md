# Eval Fixture: rev-block-pr-body-missing-sections

## Slice issue #9005

**Title:** feat(server): add /api/version endpoint

**What ships:**
- `dashboard/server.py` — /api/version route returning repo SHA

---

## PR body

```
feat(server): add /api/version endpoint

Added /api/version endpoint that returns the current git SHA.
This is useful for debugging deployments.

Closes #9005
```

---

## Diff summary

Files changed:
- `dashboard/server.py` (+22 -0): new /api/version route

---

## Commit log

```
feat(server): add /api/version endpoint

Returns current git SHA for deployment debugging.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

The PR body is missing the required sections: there is no `## Scope`, no
`## Out-of-scope`, and no `## Verification`. The PR body has only a one-sentence
description and `Closes #9005`. The reviewer requires all three structural sections
in the PR body. This should BLOCK for missing PR body structure.
