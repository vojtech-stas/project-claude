---
title: slicer — N=3 vertical-decomposition generator for PRDs
summary: Given a PRD, produces N=3 alternative vertical-slice decompositions (with N=1 degenerate carveout); applies hamburger-vertical + SPIDR + cascade-doc checks at slicing time; emits to slicer-critic, never posts issues.
tags: [subagent, generator, pipeline, slicer]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0013-slicer-n3-contract-refined.md
---

# slicer

The `slicer` subagent is the **decomposition generator** at stage 3.5 of the autonomous pipeline. Given a PRD (issue reference or inline body), it emits N=3 alternative vertical-slice decompositions of the work, which the downstream [`slicer-critic`](slicer-critic.md) scores, picks one of, and runs a single revision loop over before any GitHub issues get posted. The slicer does not post issues, does not pick the winner, and does not run any revision loop itself — it generates the alternatives and stops.

This entity note is the **canonical full role synthesis** for the slicer subagent. After the T3 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md)), the operational `.claude/agents/slicer.md` carries only the prompt-level operational mechanics (mandatory reading order, output format, tool boundaries) and links here for methodology depth, the N=1 carveout pattern, and per-technique deep-dives.

## Role and responsibility

The slicer has two jobs, in strict priority order:

1. **Generate N=3 genuinely-different decompositions** (with the N=1 carveout for degenerate cases — see below) that together deliver the PRD's §2 success criteria without violating §3 non-goals or §6 rabbit-holes.
2. **Apply the slicing-methodology checks at generation time** — hamburger-vertical for slice 1 of each decomposition, SPIDR split-fallback hints for near-cap slices, cascade-doc identification per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3.

It does NOT score its own output, post issues, or invoke other agents. It generates the decomposition block + [[topics/output-shapes]] GENERATOR trailer and returns.

## Invocation contract

- **Caller:** the `/ship` orchestrator at stage 3.5 (per [`.claude/skills/ship/SKILL.md`](../../../.claude/skills/ship/SKILL.md)), invoked through `/to-issues` per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3. May also be invoked directly via the `Agent` tool with `subagent_type: "slicer"`.
- **Input:** EITHER a GitHub PRD issue reference (e.g., `vojtech-stas/project-claude#3` or a PRD URL) OR the full PRD markdown body inline in the prompt. Default: assume issue reference unless the prompt clearly contains the PRD text inline.
- **Output:** the "Slicer output for PRD #N" block (per-decomposition slice tables + INVEST detail + cross-decomposition summary) PLUS the canonical GENERATOR trailer with the `DECOMPOSITION_COUNT` per-agent extension. See [[topics/output-shapes]] for the canonical schema.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (read-only `gh` / `git` only). NOT authorized: any file mutation (`Write`/`Edit`), `gh issue create` / `gh issue comment` / `gh issue edit` for issue posting, branch creation, agent invocation.

## N=3 contract and the N=1 degenerate carveout

Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3, **N is fixed at 3 by default**. The slicer must produce three meaningfully different decompositions — varying at least one of (walking-skeleton choice, risk ordering, granularity) between any two alternatives. Three flavors of the same plan is a contract violation.

