---
title: R-META — reviewer hard-block on new ADR additions lacking subagent provenance
summary: The reviewer rule that NEW ADR files must show subagent provenance via either a `Closes #N` link to a slice/prd issue OR a `Co-Authored-By: Claude` commit trailer; enforces main-agent meta-output discipline.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 11
  - decisions/0004-bypass-prevention.md D4
  - decisions/0009-discipline-tightening.md D1
---

# R-META

**R-META** is rule 11 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric and originates from [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4 (as superseded forward by [ADR-0009](../../../decisions/0009-discipline-tightening.md) D1). It requires that NEW ADR files (`decisions/NNNN-*.md`) show subagent provenance via EITHER a `Closes #N` link to a `slice`/`prd`-labeled issue OR a `Co-Authored-By: Claude` commit trailer. The glossary stub at [[concepts/glossary/r-meta]] is the short vocabulary entry; this note is the full rule definition with the R-META-OVERRIDE escape hatch.

## What

The rule applies ONLY to NEW files matching `^decisions/[0-9]+-.*\.md$`. Edits to existing ADRs are blocked by separate immutability conventions (per `decisions/README.md`). Mechanics:

- Reviewer runs `git diff --name-status origin/main..HEAD` and filters for `A` (addition) + ADR-path-regex matches.
- Empty → R-META trivially PASSes (does not fire).
- Non-empty → check both provenance signals.

**Signal A — PR body Closes link.** The PR body contains at least one `Closes #N` line, and issue `N` is labeled `slice` or `prd`.

**Signal B — Co-Authored-By trailer.** At least one commit in the PR carries a `Co-Authored-By: Claude` (or specific model variant) trailer.

EITHER signal alone → PASS. NEITHER signal → BLOCK with the exact paths and policy citation.

R-META does NOT fire on:

- Existing ADR edits (covered by immutability).
- Additions in `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `README.md` (covered by [R-LOC](r-loc.md) + [R-CLOSES](r-closes.md)).
- `decisions/README.md`, `decisions/branch-protection-config.json` (the regex's `[0-9]+-` discriminator excludes them).

## Why

R-META exists because **new ADRs are the highest-signal canonical decision artifacts the project produces**, and unsupervised additions risk bypassing the pipeline that gives those decisions legitimacy. Without R-META, the main agent could hand-author an ADR and merge it; the decision would lack the `prd-critic` / `adr-critic` gate; future readers would see a decision with no audit trail to the conversation that produced it.

The narrow scope (NEW ADRs only) is intentional per ADR-0009's deferred discussion. Broadening R-META to fire on every NEW tracked file would create false positives on legitimate non-ADR additions (config files, scripts, hooks) where the provenance signal is weaker and the audit cost of a missed addition is lower. ADR-0009 D1's broader policy (every tracked file flows through the pipeline) is enforced at the *policy* layer (CLAUDE.md rule #10) and at the PR-tier mechanical layer by [R-CLOSES](r-closes.md); R-META adds an ADR-specific provenance check on TOP of that base. Defense in depth, not single-point enforcement.

The dual-signal acceptance (Closes OR Co-Authored-By) reflects two valid provenance shapes: subagent-authored content typically carries the trailer; main-agent-orchestrated content typically has the Closes link. Either signal proves "this didn't happen outside the pipeline".

## How to check

```bash
gh pr view <PR> --json files --jq '.files[] | select(.path | test("^decisions/[0-9]+-.*\\.md$")) | select(.additions > 0 and .deletions == 0) | .path'
```

If empty → R-META PASSes trivially. If non-empty, check Signal A:

```bash
gh pr view <PR> --json body --jq '.body' | grep -iE '(closes|fixes|resolves) #[0-9]+'
gh issue view <N> --json labels --jq '.labels[].name' | grep -E '^(slice|prd)$'
```

Check Signal B:

```bash
gh pr view <PR> --json commits --jq '.commits[].messageBody' | grep -i 'co-authored-by: claude'
```

Signal A OR Signal B → PASS. Neither → BLOCK.

## Recovery — R-META-OVERRIDE escape hatch

A contributor whose PR legitimately adds a new ADR but trips R-META (one-time bootstrap, externally-authored ADR being absorbed, hand-fix where provenance was inadvertently lost) MAY add a single line to the PR body:

```
R-META-OVERRIDE: <one-line rationale>
```

When present with a non-empty rationale:

- R-META is recorded as `[OVERRIDE]` (not `[PASS]`, not `[FAIL]`) in the rule checklist.
- The override does NOT change the verdict for any OTHER rule.
- The verdict comment MUST include a clearly-labeled `### R-META override notice` section quoting the override rationale verbatim and naming the new ADR file(s) it covers.

The override is a soft-pass, not a silent bypass: it costs the contributor one visible line in the PR body and one visible section in the reviewer comment.

## Examples

- **ADR-0031 (knowledge architecture v2)** — added via PRD #242 slice 1; PR body had `Closes #243` AND commits had `Co-Authored-By: Claude` trailer. Both signals; R-META PASSed.
- **PRD #245** — adds ZERO new ADRs; R-META does not fire.
- **A hypothetical hand-authored ADR on `main`** — even with `trivial` label, the addition is never trivial-tier; either flows through pipeline OR uses R-META-OVERRIDE with explicit justification.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **defines:** [[concepts/glossary/r-meta]]
- **related_to:** [[concepts/rules/r-loc]]
- **related_to:** [[concepts/rules/r-closes]]
- **related_to:** [[concepts/rules/r-adr-conflict]]
- **part_of:** [[topics/reviewer-philosophy]]
