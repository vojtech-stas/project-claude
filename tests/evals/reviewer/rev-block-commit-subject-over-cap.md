# Eval Fixture: rev-block-commit-subject-over-cap

## Slice issue #9003

**Title:** feat(dashboard): add stale-branch detection row to hygiene integrity panel

**What ships:**
- `dashboard/health.py` — check_stale_branches()

---

## PR body

```
feat(dashboard): add stale-branch detection row to hygiene integrity panel

## Scope
Adds check_stale_branches() to health.py and STALE-BRANCHES to CHECK_REGISTRY.

## Out-of-scope
No changes to server.py or frontend.

## Verification
python dashboard/health.py --check STALE-BRANCHES exits 0

Closes #9003
```

---

## Diff summary

Files changed:
- `dashboard/health.py` (+55 -0): check_stale_branches() + registry entry

---

## Commit log

```
feat(dashboard): add stale-branch detection row to hygiene integrity panel for ADR-0068

This commit subject is exactly 80 characters long, which exceeds the 72-char hard cap.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

The commit subject line "feat(dashboard): add stale-branch detection row to hygiene
integrity panel for ADR-0068" is 80 characters, which exceeds the <=72-char hard cap
defined in rule #5 / Conventional Commits tightened. The PR body itself is fine.
The reviewer should BLOCK for the over-cap commit subject.
