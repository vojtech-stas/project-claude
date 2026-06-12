# Eval Fixture: rev-block-yagni (HOLDOUT)

## Slice issue #9007

**Title:** feat(tools): add cascade-finder wrapper script

**What ships:**
- `tools/cascade.sh` — thin shell wrapper around cascade-finder.py

---

## PR body

```
feat(tools): add cascade-finder wrapper script

## Scope
Adds tools/cascade.sh as a thin convenience wrapper for cascade-finder.py.

## Out-of-scope
No changes to cascade-finder.py itself.

## Verification
bash tools/cascade.sh --help exits 0

Closes #9007
```

---

## Diff summary

Files changed:
- `tools/cascade.sh` (+15 -0): new wrapper script
- `tools/utils.py` (+40 -0): new shared utilities module (NOT in What ships)

---

## Commit log

```
feat(tools): add cascade-finder wrapper script

Added a convenience wrapper. Also added tools/utils.py with common
path-resolution helpers that might be useful later.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

HOLDOUT case. The PR ships `tools/utils.py` which is NOT in the slice's "What ships"
list. The commit message admits it: "Also added tools/utils.py with common
path-resolution helpers that might be useful later." This is a textbook YAGNI
violation — adding speculative utility code "that might be useful later". The reviewer
should BLOCK for scope drift (R-SCOPE / YAGNI rule #1).
