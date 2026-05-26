---
title: current-state-reader — per-topic truth-doc reader subagent
summary: Generator subagent that takes a `<topic>` string (or KB-v2 `type=<X> name=<id>` pair), opens the resolved truth-doc / KB node, distills ≤15 lines of synthesis, resolves typed edges (KB-v2 only), and returns the canonical GENERATOR trailer with `TOPIC` + `SOURCES_READ` per-agent extensions — keeps main-agent context slim by collapsing chain-walking into a single thin read.
tags: [subagent, generator, reader, knowledge-architecture, current-state-reader]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/agents/current-state-reader.md
  - decisions/0026-knowledge-architecture-truth-docs.md
  - decisions/0031-knowledge-architecture-v2.md
  - decisions/0005-output-shape-and-slicing-methodology.md
---

# current-state-reader

The `current-state-reader` subagent is the **per-topic truth-doc reader** of the knowledge architecture. Given one input parameter — a legacy `<topic>` slug OR a KB-v2 `type=<X> name=<id>` pair — it opens the resolved truth-doc / KB node, distills the active synthesis into a ≤15-line response, resolves typed edges for KB-v2 nodes, and emits the canonical GENERATOR trailer with `TOPIC` + `SOURCES_READ` per-agent extensions. It is the 4th generator subagent (alongside `slicer`, `implementer`, `qa-tester`), keeping the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap at 6.

This entity note is the **canonical full role synthesis** for the current-state-reader subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 9), the operational [`.claude/agents/current-state-reader.md`](../../../.claude/agents/current-state-reader.md) carries the prompt-level operational mechanics (input contract, process steps, tool boundaries, adversarial mindset, bootstrap acknowledgment) and links here for the full role synthesis. The body is already at 118 LoC under the 120 cap, so slice 9 is structural alignment only (entity note creation + backlink) — no behavioral change per the slice's "Out of scope" and PRD #283 §3.

## Role and responsibility

The current-state-reader has three jobs, in strict priority order:

