# ADR-0052: AS-CRIT-4 recalibration — literal-heading proxy → documentation-contract check

- **Status:** Accepted
- **Date:** 2026-06-06
- **Supersedes:** the `AS-CRIT-4` mechanic (five literal-heading greps) defined inline in `.claude/skills/audit-subagents/SKILL.md` at the time of [ADR-0011](0011-subagent-quality-framework.md) D4 acceptance
- **Extends:** [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical/grep-only rubric, pattern-derived) — recalibrates one existing check within the same mechanical contract; [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (canonical output-shape standard — the authority to which AS-CRIT-4 now verifies delegation)
- **Decided in:** Grill session 2026-06-05 (Q1–Q4) alongside PRD #611

---

## Context

The dashboard Health tab's `AS-CRIT-4` column was showing **FAIL** for all or most of the 7 critics (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `backlog-critic`, `glossary-critic`, `codebase-critic`). The FAIL was a **false positive**.

The original `AS-CRIT-4` mechanic (shipped with [ADR-0011](0011-subagent-quality-framework.md) D4) grepped each critic's prompt file for five literal section headings (`Subject of review`, `^#+\s*Rubric`, `^#+\s*Findings`, `^#+\s*Summary`, `verdict:`) as a proxy for whether the critic's output body follows the 5-section verdict template defined by [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1a.

The proxy was built on an implicit assumption that critics would *reproduce* the section headings from the ADR-0005 template directly inside their prompt files. But the project had already standardized on a DRY approach (CLAUDE.md rule #9 — "Don't duplicate info; link/point to where the canonical version lives"): critics document their verdict-body output shape in an `## Output format` section that **delegates** to ADR-0005 D1a in prose, rather than re-listing the literal headings in every file. Every DRY-compliant critic therefore FAILed a check designed to reward quality.

Verification at the time of this ADR: running the two-condition documentation-contract check against all 7 current critic files shows all 7 PASS — confirming the recalibrated mechanic matches the converged practice without requiring any changes to critic prompt files.

---

## Decisions

### D1: Recalibrate AS-CRIT-4 — literal-heading proxy → documentation-contract

The AS-CRIT-4 mechanic is replaced with a **documentation-contract** check: two grep conditions must both pass:

1. `grep -cE "^#+\s*Output format" <file>` ≥ 1 — an `Output format` section is present (the conventional heading critics use to declare their output shape).
2. `grep -cF "ADR-0005" <file>` ≥ 1 — an `ADR-0005` citation is present (the canonical 5-section template authority the critic delegates to).

Both conditions ≥ 1 → **PASS**; any condition = 0 → **FAIL** (report which condition failed). The check stays static and grep-only per [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical/grep-only rubric, pattern-derived). The honest scope is "the verdict-body contract is *documented*" — the same epistemic posture AS-CRIT-3 takes for the CRITIC trailer.

**Why this is not a false proxy:** the two conditions together verify that the critic has (a) a dedicated section for output-shape documentation and (b) a reference to the canonical template authority. A critic that satisfies both demonstrably documents its output contract by delegation. A critic that lacks either has either no output-shape documentation at all, or documentation that does not anchor to the project's canonical standard.

**Why the old mechanic was the wrong proxy:** grepping for literal headings (`^#+\s*Findings`, `^#+\s*Summary`) inside the prompt file mistakes prompt-structure for output-structure. The prompt file describes how the critic should behave; the 5-section headings are the *output* the critic emits at runtime — they appear in the verdict, not necessarily in the critic's prompt. Critics that follow the DRY convention correctly have neither heading in their prompt; they have an `## Output format` section that names the headings in prose and cites ADR-0005. The old mechanic actively penalized DRY compliance — the inverse of the intended signal (issue [#561](https://github.com/vojtech-stas/project-claude/issues/561)).

### D2: Keep AS-CRIT-4 distinct from AS-CRIT-3

AS-CRIT-3 and AS-CRIT-4 cover different halves of the critic output contract:

- **AS-CRIT-3** — the machine-parsable CRITIC trailer (`VERDICT:`, `REASON:`, `ROUND:` fields). This is what `/ship` and other orchestrators parse programmatically to determine APPROVE/BLOCK and route accordingly.
- **AS-CRIT-4** — the human-readable verdict body (the 5-section template: Subject of review, Rubric, Findings, Summary, plus the Header). This is what implementers read to understand what to fix and what humans read for the synthesis.

Separate failure modes warrant separate checks: a critic could have a well-documented trailer but an undocumented body structure (CRIT-3 PASS, CRIT-4 FAIL), or vice versa. Granular FAIL attribution preserves the ability to diagnose which half of the contract is missing. No merge.

Parsimony per [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (reframe the critic meta-rule from a count-cap to a parsimony principle) is honored: this ADR recalibrates one existing check rather than adding a new one — the check count is unchanged.

### D3: Canonical ↔ dashboard lockstep

The recalibrated mechanic ships in **both** the canonical rubric (`.claude/skills/audit-subagents/SKILL.md` — the AS-CRIT-4 section + the rationale prose) **and** the dashboard implementation (`dashboard/server.py` — `_check_as_crit_4`) in the same change (PR for slice #612). The two surfaces encode the identical two-condition contract so the Health-tab grid and the canonical rubric cannot disagree.

`tools/ci-checks.sh` CHECK 9 enforces this canonical ↔ dashboard agreement mechanically on every PR (per the dashboard-trust discipline established by PRD #562). Running CHECK 9 after the slice-1 change confirms agreement.

### D4: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy explicit)

The recalibrated AS-CRIT-4 mechanic binds **forward from the merge of slice #612** (this slice). Audit runs performed before that merge used the old five-grep mechanic; their FAIL results for DRY-compliant critics are not retroactively revised. The recalibration is designed so all 7 existing critics PASS on first post-merge run — verified — so no grandfather carve-out for pre-existing FAILs is needed.

---

## Consequences

### Positive

- The Health-tab AS-CRIT-4 column renders green for all 7 critics immediately after merge, eliminating the false-red that eroded dashboard trust (the property PRD #562's `ci-checks.sh` CHECK 9 was built to protect).
- The recalibrated check rewards DRY compliance rather than penalizing it: critics that point to ADR-0005 rather than reproducing its headings are correctly identified as having a documented output contract.
- The two-condition contract is simpler (2 greps vs 5 greps) and more semantically accurate — it checks the right property at the right level of abstraction.
- Stays within the `/audit-subagents` mechanical/grep-only contract ([ADR-0011](0011-subagent-quality-framework.md) D2) — no new check, no LLM call, no invocation of the critics themselves.

### Negative / Accepted

- The documentation-contract check verifies that the output shape is *documented*, not that the critic *emits* the correct shape at runtime. This is the same epistemic limitation that AS-CRIT-3 has and is explicitly in scope per [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical/grep-only). A runtime-sampling auditor (invoking critics and grepping their actual verdicts) would require a separate design and home (rejected in PRD #611 §3 non-goals; breaks `/audit-subagents`' mechanical contract).
- A critic that has an `## Output format` section citing ADR-0005 but has drifted its actual runtime output away from the template will PASS CRIT-4 — the false-negative blind spot of any static check. Mitigated: (a) `reviewer` catches verdict-body drift at PR time via the standard critic gate, (b) the `codebase-critic` at the end of each PRD reviews cumulative semantic drift, (c) the human remains the last reader of every verdict.

---

## Alternatives considered

**Keep the five-grep mechanic, fix by adding literal headings to critic prompts.** Rejected: reproducing the ADR-0005 D1a headings into 7 critic files violates DRY rule #9 and merely relocates the false signal — it doesn't fix the root mismatch between "prompt file structure" and "runtime output structure". (PRD #611 §3 non-goals; grill Q1.)

**Merge AS-CRIT-3 + AS-CRIT-4 into a single "output contract" check.** Rejected: loses granular attribution (CRIT-3 FAIL means the orchestration contract is undocumented; CRIT-4 FAIL means the human-readable body structure is undocumented — different audiences and different remediation paths). Merging collapses two distinct concerns. (PRD #611 §3 non-goals; grill Q3.)

**Replace static check with a runtime-sampling check (invoke critics, grep their actual verdicts).** Rejected: breaks the `/audit-subagents` mechanical/grep-only contract established by [ADR-0011](0011-subagent-quality-framework.md) D2; runtime invocation of critics would also require a separate home per [ADR-0017](0017-audit-meta-consolidation.md) D6 (sibling-not-extension — mechanical/no-runtime is ADR-0011 D2's province). (PRD #611 §3 non-goals; grill Q2.)

---

## References

- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 — Canonical output-shape standard (the 5-section verdict template + CRITIC/GENERATOR trailers; the authority AS-CRIT-4 now verifies delegation against).
- [ADR-0011](0011-subagent-quality-framework.md) D2 — Mechanical/grep-only rubric, pattern-derived (the contract this recalibration stays within); D5 — Single Markdown report to stdout, no auto-capture.
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 — Reframe the critic meta-rule from a count-cap to a parsimony principle (parsimony honored — recalibrate-not-add).
- [ADR-0004](0004-bypass-prevention.md) D2 — Bootstrap-mode policy explicit.
- PRD [#611](https://github.com/vojtech-stas/project-claude/issues/611) — the feature PRD whose §5 drafted D1–D4 of this ADR.
- Issue [#561](https://github.com/vojtech-stas/project-claude/issues/561) — the captured false-positive report that motivated this recalibration.
- `.claude/skills/audit-subagents/SKILL.md` — the canonical rubric where AS-CRIT-4 is defined.
- `dashboard/server.py` `_check_as_crit_4` — the dashboard implementation locked in step with the canonical rubric per D3.
