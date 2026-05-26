---
title: R-TESTS — reviewer hard-block on new behavior shipped without tests
summary: The reviewer rule that BLOCKs any PR introducing new behavior unless the diff also includes tests exercising that behavior, with explicit exemptions for docs-only, config-only, and pure refactor PRs.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 3
---

# R-TESTS

**R-TESTS** is rule 3 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any PR that introduces new BEHAVIOR (not just docs/config/refactor) unless the diff also includes tests that exercise that behavior. The rule is judgment-shaped — the reviewer identifies new behavior in the diff and verifies a corresponding test exists.

## What

The rule fires when the diff alters runtime behavior. Mechanics:

- Reviewer identifies behavior changes in the diff: new code paths, modified conditionals, new agent instructions that ALTER what the agent does on a given input.
- For each identified behavior, the reviewer searches the diff for a corresponding test (smoke test, integration test, or executable assertion).
- If new behavior with no test → BLOCK with `Missing tests: <file> introduces new behavior at <line>; no corresponding test in diff`.

What counts as "behavior":

- Executable code: functions, methods, condition branches, exception handlers.
- Agent prompts with executable shell snippets, hook configuration, runtime-loadable instructions that alter agent output on a known input.

What does NOT count:

- Pure narrative documentation in `.md` files.
- Comments in code.
- Refactors with no behavior change (verifiable by behavior-equivalent test suite passing).

## Why

R-TESTS exists because **untested behavior is regression-fragile**. Without it, the slice ships behavior the reviewer cannot mechanically verify works; future PRs cannot safely modify adjacent code without risking silent breakage; the only safety net is human QA at PRD close, which is too coarse-grained for slice-level confidence.

The exemption set is deliberately narrow: even agent prompt files (which look like prose) count as behavior IF they contain executable instructions that change agent output. This catches the failure mode where an implementer ships a new agent rule as "just narrative documentation" but the agent actually applies that rule at runtime.

## How to check

Identify new behavior in the diff. For each, find a corresponding test in the diff. If new behavior with no test → BLOCK.

```bash
gh pr diff <PR> --patch
gh pr view <PR> --json files --jq '.files[] | select(.path | test("test|spec")) | .path'
```

For prompt-bearing PRs (e.g., new subagent instruction), verify the slice body includes a smoke test or dogfood section demonstrating the instruction parses and produces expected agent output.

## Exemptions

- **Docs-only changes**: `.md` files containing only narrative documentation; comments.
- **Config-only changes**: `.gitignore`, `LICENSE`, license metadata.
- **Pure refactors** with no behavior change (verifiable by existing tests passing).
- **Skill/agent definition files** containing ONLY narrative documentation. If executable shell snippets, hook configuration, or runtime-loadable instructions that alter agent behavior are present, R-TESTS DOES fire — require a smoke test.

## Examples

- **PR adds a new `/foo` skill with a 5-step bash workflow**: BLOCK without a smoke test confirming each step parses and produces expected output.
- **PR rewords reviewer.md's adversarial-mindset paragraph**: PASS — pure narrative; no behavior change.
- **PR adds a new git hook**: BLOCK without a test confirming the hook fires on the expected event.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/rules/r-scope]]
- **part_of:** [[topics/reviewer-philosophy]]
