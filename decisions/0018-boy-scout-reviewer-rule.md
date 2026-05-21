# ADR-0018: R-BOY-SCOUT reviewer rule — per-PR drift detection on audit-relevant files

- **Status:** Accepted
- **Date:** 2026-05-21
- **Supersedes:** none
- **Extends:** [ADR-0002](0002-autonomous-merge-policy.md) (reviewer is the sole gate; this ADR adds a new rule to the reviewer's rubric); [ADR-0011](0011-subagent-quality-framework.md) D2/D5 (mechanical rubric + advisory-only precedents reused); [ADR-0017](0017-audit-meta-consolidation.md) D2/D3 (the rubric content this rule consumes); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap honored — reviewer rule extension, not new critic); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D5).

## Context

PRD-γ (#139) shipped `/audit-meta` (--structure + --docs subcommands) per ADR-0017. ADR-0017 D7 explicitly deferred two halves of backlog #47: post-PRD audit cadence + per-PR boy-scout reviewer rule. The 2026-05-21 grill (Q1=1α for PRD-ε / #47 first half) chose to ship the **boy-scout reviewer rule now**, leaving cadence to wait for CI (#63).

The boy-scout pattern (named after the "leave the campsite cleaner than you found it" convention): when a reviewer audits a PR that touches audit-relevant files, the reviewer ALSO checks those files against the relevant audit rubric — surfacing drift mechanically at PR-review-time. Today's session had a concrete instance: PR #125 (README.md N=3 stale references after ADR-0013) was caught only by user manual inspection. R-BOY-SCOUT would have caught it mechanically when ANY PR touching `README.md` came through reviewer.

The rule is **additive** to the existing 11 hard-block reviewer rules (R-LOC, R-CLOSES, R-META, etc.). It does NOT renumber existing rules; it adds R-BOY-SCOUT as the 12th rule (or as a non-numbered rule with its own ID prefix). Implementer decides the exact placement; this ADR locks the rule name and semantics.

## Decisions

### D1: Rule name — `R-BOY-SCOUT`

Follows the established R-* convention used for hard-block reviewer rules. The rule name encodes the pattern (boy-scout = leave things cleaner). Implementer adds the rule to `.claude/agents/reviewer.md` in the appropriate section (after the existing R-* hard-block rules; specific section placement is implementer judgment).

### D2: Trigger paths (PR diff includes any file matching these patterns)

The rule fires when a PR's diff touches files matching ANY of:

| Pattern | Audit checks to apply |
|---|---|
| `.claude/agents/*.md` | /audit-subagents rubric (all 10 checks per ADR-0011 D4) applied to touched files only |
| `.claude/skills/*/SKILL.md` | /audit-meta `--structure` rubric (STRUCT-1, STRUCT-2, STRUCT-7) + selected /audit-subagents checks (frontmatter shape) |
| `decisions/*.md` | /audit-meta `--docs` rubric DOCS-1, DOCS-2, DOCS-7, DOCS-8 (cross-reference checks) |
| `CLAUDE.md` | /audit-meta `--docs` rubric DOCS-3, DOCS-4, DOCS-5, DOCS-9, DOCS-10 (Map row + cap + drift detectors) |
| `README.md` | /audit-meta `--docs` rubric DOCS-5, DOCS-6, DOCS-10 (drift detectors) |

Multiple matching paths in one PR → reviewer runs all applicable rubrics; findings consolidated in verdict.

### D3: Reviewer behavior on trigger

The reviewer is an LLM agent. On R-BOY-SCOUT trigger:

1. **Read** each touched file from the PR diff (use `gh pr diff <N>` or `gh api repos/.../pulls/<N>/files`).
2. **Apply** the relevant audit checks per D2 — execute the grep patterns / file-existence checks INLINE (reviewer's tool boundaries include Bash and Grep; the rubrics are mechanical and self-contained).
3. **Emit** findings in the verdict's `Findings` section with severity per D4 below.

**Important constraint** (per the 2026-05-21 hooks reality-check from PRD-α): reviewer does NOT shell out to /audit-subagents or /audit-meta as skills (would require session interaction). Instead, reviewer applies the rubric criteria inline using its own Bash + Grep tool access. The rubrics are intentionally simple enough (grep-based per ADR-0011 D2) that this is feasible.

### D4: Discretion heuristic — BLOCK vs REC severity

R-BOY-SCOUT findings are emitted at one of two severities, with the reviewer applying judgment:

- **BLOCK** when ALL of:
  - The audit rule has zero documented false-positive cases against current-main (verifiable via /audit-meta dogfood + recent backlog audit-calibration captures — currently DOCS-5, DOCS-6, DOCS-7 have known false-positive patterns per backlog [#142](https://github.com/vojtech-stas/project-claude/issues/142))
  - The fix is mechanical and small (one-line, hotfix-shape)
  - The drift would materially impact future readers (e.g., a stale ADR D-ID reference)
- **Recommendation** otherwise — findings surface in verdict but don't block merge; user/implementer can fix via trivial-lane post-merge

Default-conservative: when uncertain → Recommendation, not BLOCK. (Mirrors ADR-0009 D3's asymmetric default-BLOCK but inverted — for boy-scout, false-positive BLOCK costs more than false-negative REC because boy-scout is additive defense-in-depth, not the sole gate.)

### D5: Bootstrap-mode acknowledgment (per ADR-0004 D2)

R-BOY-SCOUT binds **forward from slice-1 merge**. PRs already open at merge time are NOT retroactively re-reviewed under the new rule. Once the rule lands, all new PRs are subject to R-BOY-SCOUT trigger evaluation.

Backlog [#142](https://github.com/vojtech-stas/project-claude/issues/142) (audit-meta dogfood findings — 3 false-FAIL rules + jq dep check) is the current known set of rule-calibration concerns. R-BOY-SCOUT D4 explicitly excludes the calibration-pending rules (DOCS-5, DOCS-6, DOCS-7) from BLOCK eligibility until #142 ships. They emit as Recommendation only.

The 6-critic-cap (ADR-0008 D7) is unaffected — R-BOY-SCOUT is a reviewer rule, not a new critic.

### D6: Additive — no renumbering of existing R-* rules

R-BOY-SCOUT is added as a new rule alongside the existing 11 hard-block rules (R-LOC, R-CLOSES, R-META, etc.). No existing rule is renumbered, modified, or superseded. The implementer chooses placement (probably after R-META as the "discretionary" rules section, OR as a non-numbered "soft" rule depending on reviewer.md structure — implementer judgment).

### D7: Composition with future cadence (#47 second half)

The other half of #47 (post-PRD audit cadence) is deferred until CI (#63) provides hook substrate to fire /audit-meta autonomously post-merge. When the cadence half lands:
- **R-BOY-SCOUT**: fires at PR-review-time, on touched files only
- **Cadence**: fires post-merge, scans entire codebase

These are **complementary, not redundant**. R-BOY-SCOUT catches drift introduced by the current PR; cadence catches drift from across multiple PRs that didn't individually trigger boy-scout. ADR-0018 D7 reserves the relationship — the cadence PRD (when it ships) supersedes nothing here.

## Consequences

### Positive

- **Closes 1/2 of #47**: boy-scout half lands; cadence half deferred to post-CI
- **Catches drift at PR-time mechanically**: PR #125's N=3-in-README pattern would have been caught by R-BOY-SCOUT firing on README.md touch + DOCS-5 check
- **Defense-in-depth**: combines with /audit-meta periodic-manual + future cadence for layered drift detection
- **No new infrastructure**: reuses reviewer's existing Bash + Grep tool access; no shell-out, no hook config, no new skill
- **Honors 6-critic-cap**: reviewer rule extension, not a new critic

### Negative / Accepted

- **Reviewer prompt grows**: ~15 LoC of new prompt for R-BOY-SCOUT semantics. Acceptable for the value delivered.
- **Reviewer must execute audit rubrics inline**: adds latency (mechanical greps on 1-5 touched files per PR). Acceptable; greps are fast.
- **Discretion judgment in D4**: reviewer must judge BLOCK vs REC per finding. Risk of over- or under-blocking. Mitigated by default-conservative-toward-REC + explicit exclusion of pending-calibration rules (DOCS-5/6/7 per #142).
- **Doesn't close #47 fully**: cadence half remains; #47 stays open until both ships.
- **Doesn't help with new check definitions**: boy-scout only consumes existing /audit-subagents + /audit-meta rubrics. Adding new check semantics requires PRDs against ADR-0011 or ADR-0017.

## Alternatives considered

- **Alt-A: Ship cadence first (the other half of #47).** Rejected per Q1=1α — hooks can't auto-invoke skills; cadence needs CI (#63) which is deferred.
- **Alt-B: Ship both halves in one PRD.** Rejected per Q1=1α — bundles two distinct architectural concerns; cadence design genuinely needs #63 first.
- **Alt-C: Add boy-scout to /audit-subagents and /audit-meta as a "called-from-reviewer" mode.** Rejected — adds skill complexity; reviewer can apply rubrics inline (simpler).
- **Alt-D: Make R-BOY-SCOUT a separate "boy-scout-critic" subagent.** Rejected — breaches ADR-0008 D7 6-critic-cap; reviewer rule extension is the right shape.
- **Alt-E: Make all R-BOY-SCOUT findings hard-BLOCK.** Rejected per D4 — risk of false-positive BLOCKs (e.g., DOCS-5/6/7 calibration false-FAILs); discretion is the right default.
- **Alt-F: Make all R-BOY-SCOUT findings recommendations only (never BLOCK).** Rejected per D4 — losing BLOCK eligibility removes the mechanical-drift-catching value the user explicitly wanted.
- **Alt-G: Defer R-BOY-SCOUT until #142 calibration is done.** Rejected — D5 carves out the calibration-pending rules; remaining rubric checks have zero false positives and can BLOCK safely now.

## Open questions deferred

- **Reviewer-inline-rubric latency**: if PR-review slows materially, future PRD could shell out to /audit-meta as Bash subprocess
- **Trigger path expansion**: `.gitignore`, `bootstrap.sh`, `.githooks/` etc. — defer until real cases
- **BLOCK-vs-REC heuristic calibration**: revisit after observation
- **Cadence integration (#47 second half)**: future PRD, complementary not redundant

## Future direction

- **#47 cadence half**: post-merge automatic /audit-meta firing (waits for CI #63)
- **Backlog #142 calibration**: when DOCS-5/6/7 false-positives are fixed, those rubrics become BLOCK-eligible
- **Reviewer-side audit-rubric execution optimization**: subprocess shell-out if inline becomes slow
- **Trigger path expansion**: add `.gitignore`, `bootstrap.sh`, etc. as patterns warrant

## References

- [ADR-0002](0002-autonomous-merge-policy.md) — reviewer-as-sole-gate (extended here)
- [ADR-0011](0011-subagent-quality-framework.md) — /audit-subagents rubric (consumed by R-BOY-SCOUT for .claude/agents/* triggers)
- [ADR-0017](0017-audit-meta-consolidation.md) — /audit-meta rubric (consumed by R-BOY-SCOUT for .claude/skills/*, decisions/*, CLAUDE.md, README.md triggers)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap (honored; reviewer rule, not new critic)
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited in D5
- [ADR-0009](0009-discipline-tightening.md) D3 — asymmetric default-BLOCK pattern (R-BOY-SCOUT inverts for advisory layer)
- [ADR-0013](0013-slicer-n3-contract-refined.md) — the convention DOCS-5 enforces (mentioned in D4 calibration carve-out)
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — the captured item this PRD ships 1/2 of (boy-scout half)
- Backlog [#142](https://github.com/vojtech-stas/project-claude/issues/142) — audit-rule calibration concerns (D5 + D4 carve-out reference)
- Backlog [#63](https://github.com/vojtech-stas/project-claude/issues/63) — CI / branch protection (cadence half awaits)
- PR [#125](https://github.com/vojtech-stas/project-claude/pull/125) — concrete motivating case (N=3 README drift caught manually)
- `.claude/agents/reviewer.md` — the file being extended with R-BOY-SCOUT