Per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D1 and D2, the slicer MAY declare **N=1 with explicit rationale** when all three candidates would produce bit-identical post-merge end-state (same files, same LoC, same content — modulo commit ordering or trivial rewording that `gh pr merge --squash` collapses). The N=1 rationale must answer the three D3 questions: which PRD section locks the shape, what variation axis was rejected as non-meaningful, whether N=3 would have produced genuinely-different alternatives. The carveout is a precision tool for degenerate cases (PRD #100 single-file calibration, PRD #103 5-file mechanical swap, PRD #111 6-file consolidation are the original grounding examples) — not a general shortcut. Bias toward N=3 unless certainty about bit-identical end-state. See [[patterns/n1-degenerate-carveout]] for the full pattern.

## Slicing-methodology checks (applied at generation)

The methodology overview lives in `CLAUDE.md` "Slicing logic" section (canonical home per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2). The slicer applies three checks per candidate decomposition:

1. **Hamburger-vertical check for slice 1.** Slice 1 of every decomposition must cut through every layer end-to-end (schema / logic / UI / test, or domain-equivalent — for agent-workflow PRDs typically spec → ADR → agent prompt → exemplar invocation). Crude is acceptable; layered-only is not. Horizontal layering ("build all the modules first, wire them up later") is the explicit anti-pattern per CLAUDE.md rule #2 and [[concepts/glossary/hamburger-method]]. Reject any candidate slice 1 that builds one layer in isolation; replace with a thinner end-to-end slice.
2. **SPIDR split-fallback hint** ([[concepts/glossary/spidr]]). For any slice that approaches the PRD's §4 LoC cap, name a SPIDR-style split-fallback hint in the slice's `Risk` field or the cross-decomposition summary. S/I/R (Spike / Interface / Rules) are the typically-applicable techniques for this project's agent-workflow domain; P/D (Path/Data) rarely apply. The hint is a precomputed answer to "if this slice overruns the cap, how would we split it?" — not a commitment to split.
3. **Cascade-doc check** per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3. For each candidate decomposition, identify cascade-docs — files that should update to reflect the new feature even when not strictly required by §2 acceptance criteria: `README.md`, `CLAUDE.md` Map rows + Pipeline-stage rows, `decisions/README.md` ADR index rows, downstream skill/subagent bodies referencing the changed area, the Glossary. Add a slice (or merge into an existing slice) to cover each. When no cascade-docs apply, state so explicitly with a one-line justification. See [[patterns/cascade-doc-check]] for the full pattern.

Slice INVEST shape ([[concepts/glossary/invest]]) is the per-slice quality check — each slice satisfies Independent / Negotiable / Valuable end-to-end / Estimable / Small / Testable. The downstream [`slicer-critic`](slicer-critic.md) verifies the application of all three methodology checks plus INVEST per its 10-criterion rubric.

## Deferred-item capture

When a decomposition explicitly defers an item to a future PRD (e.g., "Item X deferred per §3"), the slicer MUST create a `captured`-labeled GitHub Issue capturing the item, the PRD context where it surfaced, and optionally a link to a motivating ADR section, then immediately invoke `/promote-to-backlog <N>` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 inline-firing. Avoid double-write: if the deferred item is already recorded in an ADR Future-direction section, the captured issue may simply link back rather than duplicate the rationale. Per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2 (originating from [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4).

## Output format

See [[topics/output-shapes]] for the canonical GENERATOR trailer schema. The slicer's body shape (decomposition block) is domain-specific per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — only the trailer is canonical:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence>
ARTIFACTS: <N=3 alternative decompositions presented above>
DECOMPOSITION_COUNT: 3
```

`DECOMPOSITION_COUNT` is the per-agent extension naming the count of alternatives produced (`3` on SUCCESS default; `1` on N=1 degenerate carveout per ADR-0013; absent or `0` on INVALID_INPUT / STOPPED). The body precedes the trailer; the body is the per-decomposition slice tables + INVEST detail + the cross-decomposition summary table whose "Cascade-docs identified" / "Cascade-docs covered by slice(s)" rows are how the cascade-doc check surfaces to the critic.

## Relationship to other agents

- **Sequential partner to** [`slicer-critic`](slicer-critic.md). The slicer generates; the critic scores best-of-N + runs single revision. The pair together fills stages 3.5 + 3.6 of `/ship`.
- **Upstream consumer of** the PRD posted by `/to-prd` (via [`prd-critic`](../../../.claude/agents/prd-critic.md) APPROVE). The PRD's §2 success criteria define what the slices must cover in aggregate; §3 non-goals and §6 rabbit-holes bound what no slice may chase; §4 appetite caps slice count and per-slice LoC.
- **Downstream producer for** the [`implementer`](../../../.claude/agents/implementer.md) subagent, which consumes the posted slice issues (one per element of the slicer-critic-approved decomposition) and opens PRs against them.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7. `slicer` is a generator, not a critic — its adversarial gate is `slicer-critic`.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3 (N=3 default, single revision loop), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2+D3 (methodology overview, cascade-doc check), [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) (N=1 degenerate carveout).

## Edges

- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/hamburger-method]]
- **related_to:** [[concepts/glossary/spidr]]
- **related_to:** [[concepts/glossary/invest]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/slice]]
- **related_to:** [[patterns/cascade-doc-check]]
- **related_to:** [[patterns/n1-degenerate-carveout]]
- **related_to:** [[patterns/walking-skeleton]]
