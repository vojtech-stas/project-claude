---
title: R-META — reviewer rule enforcing ADR provenance via slice or trailer
summary: The reviewer rule that NEW ADR files must show subagent provenance via a Closes #N link to a slice or prd issue OR a Co-Authored-By Claude commit trailer, enforcing main-agent meta-output discipline.
tags: [glossary, reviewer-rule, project-jargon, governance]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0004-bypass-prevention.md
  - .claude/agents/reviewer.md
  - CLAUDE.md
---

# R-META

**R-META** is rule 11 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric and originates from [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4. It requires that NEW ADR files (`decisions/NNNN-*.md`) show subagent provenance via EITHER a `Closes #N` link to a `slice`/`prd`-labeled issue in the PR body OR a `Co-Authored-By: Claude` trailer on at least one commit. Either signal alone passes; both absent BLOCKs. The rule mechanically enforces CLAUDE.md rule #10 (main-agent meta-output discipline) at the narrowest, highest-signal slice of that policy: NEW canonical decision artifacts.

**Edges**

- **related-to:** [[concepts/glossary/r-loc]]
- **related-to:** [[concepts/glossary/r-closes]]
- **part-of:** [[entities/subagents/reviewer]]

## What

The rule applies ONLY to NEW files in the regex `^decisions/[0-9]+-.*\.md$`. Edits to existing ADRs are blocked by separate immutability conventions (per `decisions/README.md`). Mechanics:

- Reviewer runs `git diff --name-status origin/main..HEAD` and filters for `A` (addition) + ADR-path-regex matches.
- Empty → R-META trivially PASSes (does not fire).
- Non-empty → check both provenance signals.

**Signal A — PR body Closes link.** The PR body contains at least one `Closes #N` line, and issue `N` is labeled `slice` or `prd`.

**Signal B — Co-Authored-By trailer.** At least one commit in the PR carries a `Co-Authored-By: Claude` (or specific model variant) trailer.

EITHER signal alone → PASS. NEITHER signal → BLOCK with the exact paths and the policy citation.

A false-positive escape hatch (`R-META-OVERRIDE`) exists for one-time bootstraps or externally-authored ADRs being absorbed: the PR body adds an explicit override line; reviewer logs the override and APPROVES (not silently — the override appears in the verdict).

R-META does NOT fire on:

- Existing ADR edits (covered by immutability).
- Additions in `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `README.md` (covered by R-LOC + R-CLOSES).
- `decisions/README.md`, `decisions/branch-protection-config.json` (the regex's `[0-9]+-` discriminator excludes them).

## Why

R-META exists because **new ADRs are the highest-signal canonical decision artifacts the project produces**, and unsupervised additions risk bypassing the pipeline that gives those decisions legitimacy. Without R-META, the main agent could hand-author an ADR and merge it; the decision would lack the prd-critic / adr-critic gate; future readers would see a decision with no audit trail to the conversation that produced it.

The narrow scope (NEW ADRs only) is intentional per ADR-0009's deferred discussion. Broadening R-META to fire on every NEW tracked file would create false positives on legitimate non-ADR additions (config files, scripts, hooks) where the provenance signal is weaker and the audit cost of a missed addition is lower. ADR-0009 D1's broader policy (every tracked file flows through the pipeline) is enforced at the *policy* layer (CLAUDE.md rule #10) and at the PR-tier mechanical layer by R-CLOSES; R-META adds an ADR-specific provenance check on TOP of that base. Defense in depth, not single-point enforcement.

The dual-signal acceptance (Closes OR Co-Authored-By) reflects two valid provenance shapes: subagent-authored content typically carries the trailer; main-agent-orchestrated content typically has the Closes link. Either signal proves "this didn't happen outside the pipeline".

## Examples from this project

- **ADR-0031 (knowledge architecture v2)** — added via PRD #242 slice 1; PR body had `Closes #243` (slice-labeled) AND commits had `Co-Authored-By: Claude` trailer. Both signals; R-META PASSed trivially.
- **ADR-0007 (vocabulary & grill-me extension)** — added with `Closes #` link to its slice; the implementer subagent's commit trailers supplied Signal B too.
- **PRD #245 (this migration)** — adds ZERO new ADRs; R-META does not fire.

## Anti-patterns

- **Hand-authoring an ADR on main in a hotfix** — bypasses every gate the pipeline provides; even with `trivial` label, an ADR addition is never trivial-tier.
- **Adding an ADR via a non-pipeline PR with no provenance signals** — R-META BLOCKs; the contributor must either restructure into the pipeline or use the R-META-OVERRIDE escape hatch with explicit justification.
- **Citing R-META as cover for skipping prd-critic/adr-critic** — R-META is the trailing mechanical check; it does NOT replace the upstream critic gates.

## Scope

(a) project jargon coined here

## Authority

[ADR-0004](../../../decisions/0004-bypass-prevention.md) D4

## References

- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D4 — policy origin of R-META; main-agent meta-output discipline.
- [ADR-0009](../../../decisions/0009-discipline-tightening.md) D1 — broader CLAUDE.md rule #10 that R-META mechanically enforces for the ADR slice.
- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 11 — operational R-META check + R-META-OVERRIDE escape hatch.
- [CLAUDE.md](../../../CLAUDE.md) rule #10 — the broader policy R-META partially mechanizes.
- [[concepts/glossary/r-loc]] — sibling reviewer rule capping runtime-artifact diff.
- [[concepts/glossary/r-closes]] — sibling reviewer rule binding PR to slice issue.
- [[entities/subagents/reviewer]] — the subagent that owns this rule.
