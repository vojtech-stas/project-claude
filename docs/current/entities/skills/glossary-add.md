---
title: glossary-add — single-term interactive flow with glossary-critic gate
summary: Interactive single-term flow per ADR-0007 D4 + ADR-0012 D1; collects term/definition/scope/authority, drafts both the atomic concept note at docs/current/concepts/glossary/<slug>.md and the CLAUDE.md INDEX row, runs glossary-critic in a ≤3-round APPROVE/BLOCK loop, then opens a trivial-lane PR on APPROVE.
tags: [skill, glossary, generator, interactive, glossary-add]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/glossary-add/SKILL.md
  - decisions/0007-vocabulary-glossary-and-grill-me-extension.md
  - decisions/0012-glossary-consolidation-single-tier.md
  - decisions/0031-knowledge-architecture-v2.md
---

# /glossary-add

The `/glossary-add` skill is the **explicit write path** for the glossary per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4. It adds exactly **one** term per invocation: interview the user for the required fields (or accept inline args), draft the entry markdown using the [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 canonical shape, invoke [`glossary-critic`](../subagents/glossary-critic.md) in a ≤3-round APPROVE/BLOCK loop, and on APPROVE open a `hotfix/glossary-<term>` PR with the `trivial` label.

The complementary **discretionary surfacing path** — subagents inlining *"Heads up: 'X' looks glossary-worthy — run `/glossary-add` to capture"* — is non-mandatory and described in each agent's own body file.

## Role and responsibility

`/glossary-add` has four jobs, in order:

1. **Collect required fields** — `term`, `definition` (one declarative sentence), `scope` category (exactly one of `a` project jargon / `b` external standard / `c` common word narrowed here per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3), `authority` (`ADR-NNNN D-X`, a URL, or `external`).
2. **Draft both artifacts** per the dual-tier knowledge architecture established by [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 + D10 step 1 (executed in PRD #245): (a) a full atomic concept note at `docs/current/concepts/glossary/<slug>.md` (the canonical home; 50–100 LoC body + YAML frontmatter + typed edges per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D4 + D5 + D3), and (b) a single-line INDEX row appended to the `## Glossary` section of `CLAUDE.md` at the alphabetically-correct position, pointing to the atomic note.
3. **Invoke `glossary-critic`** in a ≤3-round APPROVE/BLOCK loop. The 5-rule rubric per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D5 + [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D4: scope category (a/b/c), no duplicate, one-sentence definition, authority field, inclusion threshold (≥3 citations across ≥2 of {`decisions/`, `.claude/agents/`, `.claude/skills/`}).
4. **Open the trivial-lane PR on APPROVE.** Branch `hotfix/glossary-<kebab-term>`; label `trivial` per CLAUDE.md I3 (skips slice ceremony). PR body includes Scope + the critic's APPROVE verdict for reviewer-time inspection.

## Invocation contract

- **Caller:** the user via `/glossary-add` (interactive) or `/glossary-add <term> --definition "..." --category a|b|c --authority "..."` (inline args).
- **Input:** required fields above; missing fields fall back to one-question-at-a-time prompts.
- **Output:** the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) with `TERM` and `CRITIC_ROUND` per-agent extensions, plus the opened PR URL in `ARTIFACTS:` on SUCCESS.
- **Tool boundaries:** `Read`, `Write` (for the atomic note), `Edit` (for CLAUDE.md INDEX row), `Bash` (`git`, `gh pr create`), `AskUserQuestion` (interactive field collection), `Agent` (glossary-critic dispatch).

## Glossary cap warning (soft, not mechanical)

Before drafting, count existing INDEX rows; if the count is at or above the ~35 soft cap per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D5, surface a warning but proceed. The cap is soft, not mechanically enforced. `glossary-critic`'s rule 5 (inclusion threshold) is the load-bearing gate per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2.

## Round-3 BLOCK handling

On `VERDICT: BLOCK` with `ROUND == 3` (or `ESCALATE: needs-human`) → STOP. Do NOT open the PR. Surface the verdict + failing findings to the user. Per the I5 escalation pattern, this is the user-revises-and-retries surface; the skill is the gatekeeper for the trivial-lane PR — a thrice-blocked entry never reaches `reviewer`.

## Relationship to other skills and agents

- **Sibling to** [`/glossary-fold`](glossary-fold.md) — single-entry interactive flow vs bulk-fold from `## Local vocabulary` sections per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D2.
- **Invokes** [`glossary-critic`](../subagents/glossary-critic.md) per entry.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/glossary-add` is a skill, its gate is `glossary-critic`.
- **Authority:** [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 (entry shape), D3 (scope rule), D4 (explicit write path), D7 (bootstrap-mode); [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D1 (single-tier consolidation), D2 (≥3-citations inclusion threshold), D4 (critic rubric updated to 5 rules), D5 (~35-entry soft cap); [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 + D10 step 1 (dual-tier atomic note + INDEX row).

## Edges

- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[entities/skills/glossary-fold]]
- **related_to:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/trivial-lane]]
- **related_to:** [[concepts/glossary/generator-trailer]]
