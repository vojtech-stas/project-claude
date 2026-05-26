---
title: output shapes — canonical verdict template, CRITIC trailer, and GENERATOR trailer schemas
summary: The canonical output-shape standard for critic verdicts (5-section body + CRITIC trailer) and output-emitting generators (domain body + GENERATOR trailer), with per-agent extension examples.
tags: [output-shape, verdict-template, critic-trailer, generator-trailer, topic]
type: topic
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - CLAUDE.md
  - decisions/0005-output-shape-and-slicing-methodology.md
---

# output shapes

The canonical output-shape standard for the project's 6 critics and ~6 output-emitting generators. Authority: [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1. This topic page is the **canonical KB-layer home of the standard** — content is identical to two source locations on origin/main as of 2026-05-26:

1. `.claude/agents/reviewer.md` "Output format" section (the executable shell for the reviewer)
2. `CLAUDE.md` "Output-shape standard for subagents and output-emitting skills" section (the project-rules shell)

Both sources will eventually be thinned: reviewer.md across the T2 slice 3 cluster (per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 2), CLAUDE.md in T6 (per ADR-0031 D10 step 6). Until T6 ships, edits to ANY of the three locations (this page + reviewer.md + CLAUDE.md) must update all three to prevent drift. See PRD #253 §6 OQ-2 for the captured-issue tracking T6 cleanup.

## Scope of the standard

Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 (canonical home), subagents and output-emitting skills conform to canonical output shapes so cross-agent consumers (`/ship`, future orchestrators) can parse returns via a shared schema and so critic verdict bodies converge across all critics.

- **Critics** emit the **verdict template + CRITIC trailer** below. Current critics: [`reviewer`](../../entities/subagents/reviewer.md), `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic` (6 per the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap).
- **Output-emitting generators** emit the **GENERATOR trailer** below; their bodies remain domain-shaped (per ADR-0005 D1c). Current generators: `slicer`, `qa-plan`, `ship`, `implementer`, `qa-tester`, plus the "Final approved decomposition" output of `slicer-critic` (which doubles as a critic AND a generator).

## Verdict template (required for the 6 critics)

The critic's emitted output body has **5 required sections, in order**:

1. **Header** — `## <critic-name> verdict: [APPROVE | BLOCK] (round N/3)`
2. **Subject of review** — 2–4 sentences. What is being judged. The critic's restated spec contract.
3. **Rubric** — each criterion: PASS/FAIL + reason. Per-rule line items; numbered.
4. **Findings** — on BLOCK: numbered itemized list, mechanically-actionable (rule + section + diagnosis + concrete fix). On APPROVE: `None.`
5. **Summary** — one paragraph. The synthesis the human reads first.

Then the **CRITIC trailer** (below).

**Permitted critic-specific extensions**, appended *after* Summary, *before* the trailer:

- **Recommendations** (non-blocking) — any critic. Optional. 1-5 bullets typical.
- **Scoring matrix** — `slicer-critic` specific. Per-decomposition scoring table for N≥2 candidate decompositions.
- **Tiebreak path** — `slicer-critic` specific. The deterministic tiebreak when 2+ decompositions score identically.
- **Final approved decomposition** — `slicer-critic` specific. The chosen decomposition's slice list with parent/child edges (this is the generator-shaped half of slicer-critic's dual role).
- **R-META override notice** — `reviewer` specific. Only when R-META is `[OVERRIDE]`; quotes the override line verbatim and names the new ADR file(s) it covers.
- **Merge status** — `reviewer` specific. `reviewer` is the only critic that auto-merges. One line: `merged (commit <sha>)` on success, `failed: <error>` on auto-merge failure.

Extensions are named in each critic's own body file; this topic page does not enumerate every possible extension.

## CRITIC trailer field schema

Fenced code block at the end of the verdict output. Same fields appear verbatim in the **posted comment** (full 5-section body + extensions + trailer) AND in the **return-block to the calling agent** (trailer only, no body — for parsing efficiency per ADR-0005 D1b).

### On APPROVE

```
VERDICT: APPROVE
REASON: <one sentence>
ROUND: <N>/<max>
```

