---
title: AM-DOCS-GLOSSARY-CAP — audit-meta docs check, CLAUDE.md glossary entry count ≤ 35 (DOCS-9)
summary: The audit-meta docs-subcommand mechanical check that the CLAUDE.md glossary section's top-level entry count stays at or below the ADR-0012 D5 soft cap of 35; exceeding triggers WARN (consolidation candidate).
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-9
  - decisions/0017-audit-meta-consolidation.md D3
  - decisions/0012-glossary-consolidation-single-tier.md D5
---

# AM-DOCS-GLOSSARY-CAP

**AM-DOCS-GLOSSARY-CAP** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check (DOCS-9) that enforces the CLAUDE.md `## Glossary` section's top-level entry count stays at or below the **soft cap of 35 entries** per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D5. Exceeding the cap triggers WARN (not FAIL) — the cap is a discoverability heuristic, not a hard contract.

## What

The check fires under the `docs` subcommand. Mechanics:

- Run: `awk '/^## Glossary/,/^## /' CLAUDE.md | grep -cE '^- \*\*'`.
- If the count is ≤ 35 → **PASS**.
- If the count is > 35 → **WARN** (consolidation candidate; entries should be reviewed for merging or pruning).

The awk pattern extracts the lines between the `## Glossary` heading and the next H2 heading; the grep counts only top-level glossary bullets (lines beginning with `- **`, the canonical entry shape). Sub-bullets (e.g., `*Scope:*` / `*Authority:*` / `*See also:*` fields per the canonical shape) are excluded — they're part of an entry, not a separate entry.

## Why

The 35-entry cap exists because the glossary is **auto-loaded into every Claude Code session's context** per the CLAUDE.md preamble. Past ~35 entries, the cost-benefit shifts unfavorably:

- **Context-window cost** — every additional entry inflates the per-session base load, leaving less room for the actual task.
- **Discoverability cost** — past ~35 entries, the glossary stops functioning as a "load-bearing terms only" quick-reference and starts becoming a "general computing dictionary" that readers skim past.
- **Maintenance cost** — every entry should be defensible per the [`glossary-critic`](../../entities/subagents/glossary-critic.md) 5-rule rubric; past 35, the audit-time pressure on each entry's defensibility relaxes.

The WARN level reflects that hitting the cap is **a signal to act, not a failure mode**. Options when WARN fires: consolidate two related entries into one, demote a generic-leaning entry back to skill-local vocabulary, or accept the cap-exceed if the new entry is genuinely load-bearing AND a careful prune of an existing entry isn't viable.

## How to check

When `--docs` is active:

1. Run `awk '/^## Glossary/,/^## /' CLAUDE.md | grep -cE '^- \*\*'`.
2. If ≤ 35 → PASS.
3. If > 35 → WARN with the current count and a "consolidation candidate" note.

## Examples

- **Glossary contains 24 entries** → DOCS-9 PASS (well under 35).
- **Glossary contains 35 entries exactly** → DOCS-9 PASS (at the cap, but not over).
- **Glossary contains 38 entries after a wave of additions** → DOCS-9 WARN (3 over; review for consolidation).
- **A new entry was added that pushes count to 36** → DOCS-9 WARN (just over).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-literal-drift]]
- **related_to:** [[entities/subagents/glossary-critic]]
