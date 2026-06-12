# Eval Fixture: rev-block-missing-closes

## Slice issue #9002

**Title:** docs(adr): add ADR-0099 decision record for event schema

**What ships:**
- `decisions/0099-fictional-adr.md` — new ADR file

---

## PR body

```
docs(adr): add ADR-0099 decision record

## Scope
Adds ADR-0099 formalizing the v3 event schema.

## Out-of-scope
No code changes.

## Verification
File exists at decisions/0099-fictional-adr.md
```

---

## Diff summary

Files changed:
- `decisions/0099-fictional-adr.md` (+85 -0): new ADR

---

## Commit log

```
docs(adr): add ADR-0099 decision record for event schema v3

Formalizes the v3 event schema that shipped in #820.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

---

## Analysis notes

The PR body is well-formed and the diff is clean. However, there is no `Closes #N`
anywhere in the PR body. The R-CLOSES rule requires every slice PR body to contain
`Closes #<n>` pointing to a valid slice-labeled issue. This PR lacks it entirely.