Plus permitted critic-specific extensions (e.g., reviewer's `MERGE_STATUS: merged (commit <sha>)`).

### On BLOCK (rounds 1 through max-1)

```
VERDICT: BLOCK
REASON: <one sentence>
ROUND: <N>/<max>
FAILED_RULES: <comma-separated rule IDs>
FINDINGS_COUNT: <integer>
```

`FAILED_RULES` enumerates the rule numbers (or rule IDs, depending on critic) that triggered the BLOCK — e.g., `"2,5,7"` or `"R-LOC,R-CLOSES"`. `FINDINGS_COUNT` matches the count of items in the Findings section.

### On round-max BLOCK (e.g., round 3 of 3)

Add an `ESCALATE` line to the BLOCK trailer:

```
VERDICT: BLOCK
REASON: <one sentence>
ROUND: <N>/<max>
FAILED_RULES: <comma-separated rule IDs>
FINDINGS_COUNT: <integer>
ESCALATE: needs-human
```

`ESCALATE: needs-human` is the canonical machine-readable signal that the I5 human-escalation surface fires. The reviewer ALSO performs the I5 side effects (apply `needs-human` label to the PR; comment on the parent PRD) and reports outcome via the `ESCALATION_STATUS` permitted extension:

```
ESCALATION_STATUS: applied (PR labeled needs-human; parent PRD #<n> commented) | failed: <error>
```

`ESCALATION_STATUS` records the *outcome* of the escalation actions; `ESCALATE: needs-human` records the *condition* triggering them.

## GENERATOR trailer field schema

Fenced code block at the end of the generator output:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence>
ARTIFACTS: <URLs or paths, comma-separated>
```

Plus per-agent extensions follow. **Rule:** Generator output **bodies are NOT standardized** (per ADR-0005 D1c) — each generator's body shape serves its domain (decompositions for `slicer`, test plans for `qa-plan`, chain reports for `ship`, per-criterion verdict tables for `qa-tester`). Only the trailer is canonical.

### Per-agent extension examples

The `RESULT` / `REASON` / `ARTIFACTS` triad is canonical. Below are documented per-agent extensions on origin/main:

| Generator | Extensions | Meaning |
|---|---|---|
| `slicer` | `DECOMPOSITION_COUNT: <N>` | Number of alternative decompositions produced (N≥1 per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md); N=1 reserved for degenerate cases). |
| `slicer-critic` | (uses CRITIC trailer; the generator-shaped "Final approved decomposition" is a permitted extension) | — |
| `qa-plan` | `PRD_DISPOSITION: closed-completed \| reopened-for-fix \| culled \| left-open-pending-fix` | Per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D10 — terminal state of the PRD after QA. |
| `qa-tester` | `PASS_COUNT: <N>`, `FAIL_COUNT: <N>`, `JUDGMENT_COUNT: <N>`, `EXTRACT_FAILED_COUNT: <N>` | Per ADR-0020 D9 — per-criterion verdict counts the writer renders downstream. |
| `ship` | `SLICE_COUNT: <N>`, `IMPLEMENTATION_PRS: <comma-sep URLs>`, `BLOCKED_SLICES: <comma-sep #N>`, `IN_FLIGHT_AT_FAILURE: <comma-sep #N>` | Per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2/D3 — orchestrator chain-report extensions. |
| `implementer` | `PR_URL: <URL>`, `BRANCH_NAME: <branch>`, `SLICE_ISSUE: #<N>` | Per ADR-0010 D7 — implementer's PR opening signal. |
| `audit-subagents` | `RULE_COUNT: <N>`, `FILES_AUDITED: <N>`, `PASS_COUNT: <N>`, `FAIL_COUNT: <N>` | Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4 — audit-report summary fields. |
| `audit-meta` | `STRUCT_PASS: <N>`, `STRUCT_FAIL: <N>`, `DOCS_PASS: <N>`, `DOCS_FAIL: <N>`, `WARN_COUNT: <N>` | Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D2+D3 — audit-report summary fields. |

The extension naming convention: `UPPER_SNAKE_CASE` keys, single-line values. Per-agent extensions are documented in each agent's own body file; future orchestrators read them by key.

## Posted PR comment template (reviewer-specific canonical instance)

Pulled verbatim from `.claude/agents/reviewer.md` — the reviewer is the most-load-bearing critic, so its full template is replicated here as the reference shape other critics mirror with their own rubric content:

````markdown
## reviewer verdict: **[APPROVE | BLOCK]** (round <N>/3)

### Subject of review
<2-4 sentences. State what THIS PR was supposed to accomplish, drawn from the PR body's stated scope, linked GitHub issues' acceptance criteria, any referenced ADRs, and the PRD if linked. This is the spec contract you are judging the diff against — making your interpretation visible to the human at QA time. If you couldn't form a clear picture, BLOCK with "task intent unclear".>

### Rubric
- [PASS/FAIL] 1. Scope: <one-line verdict>
- [PASS/FAIL] 2. YAGNI: <one-line verdict>
- [PASS/FAIL] 3. Tests for new behavior: <one-line verdict>
- [PASS/FAIL] 4. Conventional Commits: <one-line verdict>
- [PASS/FAIL] 5. No commits to main: <one-line verdict>
- [PASS/FAIL] 6. No secrets: <one-line verdict>
- [PASS/FAIL] 7. PR body complete (scope/out-of-scope/verification): <one-line verdict>
- [PASS/FAIL] 8. No ADR conflicts: <one-line verdict>
- [PASS/FAIL] 9. R-LOC (≤300 LoC runtime-artifact diff): <one-line verdict, include the counted N>
- [PASS/FAIL] 10. R-CLOSES (Closes #<n> references a valid slice-labeled issue): <one-line verdict>
- [PASS/FAIL/OVERRIDE] 11. R-META (new ADR additions show subagent provenance): <one-line verdict; mark [PASS] when no new ADR file is added or when a signal is satisfied, [OVERRIDE] when R-META-OVERRIDE is present, [FAIL] otherwise>
- [PASS/FAIL] 12. R-TRUTH-DOC (ADR-touching PR also updates docs/current/<topic>.md per ADR-0026 D5): <one-line verdict>

### Findings
<On BLOCK: numbered list. For each blocked rule: rule number + file:line reference + 1-3 sentence diagnosis + concrete fix the implementer can apply mechanically. Be specific.
On APPROVE: "None.">

### Summary
<One paragraph. State verdict, key reason. If BLOCK: what the implementer should fix. If APPROVE: confirm you will auto-merge after this comment posts.>

### R-META override notice (only if R-META is [OVERRIDE])
<Permitted critic-specific extension. Quote the R-META-OVERRIDE: <rationale> line verbatim and list the new ADR file paths it covers. Omit this section entirely if R-META is [PASS] or [FAIL].>

### Recommendations (non-blocking)
<Optional permitted extension. 1-5 bullets. Each on its own line.>

### Merge status (only on APPROVE, populated after the merge attempt completes)
<Permitted reviewer-specific extension per ADR-0005 D1 — reviewer is the only critic that auto-merges. One line: "merged (commit <sha>)" on success, or "failed: <error>" on auto-merge failure. Omit on BLOCK.>

<CRITIC trailer — fenced code block per the schema above>

---
*Posted by `reviewer` subagent. Auto-merge follows on APPROVE per ADR-0002. Human checkpoint is at PRD-level via the `qa-plan` skill.*
````

`[PASS/FAIL]` is placeholder syntax — write either literal `[PASS]` or `[FAIL]` for each line in the actual comment. Plain text is used (not emoji) for terminal portability across Windows/Linux/macOS.

## Verdict-comment vs return-block (OQ#1 resolution)

Per ADR-0005 D1b and PRD #28 §6 OQ#1 resolution preserved in reviewer.md:

The **posted PR comment** (via `gh pr comment <PR> --body-file <tempfile>`) is the **canonical verdict-template instance** — the full 5-section body + permitted extensions + CRITIC trailer. The **return-block to the calling agent** is the **derived trailer-only summary** — same CRITIC-trailer fields (plus any permitted extensions like `MERGE_STATUS`), with no body sections — for parsing efficiency.

The two emissions carry the same trailer fields verbatim; the difference is only that the posted comment additionally renders the 5-section human-readable body above the trailer.

## Why this matters

Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, the standard exists for two reasons:

1. **Cross-agent consumers parse via shared schema.** `/ship` reads CRITIC and GENERATOR trailers programmatically to chain stages. Future orchestrators (impact-analyst, kb-maintainer per ADR-0031 D10) consume the same trailers. Without a canonical shape, each consumer would need bespoke per-agent parsers.
2. **Critic verdict bodies converge across critics.** The 6 critics have very different rubrics (reviewer judges PR diffs; slicer-critic judges decompositions; backlog-critic judges captured items). The 5-section body shape (Header → Subject → Rubric → Findings → Summary) gives humans a stable reading order regardless of which critic emitted the verdict.

See [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 for the canonical specification and rationale; D4 records the bootstrap-mode rollout (each subagent/skill file becomes canonical at the moment its alignment slice merges).

## Edges

- **defines:** [[concepts/glossary/critic-trailer]]
- **defines:** [[concepts/glossary/generator-trailer]]
- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[topics/reviewer-philosophy]]
- **related_to:** [[topics/reviewer-edge-cases]]
- **related_to:** [[concepts/glossary/critic]]