1. **Validate the input shape** — accept either the legacy form (a kebab-case `<topic>` slug matching a filename under `docs/current/`) or the KB-v2 form (`type=<concept|entity|topic|pattern>` + `name=<id>`, both kebab-case `[a-z0-9-]+`), with decision-node queries (`type=decision name=<NNNN-slug>`) path-dispatching `decisions/NNNN-*.md` per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 alias.
2. **Resolve, read, and condense** — open the target file once, distill the synthesis to ≤15 lines (leading with the `summary:` frontmatter field or H1 + first paragraph for legacy / decision nodes), resolve typed edges for KB-v2 nodes per the [[topics/kb-schema]] `\*\*[a-z-]+:\*\* \[\[[^\]]+\]\]` pattern, and surface staleness or shape warnings as one-line `WARN:` lines without blocking.
3. **Return the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md)** with `TOPIC` + `SOURCES_READ` per-agent extensions per [[topics/output-shapes]] + [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D3.

It does NOT post to GitHub, does NOT call any other subagent (no `Agent` tool per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D3), does NOT modify any file (no `Write`/`Edit`), does NOT fall back to reading source ADRs / skills inline when a truth-doc is missing (that defeats the pre-computed-slim-load premise of [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D1).

## Invocation contract

- **Caller:** the main agent — typically after the [UserPromptSubmit topic-nudge hook](../../../.claude/hooks/user-prompt-submit-topic-nudge.sh) (per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D4) injects an `additionalContext` instruction matching the prompt's keywords. May also be invoked directly via the `Agent` tool with `subagent_type: "current-state-reader"`.
- **Input:** ONE of (a) a legacy `<topic>` kebab-case slug, e.g., `qa-automation`; (b) a KB-v2 `type=<X> name=<id>` pair, e.g., `type=pattern name=walking-skeleton`; (c) a decision-node query, e.g., `type=decision name=0026-knowledge-architecture-truth-docs`. Path resolution per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6: legacy `<topic>` → `docs/current/<topic>.md` with `docs/current/topics/<topic>.md` fallback; KB-v2 → `docs/current/<type>s/<name>.md` (pluralized); decision → `decisions/<name>.md`. Both forms additive per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 backward-compat.
- **Output:** a ≤15-line synthesis (default-bullets keyed on load-bearing contract names per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) OQ-8) plus the canonical GENERATOR trailer with `TOPIC` echoing the input + `SOURCES_READ` integer (typically `1`, the truth-doc).
- **Tool boundaries** per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D3: `Read` (open the target file), `Glob` (confirm a file exists), `Grep` (pattern-extract for edge resolution). **NOT** authorized: `Agent` (honors no-nested-spawn per `/best-practice-subagents` Rule 6), `Write`/`Edit` (truth-doc upkeep is the implementer + reviewer's job via [R-TRUTH-DOC](../../concepts/rules/r-truth-doc.md)), `Bash` (not in the granted tool set), `AskUserQuestion` (not available to subagents per Claude Code architecture).

## 5-node-type dispatch and edge resolution (the ADR-0031 D6 extension)

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6, the reader was extended in PRD-T slice 1 to handle the KB-v2 typed-node schema additively (legacy form remains backward-compatible). The 5 node types and their path-dispatch:

- **`concept`** → `docs/current/concepts/<name>.md` (small atomic definitions; rule notes under `concepts/rules/`, glossary terms under `concepts/glossary/`)
- **`entity`** → `docs/current/entities/<name>.md` (subagent / skill / hook role syntheses; this file is one of them)
- **`topic`** → `docs/current/topics/<name>.md` (cross-cutting synthesis pages)
- **`pattern`** → `docs/current/patterns/<name>.md` (reusable methodology notes)
- **`decision`** → `decisions/<name>.md` (ADR files; no separate `docs/current/decisions/` per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 alias)

For KB-v2 nodes (NOT legacy truth-docs, NOT decision nodes — decision nodes are read without edge resolution per the D5 frontmatter-carveout), the reader runs the typed-edge resolution step: `Grep` the body for `\*\*[a-z-]+:\*\* \[\[[^\]]+\]\]` matches per [[topics/kb-schema]], open each link target once, read its `summary:` frontmatter (or H1 for decision-node link targets), and append an `## Edges` section to the synthesis with one bullet per edge — `**<edge-type>:** [[<path>]] — <1-sentence summary>` or `— UNRESOLVED` when the target is missing. Unresolved targets are reported but do NOT BLOCK (edges may point to future content per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) forward-binding).

This extension is preserved verbatim per PRD #283 §3 non-goal + slice 9's "PRESERVE all 5-node-type + edge-resolution logic verbatim per ADR-0031 D6". Slice 9 is structural alignment + entity note only — no logic change.

## Failure return modes

- **`RESULT: SUCCESS`** — target file found, read, synthesized — even with a non-blocking shape `WARN:` line in the synthesis.
- **`RESULT: INVALID_INPUT`** + one-sentence `REASON:` — input neither matches legacy nor KB-v2 form; any provided string fails `[a-z0-9-]+`; `type` not in the enum; the target file does not exist (reason text: `"node '<input>' has no file at <resolved-path>; per ADR-0031 D13 bootstrap-mode, KB content backfills organically — capture a backlog item if blocking"`). Trailer-only — no synthesis.

A `RESULT: INVALID_INPUT` from a missing target is the **correct bootstrap-mode signal**, not a defect. Topic coverage backfills FORWARD per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D7 + [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D13 — un-truth-docced topics correctly return `INVALID_INPUT` and the caller captures a backlog item if the gap is blocking.

## Bootstrap-mode acknowledgment

Per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D7 + [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D13: from slice-1-merge of PRD #224 forward, the topic-nudge hook + reader pair is the canonical way to answer "what's the current state of X?" The KB-v2 extension (per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6) is additive — legacy `<topic>` reads remain backward-compatible during the T1-T4 migration window. Slice 9 of PRD #283 ships this entity note plus structural alignment; no behavioral change.

## Relationship to other agents

- **No adversarial critic.** As a generator that produces no tracked-artifact write and no GitHub-side mutation, the reader has no per-invocation gate. Quality of its output is bounded by the truth-doc / KB-node fidelity (the implementer + reviewer's [R-TRUTH-DOC](../../concepts/rules/r-truth-doc.md) responsibility per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D5) and the reader's own ≤15-line slim contract + fidelity discipline.
- **Sibling generators:** [`slicer`](slicer.md), [`implementer`](implementer.md), [`qa-tester`](qa-tester.md) — but the reader is the only generator with no tracked-artifact side effects.
- **Future sibling:** the `impact-analyst` subagent (T7 per [[topics/knowledge-architecture]], [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D8) will be the second read-only KB generator, querying the edge graph for `references` + `defines` cascade analysis. The current-state-reader is per-node read; impact-analyst is graph traversal — complementary, non-overlapping responsibilities. Honors the 6-critic-cap; both are generators, not critics.
- **Upstream consumer of** the truth-docs / KB nodes maintained per [R-TRUTH-DOC](../../concepts/rules/r-truth-doc.md) (per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D5). When the truth-doc layer is stale, the reader surfaces a `WARN:` line but still returns — partial freshness beats no answer.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — reader is the 4th generator, not a critic.
- **Authority:** [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D3 (original tool boundaries + generator role + trailer extensions; superseded by [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 only for the additive KB-v2 dispatch — the D3 legacy form remains active per the additive-not-replacement supersession shape), [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D4 (the topic-nudge hook that dispatches it), [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D7 (bootstrap-mode forward-only), [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 (decision-node alias), [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D5 (decision-node frontmatter carveout — skip edge-resolution), [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 (5-node-type dispatch + edge resolution extension), [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D13 (KB content backfills forward), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer schema).

## Edges

- **related_to:** [[entities/subagents/slicer]]
- **related_to:** [[entities/subagents/implementer]]
- **related_to:** [[entities/subagents/qa-tester]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[topics/kb-schema]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/generator-trailer]]
- **related_to:** [[concepts/rules/r-truth-doc]]
- **related_to:** [[patterns/walking-skeleton]]
