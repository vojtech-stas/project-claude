---
name: audit-subagents
description: Periodic mechanical audit of subagent-prompt quality. Scans every file under `.claude/agents/*.md`, classifies each as critic or generator, applies the 10-check `scope`-tagged grep rubric, and emits a single Markdown PASS/FAIL report. No-args invocation; advisory output only (no auto-capture, no PR, no critic gate). Use when you suspect subagent drift, after merging a convention-changing ADR, or on the cadence backlog #47 will eventually define.
---

This skill is the mechanical drift-detector for subagent prompts under `.claude/agents/`. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md), it codifies conventions from [ADR-0001](../../../decisions/0001-foundational-design.md) D6, [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8, and [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 as literal `grep` patterns producing deterministic PASS/FAIL per (subagent, applicable check) pair.

Sibling skill of [`/audit-meta`](../audit-meta/SKILL.md) per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D6 (not an extension — separate domains).

**Ownership rationale** (ADR-0011 D1): skill (not 7th critic — ADR-0008 D7 cap) and not a reviewer rule (PR-time gating misses drift in unchanged files).

**Default conservative.** When a grep pattern is ambiguous (literal string only inside a quoted example), FAIL. Asymmetric-cost: spurious FAIL costs one user-glance; wrong-PASS lets real drift slip past (the #93 failure mode).

---

## Invocation

```
/audit-subagents
```

No arguments per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D7. Globs `.claude/agents/*.md`, applies the rubric per file, prints the report to stdout. Does NOT call `gh issue create`, does NOT open a PR, does NOT modify any tracked file.

---

## Process

1. **List subagents.** `Glob` `.claude/agents/*.md`. Non-recursive per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D8 — the skill does NOT audit `.claude/skills/audit-subagents/SKILL.md` itself.
2. **Classify each file** per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3: filename ends `-critic.md` OR is exactly `reviewer.md` → critic; else generator.
3. **Apply the rubric** below. Each check declares a `scope:` tag (`all` | `critic` | `generator`). Skip checks whose scope does not match the file's classification. Honor each check's optional `excludes:` allowlist — excluded pairs render `N/A (excluded per rubric)` and are omitted from FAIL enumeration.
4. **Aggregate** into the Markdown report — one H2 per subagent, one row per applicable check (`PASS` / `FAIL` / `N/A (excluded per rubric)` / `—`).
5. **Emit the report to stdout** followed by the canonical GENERATOR trailer.

---

## Rubric (10 checks; ADR-0011 D4)

**Coverage arithmetic** (ADR-0011 D4 at current 6-critic + 2-generator baseline): 5 × 8 + 4 × 6 + 1 × 2 = baseline 66 evaluations; effective 64 after CRIT-2 + ALL-4 exclusions of `backlog-critic.md`.

**Per-check `excludes:` schema.** A check MAY declare `excludes: <comma-separated subagent filenames>`. For excluded pairs the runner renders `N/A (excluded per rubric)` instead of PASS/FAIL and omits the pair from the FAIL enumeration.

---

### AS-ALL-1 — frontmatter fields (scope: all)

**Mechanic:** `grep -cE "^(name|description|tools|model):" <file>` — count ≥ 4 → **PASS**; count < 4 → **FAIL** (one or more required fields missing).

The pattern matches line-starts only (anchored `^`), so YAML fields embedded inside prose or example blocks do not satisfy the check — only true frontmatter declarations count.

**Rationale:** [ADR-0001](../../../decisions/0001-foundational-design.md) D6 defines the canonical subagent shape: a YAML frontmatter block declaring `name` (identity), `description` (drives auto-delegation), `tools` (boundaries the runtime enforces), and `model` (model choice). A missing field either prevents the subagent from loading (`name`) or silently widens its capabilities (`tools` missing → default-broad). This is the cheapest, most-foundational drift detector: it catches subagents that were hand-edited to remove fields, copy-pasted from incomplete templates, or migrated from a shape that pre-dates ADR-0001.

---

### AS-ALL-2 — "Tool boundaries" section heading (scope: all)

**Mechanic:** `grep -cE "^#+\s*Tool boundaries" <file>` — count ≥ 1 → **PASS**; count = 0 → **FAIL**. Headings at any depth (H1, H2, H3, ...) satisfy the check.

**Rationale:** The YAML `tools:` frontmatter field tells the runtime which tools to expose, but carries no human-readable rationale. The "Tool boundaries" prose section is where the subagent author explains *why* — e.g., "Forbidden: `Agent` — no recursive subagent invocation per ADR-0010 D6". For critics in particular, this section documents the "no `Edit`/`Write` on tracked files" convention. Missing the section signals either skipped design discipline or drifted tool-boundary contract.

---

### AS-ALL-3 — cross-reference section heading (scope: all)

**Mechanic:** `grep -ciE "^#+\s*.*(References|Related|See also|Cross-refs)" <file>` — count ≥ 1 → **PASS**; count = 0 → **FAIL**. The pattern is case-insensitive (`-i`) and accepts all four enumerated variants.

**Note:** Pattern was **broadened from the original literal `^#+\s*References`** after PR #96 dogfood showed 7 of 8 subagents FAILing — the convention is "any heading-shaped cross-link section", not the exact word "References".

**Rationale:** A subagent without a cross-reference section is a maintenance liability: future readers cannot trace design constraints back to their ADRs, cannot find sibling agents whose rubrics or output shapes the subagent must align with, and cannot verify consistency with pipeline conventions. The breadth of the pattern (4 variants, case-insensitive) is intentional — the rule cares about *presence* of a back-link section, not exact heading text.

---

### AS-ALL-4 — surfacing-convention prose (scope: all; excludes: backlog-critic.md)

**Mechanic:** `grep -cE "(\x60backlog\x60-labeled|--label backlog)" <file>` — count = 0 → **PASS**; count ≥ 1 → **FAIL**.

`excludes: backlog-critic.md` — whose domain IS the backlog tier per ADR-0008 D2; excluded pair renders `N/A (excluded per rubric)`.

**Default-conservative rendering:** if a match appears anywhere in the file — including inside example / quoted blocks — FAIL. Spurious FAIL costs one user-glance round; missed real drift is the #93 failure mode (deferred work surfaced directly into the curated `backlog` queue, bypassing `backlog-critic`'s quality gate).

**Rationale:** Post-[ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 / [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2, the convention is to capture into the `captured` tier and let `backlog-critic` promote to `backlog`. Subagent bodies that still say `--label backlog` or `` `backlog`-labeled `` instruct agents to skip the gate — the exact regression #93 catches. The mechanical grep cannot distinguish "this file's subject IS the backlog label" from "this file is using it as a surfacing idiom (drift)", so the `backlog-critic.md` allowlist is required.

---

### AS-ALL-5 — entry-protocol section heading (scope: all)

**Mechanic:** `grep -cE "^#+\s*(Mandatory reading order|When invoked)" <file>` — count ≥ 1 → **PASS**; count = 0 → **FAIL**. Either variant satisfies the check.

**Rationale:** Subagents run in isolated context windows; they do NOT inherit the main agent's context. Without an explicit "read this first" section, the subagent risks operating on stale assumptions or missing constraints from ADRs / parent PRDs / linked issues. Critics typically have "Mandatory reading order" (ground the verdict in linked artifacts); generators typically have "When invoked" (walk a deterministic process from clear input to clear output). Missing both is a strong signal the subagent will silently make wrong calls on cold-start invocations.

---

### AS-CRIT-1 — "Default conservative" clause (scope: critic)

**Mechanic:** `grep -cF "Default conservative" <file>` — count ≥ 1 → **PASS**; count = 0 → **FAIL**. `-F` forces fixed-string matching; the literal must appear verbatim. Generators render `—`.

**Rationale:** [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 establishes the **asymmetric-cost principle**: a spurious BLOCK costs one human-prompt round to refute; a wrong APPROVE lets a real defect ship into a merged PR (much more expensive to revert). Critics must bias their default toward BLOCK on ambiguity. Hard-coding "Default conservative" as a literal string check (rather than a semantic check) catches critic prompts edited to remove the clause, copy-pasted from a pre-ADR-0009 template, or drifted into permissive defaults. A FAIL here is a strong signal the critic will silently flip APPROVE in close cases. Note: "default-conservative" (lowercase + hyphen) does NOT satisfy the case-sensitive `-F` grep.

---

### AS-CRIT-2 — adversarial mindset block (scope: critic; excludes: backlog-critic.md)

**Mechanic:** `grep -cE "(paranoid|Adversarial mindset)" <file>` — count ≥ 1 → **PASS**; count = 0 → **FAIL**. `excludes: backlog-critic.md` renders `N/A (excluded per rubric)`. Generators render `—`.

**Rationale:** A critic's job is **adversarial audit** — by default, the reading-mode should be "find what's wrong", not "find what's right". Without a mindset block, critics drift toward leniency. [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4 introduces two canonical forms — "paranoid" (visceral) and "Adversarial mindset" (formal as section heading); either suffices. The `backlog-critic.md` exclusion exists because ADR-0009 D4 deliberately excluded it: its single-fire autopilot semantics (per ADR-0008 D2) differ from the ≤3-round critics that received the mindset block. Flagging `backlog-critic.md` as a CRIT-2 FAIL would contradict the explicit ADR decision.

---

### AS-CRIT-3 — CRITIC trailer fields (scope: critic)

**Mechanic:** Run three fixed-string greps and require ALL three:

- `grep -cF "VERDICT:" <file>` ≥ 1 AND
- `grep -cF "REASON:" <file>` ≥ 1 AND
- `grep -cF "ROUND:" <file>` ≥ 1.

All three counts ≥ 1 → **PASS**; any count = 0 → **FAIL** (report the missing field(s)). Generators render `—`.

The check verifies the trailer is *documented in the critic body*, not that it is emitted at runtime.

**Rationale:** The CRITIC trailer is the machine-parsable verdict-output contract: downstream consumers (`/ship`, future orchestrators) parse it to determine APPROVE/BLOCK and route accordingly. A critic that does not document the trailer will either omit it at runtime (silent break) or invent a non-canonical shape (parser break). Checking all three fields together (rather than just one) catches the common copy-paste drift pattern: a critic with `VERDICT:` and `REASON:` but missing `ROUND:` produces a trailer useless for the ≤3-round loop.

---

### AS-CRIT-4 — 5-section verdict template (scope: critic)

**Mechanic:** Run five greps and require ALL five:

- `grep -cF "Subject of review" <file>` ≥ 1 AND
- `grep -cE "^#+\s*Rubric" <file>` ≥ 1 AND
- `grep -cE "^#+\s*Findings" <file>` ≥ 1 AND
- `grep -cE "^#+\s*Summary" <file>` ≥ 1 AND
- `grep -cE "verdict:" <file>` ≥ 1.

All five counts ≥ 1 → **PASS**; any count = 0 → **FAIL** (report the missing section(s)). Generators render `—`.

The canonical 5-section shape: (1) Header — `## <critic-name> verdict: [APPROVE | BLOCK] (round N/3)`; (2) Subject of review — restated spec contract; (3) Rubric — per-criterion PASS/FAIL; (4) Findings — itemized list on BLOCK, `None.` on APPROVE; (5) Summary — one-paragraph synthesis.

**Rationale:** The 5-section verdict template is the converged shape across the 4 ≤3-round critics (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`) per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1a. A critic that omits a section produces a verdict the user (and downstream consumers) cannot parse consistently — Summary is what humans read first; Findings are what implementers act on. Checking all five together catches partial migrations: critics that added the CRIT-3 trailer but never updated their body template, or critics copy-pasted from an older 3-section shape pre-dating ADR-0005.

---

### AS-GEN-1 — GENERATOR trailer fields (scope: generator)

**Mechanic:** Run three fixed-string greps and require ALL three:

- `grep -cF "RESULT:" <file>` ≥ 1 AND
- `grep -cF "REASON:" <file>` ≥ 1 AND
- `grep -cF "ARTIFACTS:" <file>` ≥ 1.

All three counts ≥ 1 → **PASS**; any count = 0 → **FAIL** (report the missing field(s)). Critics render `—`.

The check verifies the trailer is *documented in the generator body*, not that it is emitted at runtime. Generators MAY add per-agent extension fields (e.g., `PR_URL`, `BRANCH_NAME`, `SLICE_ISSUE` for implementer; `SLICE_COUNT` for slicer; `SUBAGENTS_AUDITED` for this skill) but the three core fields are non-negotiable.

**Rationale:** The GENERATOR trailer is the machine-parsable output-shape contract for non-critic agents: downstream consumers parse `RESULT: SUCCESS | STOPPED | INVALID_INPUT` to determine whether to chain, retry, or escalate. A generator that does not document the trailer will either omit it at runtime (silent break) or invent a non-canonical shape (parser break). The three required fields are the **minimum viable contract** per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c.

---

## Report shape

Print one Markdown H2 per subagent, then a per-file table whose columns are the applicable check IDs. End with a Summary section enumerating every FAIL by `(file, check ID)`. Excluded pairs appear only in the per-subagent table as `N/A (excluded per rubric)`; not in the FAIL list.

Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5, the report is advisory only — the user reads it and captures real drift findings per CLAUDE.md rule #11 manually.

---

## Canonical GENERATOR trailer (ADR-0005 D1c)

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "audited 8 subagents, 5 FAILs (all ALL-4, duplicates of backlog #93)">
ARTIFACTS: <path to report if persisted, else "stdout">
SUBAGENTS_AUDITED: <integer>
CHECK_EVALUATIONS: <integer; baseline 66, effective 64 with current CRIT-2 + ALL-4 exclusions of backlog-critic.md>
FAIL_COUNT: <integer>
```

`SUBAGENTS_AUDITED` / `CHECK_EVALUATIONS` / `FAIL_COUNT` are per-agent extensions per ADR-0005 D1c. `RESULT: SUCCESS` regardless of FAIL count — the audit ran; FAILs are advisory findings, not runtime failures. `RESULT: STOPPED` for runtime errors (file-read, glob); `RESULT: INVALID_INPUT` if invoked with unexpected positional arguments (the no-args contract per ADR-0011 D7).

---

## Tool boundaries

Allowed: `Read`, `Glob`, `Grep`, `Bash` (for executing the grep patterns above against globbed files).

Forbidden: `Edit`, `Write` (advisory only); `Agent` (no recursive invocation — not a critic, no adversarial pair per ADR-0011 D1); `gh issue create` / `gh pr create` (no auto-capture per ADR-0011 D5).

---

## References

- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D1 (skill ownership), D2 (mechanical-only rubric), D3 (classifier), D4 (the 10 checks), D5 (single Markdown report, no auto-capture), D6 (rubric embedded), D7 (no-args invocation), D8 (bootstrap-mode + non-recursive), D9 (sibling backlog relationships).
- [ADR-0001](../../../decisions/0001-foundational-design.md) D6 — subagent definition (sources AS-ALL-1, AS-ALL-2).
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1a/D1b/D1c — verdict template + CRITIC + GENERATOR trailers (sources AS-CRIT-3, AS-CRIT-4, AS-GEN-1, this skill's own output shape).
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap, honored), D8 (surfacing convention — sources AS-ALL-4).
- [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 (default-BLOCK — sources AS-CRIT-1), D4 (adversarial mindsets — sources AS-CRIT-2).
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — T5 thin-prompt migration; full rule bodies previously in the KB layer (now inlined per ADR-0032 D1).
- Backlog [#93](https://github.com/vojtech-stas/project-claude/issues/93) — surfacing-convention drift fix that AS-ALL-4 detects.
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — future post-PRD audit pipeline; natural consumer of this skill per ADR-0011 D9.
