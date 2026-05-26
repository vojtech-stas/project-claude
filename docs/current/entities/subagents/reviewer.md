---
title: reviewer — adversarial PR auditor and auto-merge gate
summary: Sole gate per PR; reads PR body + diff + CLAUDE.md + ADRs; emits APPROVE/BLOCK verdict; auto-merges on APPROVE via gh pr merge --squash.
tags: [subagent, critic, gate, reviewer]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - decisions/0002-autonomous-merge-policy.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0018-boy-scout-reviewer-rule.md
---

# reviewer

The `reviewer` subagent is the **sole PR-tier gate** between an `implementer` and `main`. It is the project's primary anti-drift mechanism: every merged PR — slice, trivial, or PRD — passes through its rubric. No human approval is required at the PR layer; the human checkpoint sits one tier higher, at PRD-level via the [`qa-plan`](../../../.claude/skills/qa-plan/SKILL.md) skill.

## Role and responsibility

The reviewer has two jobs, in strict priority order:

1. **Hard-block** any PR that violates non-negotiable rules from the 12-rule rubric.
2. **Recommend** improvements on subjective items without blocking.

It does NOT edit code. It reads, judges, comments via `gh pr comment`, and (on APPROVE only) auto-merges via `gh pr merge --squash --delete-branch` per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md). On BLOCK, the PR returns to the implementer for revision; on round-3 BLOCK, the reviewer applies the `needs-human` label and comments on the parent PRD per the I5 escalation surface ([ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4).

## Invocation contract

- **Caller:** the `/ship` orchestrator (stage 5, per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D8), or any agent/human via the `Agent` tool with `subagent_type: "reviewer"`.
- **Input:** EITHER a GitHub PR reference (e.g., `vojtech-stas/project-claude#42` or a PR URL) OR an instruction to review the current branch's unpushed changes.
- **Output:** a posted PR comment (5-section verdict body + CRITIC trailer) AND a derived trailer-only return-block to the caller. Both carry identical CRITIC-trailer fields verbatim; see [[topics/output-shapes]] for the canonical schema.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` — read-only for files; carefully scoped for shell. Authorized commands: `git diff/log/branch/status`, `gh pr view/diff/list/checks/comment/merge/edit --add-label needs-human`, `gh issue view/list/comment` (round-3 escalation only). NOT authorized: `git commit/push/merge/rebase/reset/revert`, `gh pr close/edit (except needs-human)`, `gh pr review --approve`, any `Edit`/`Write`/file-mutation tool.

## Rubric (12 hard-block rules + 1 discretionary)

The reviewer applies these rules to every PR. Each linked note expands the rule's What / Why / How-to-check / Exemptions / Recovery. The atomic-note layer is the canonical home; the [`reviewer.md`](../../../.claude/agents/reviewer.md) executable shell quotes each rule's name + one-line trigger only.

**Hard-block rules (BLOCK on any violation):**

1. [[concepts/rules/r-scope]] — scope drift outside PR body
2. [[concepts/rules/r-yagni]] — unused additions
3. [[concepts/rules/r-tests]] — new behavior without tests
4. [[concepts/rules/r-conv-commits]] — Conventional Commits format violation
5. [[concepts/rules/r-no-main]] — base ≠ main; head ≠ main
6. [[concepts/rules/r-secrets]] — secret-shaped strings in diff
7. [[concepts/rules/r-pr-body]] — missing Scope / Out-of-scope / Verification sections
8. [[concepts/rules/r-adr-conflict]] — PR contradicts accepted ADR without superseding
9. [[concepts/rules/r-loc]] — slice PR ≤300 LoC of runtime-artifact diff
10. [[concepts/rules/r-closes]] — `Closes #N` to a `slice`-labeled issue
11. [[concepts/rules/r-meta]] — NEW ADR provenance (`Closes #N` to slice/prd issue OR `Co-Authored-By: Claude` trailer)

**Discretionary rule (severity-calibrated per ADR-0018 D4):**

12. [[concepts/rules/r-boy-scout]] — per-PR drift detection on audit-relevant files

(Numbering note: the rubric currently runs 12 hard-blocks + 1 discretionary = 13 lines. R-BOY-SCOUT is the discretionary 13th rule per ADR-0018; rule numbering shifts as new hard-blocks land — e.g., R-TRUTH-DOC per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D5 became the 12th hard-block, pushing R-BOY-SCOUT from 12th to 13th rubric position.)

## Relationship to other agents

- **Adversarial critic to** the [`implementer`](../../../.claude/agents/implementer.md) subagent. The implementer generates PRs; the reviewer judges them. The implementer's adversarial-mindset paragraph explicitly references "pre-empting reviewer findings is the cheapest path to APPROVE".
- **Sibling critic of** [`prd-critic`](../../../.claude/agents/prd-critic.md), [`adr-critic`](../../../.claude/agents/adr-critic.md), [`slicer-critic`](../../../.claude/agents/slicer-critic.md), [`glossary-critic`](../../../.claude/agents/glossary-critic.md), [`backlog-critic`](../../../.claude/agents/backlog-critic.md). All 6 critics conform to the same verdict template + CRITIC trailer ([[topics/output-shapes]]); the reviewer is the only one that auto-merges.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7. R-BOY-SCOUT and R-TRUTH-DOC are reviewer rule extensions, NOT new critics.
- **Authority:** [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) (autonomous merge), [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 + D4 (sole gate per PR; no human checkpoints between stages), [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md) (R-BOY-SCOUT).

## Edges

- **part_of:** [[concepts/rules/r-scope]]
- **part_of:** [[concepts/rules/r-yagni]]
- **part_of:** [[concepts/rules/r-tests]]
- **part_of:** [[concepts/rules/r-conv-commits]]
- **part_of:** [[concepts/rules/r-no-main]]
- **part_of:** [[concepts/rules/r-secrets]]
- **part_of:** [[concepts/rules/r-pr-body]]
- **part_of:** [[concepts/rules/r-adr-conflict]]
- **part_of:** [[concepts/rules/r-loc]]
- **part_of:** [[concepts/rules/r-closes]]
- **part_of:** [[concepts/rules/r-meta]]
- **part_of:** [[concepts/rules/r-boy-scout]]
- **related_to:** [[topics/reviewer-philosophy]]
- **related_to:** [[topics/reviewer-edge-cases]]
- **related_to:** [[topics/output-shapes]]
