---
title: AM-DOCS-LITERAL-DRIFT — audit-meta docs check, named-literal drift detectors (DOCS-5 N=3, DOCS-6 GLOSSARY.md)
summary: The audit-meta docs-subcommand mechanical check pair detecting two specific stale-literal drifts — DOCS-5 catches the `N=3` literal in README.md (post-ADR-0013 fix) and DOCS-6 catches GLOSSARY.md references anywhere in *.md files (post-ADR-0012 file deletion).
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-29
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-5
  - .claude/skills/audit-meta/SKILL.md DOCS-6
  - decisions/0017-audit-meta-consolidation.md D3
  - decisions/0012-glossary-consolidation-single-tier.md
  - decisions/0013-slicer-n3-contract-refined.md
---

# AM-DOCS-LITERAL-DRIFT

**AM-DOCS-LITERAL-DRIFT** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check pair detecting **named-literal drift** — specific text strings that should NOT appear because the convention they referenced has been superseded:

- **DOCS-5** — no `N=3` literal references in `README.md` that are NOT adjacent to an `ADR-0013` reference (post-[ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) drift detector; PR #125 fix).
- **DOCS-6** — no `GLOSSARY.md` references in `*.md` files outside the known-legitimate carriers (post-[ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) drift detector; the file was deleted).

Both check for absence of a known-bad literal in unanticipated contexts; matches in the allowlisted contexts PASS.

## What

The checks fire under the `docs` subcommand. Mechanics:

- **DOCS-5 (±2-line ADR-0013 proximity check):**
  ```
  grep -nF "N=3" README.md | while IFS= read -r hit; do
    lineno=$(echo "$hit" | cut -d: -f1)
    ctx=$(awk "NR>=$((lineno-2)) && NR<=$((lineno+2))" README.md)
    echo "$ctx" | grep -qF "ADR-0013" || echo "$hit"
  done
  ```
  PASS if the loop produces no output (every `N=3` occurrence is within ±2 lines of an `ADR-0013` reference); FAIL with offending lines otherwise.

- **DOCS-6 (allowlist-aware):**
  ```
  grep -rlF "GLOSSARY.md" --include="*.md" . \
    | grep -v "^\./\.git/" \
    | grep -v "^\./\.claude/worktrees/" \
    | grep -v "^\./tool-results/" \
    | grep -vE "^\./decisions/" \
    | grep -vF "./.claude/skills/audit-meta/SKILL.md" \
    | grep -vF "./.claude/skills/grill-me/SKILL.md" \
    | grep -vF "./docs/current/concepts/rules/am-docs-literal-drift.md" \
    | grep -vF "./docs/current/entities/skills/audit-meta.md" \
    | grep -vF "./docs/current/topics/knowledge-architecture.md"
  ```
  PASS if empty; FAIL with file list otherwise.

DOCS-5 uses fixed-string matching (`-F`) for speed. DOCS-5 is scoped to README.md only (the file that historically carried the wrong literal). DOCS-6 is repo-wide with allowlist exclusions for the 5 known-legitimate carriers and all `decisions/*` (ADRs documenting the file's lifecycle are immutable historical record per ADR-0001 D8).

## Why

The named-literal drift pattern catches a specific failure mode: **a convention is superseded, the ADR is written, the canonical file is updated, but cross-references in OTHER files retain the stale literal.** This is exactly what happened with:

- **`N=3`** — [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) refined the slicer's N-decompositions contract; PR #125 fixed the README but the literal could regress. DOCS-5 ensures it stays gone. The ±2-line ADR-0013 proximity check allows the legitimate citation `(N=3 or N=1 decompositions per ADR-0013)` in README.md L90 that explicitly references the ADR as context.
- **`GLOSSARY.md`** — [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) consolidated the glossary into CLAUDE.md and deleted the standalone `GLOSSARY.md` file. Any remaining reference to that filename is dead — either a broken link or a stale instruction. Five files legitimately reference it: the audit-meta skill body (documenting the check), the rule body itself (this file), the entity note, the knowledge-architecture topic synthesis, and `grill-me/SKILL.md` (which retains a historical `Read GLOSSARY.md` instruction from the pre-ADR-0012 era); all 5 are allowlisted. ADRs 0007/0009/0012/0017/0026/0031 that reference GLOSSARY.md are documenting its historical lifecycle and are allowlisted wholesale via the `decisions/*` pattern.

Each check is **purpose-built for a known regression**, not a general convention. As new conventions supersede old ones, new DOCS-* literal-drift checks may be added (each cheap, each focused on one named literal).

## How to check

When `--docs` is active:

1. Run DOCS-5: pipe `grep -nF "N=3" README.md` through the ±2-line ADR-0013 proximity filter. PASS if output empty; FAIL with offending lines otherwise.
2. Run DOCS-6: `grep -rlF "GLOSSARY.md" --include="*.md" .` with allowlist exclusions. PASS if empty; FAIL with file list otherwise.

## Examples

- **`README.md` describes slicer N as "default 3" without the literal `N=3`** → DOCS-5 PASS.
- **`README.md` contains `(N=3 or N=1 decompositions per ADR-0013)` on a line with ADR-0013 nearby** → DOCS-5 PASS (proximity check allows it).
- **`README.md` still contains a bare `N=3` not adjacent to any ADR-0013 reference** → DOCS-5 FAIL.
- **No non-allowlisted file references `GLOSSARY.md`** → DOCS-6 PASS.
- **An older subagent file still says "see GLOSSARY.md for vocabulary"** → DOCS-6 FAIL.
- **`decisions/0012-glossary-consolidation-single-tier.md` references `GLOSSARY.md` in its historical narrative** → DOCS-6 PASS (decisions/* allowlisted).
- **`.claude/skills/audit-meta/SKILL.md` mentions `GLOSSARY.md` in the DOCS-6 rule description** → DOCS-6 PASS (allowlisted).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-backlog-surfacing]]
- **related_to:** [[concepts/rules/am-docs-glossary-cap]]
