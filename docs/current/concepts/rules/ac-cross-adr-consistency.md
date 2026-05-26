---
title: AC-CROSS-ADR-CONSISTENCY — adr-critic criterion 2, no silent contradiction with accepted ADRs without supersession header
summary: The adr-critic rule that a draft ADR may not silently contradict any accepted ADR — any decision that overrides a prior accepted decision MUST carry an explicit `Supersedes:` header naming the specific D-ID being overridden.
tags: [rule, adr-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md criterion 2
  - decisions/README.md (supersession-via-new-ADR immutability rule)
  - decisions/0004-bypass-prevention.md D1
---

# AC-CROSS-ADR-CONSISTENCY

**AC-CROSS-ADR-CONSISTENCY** is criterion 2 in the [`adr-critic`](../../../.claude/agents/adr-critic.md) rubric. It enforces that a draft ADR does not silently contradict any accepted ADR. If the draft contradicts an accepted ADR's decision, the draft MUST carry an explicit `Supersedes:` header entry citing the specific decision being overridden by **D-ID** (e.g., `ADR-0003 D2`, not "ADR-0003" alone, and not "parts of ADR-0003").

Implicit contradiction without supersession is the precise defect this rule exists to catch — the failure mode where a new ADR quietly assumes a different policy than a prior accepted ADR, leaving both on the record with no documented relationship and downstream consumers unable to tell which one binds. Paired with [AC-SUPERSEDES-BY-D-ID](ac-supersedes-by-d-id.md) which checks that the cited D-ID is actually accurate; this rule first checks that supersession was declared at all.

## What

The rule fires on every draft ADR's Decisions section. Mechanics:

- For each Decision in the draft, compare against any accepted ADR's decisions in the same problem area (Glob `decisions/*.md`; read those whose theme overlaps).
- If a contradiction exists AND no `Supersedes:` header entry names the specific D-ID being overridden → FAIL with `"silent contradiction: <draft section> overrides <ADR-NNNN D-X> without Supersedes header"`.
- A `Supersedes:` entry that lists only the ADR number (e.g., `Supersedes: ADR-0003`) without a D-ID is treated as insufficient → FAIL with `"supersession lacks D-ID granularity"`.

## Why

This rule exists because ADRs are **immutable after acceptance** per `decisions/README.md`. The only legal way to override a prior decision is a new ADR with an explicit `Supersedes:` header naming the specific D-ID. Without this discipline:

- Two ADRs sit on the record both claiming authority over the same policy area, with no way for downstream consumers to know which binds.
- Future ADRs that cite the obsolete decision propagate the contradiction.
- The `git log` audit trail loses its supersession semantics — `git blame` shows only "this was added," not "this overrode X".

The asymmetric cost: a silent contradiction discovered at ADR-draft time costs one revision round; the same contradiction discovered after merge costs an ADR-bis (a corrective new ADR) plus reconciliation of every downstream cite.

## How to check

For each draft ADR:

1. Read the Decisions section. Identify the problem area each Decision addresses.
2. `Glob decisions/*.md`; for any accepted ADR whose theme overlaps, `Read` it and locate its Decisions in the same problem area.
3. For each potential contradiction, check the draft's `Supersedes:` header.
4. If the contradiction is real AND no `Supersedes:` entry names the specific D-ID being overridden → FAIL.

## Examples

- **Draft D2 says "Use squash-merge always"; ADR-0002 D1 says "Use merge-commit"; draft has no `Supersedes:` header** → FAIL (silent contradiction).
- **Same scenario but draft header reads `Supersedes: ADR-0002 D1`** → PASS for this rule (then AC-SUPERSEDES-BY-D-ID verifies the D-ID accuracy).
- **Draft introduces an unrelated new mechanism with no overlap to any prior ADR** → PASS (no contradiction to declare).

## Edges

- **part_of:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/rules/ac-supersedes-by-d-id]]
- **related_to:** [[concepts/rules/ac-immutability-respected]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/supersession]]
