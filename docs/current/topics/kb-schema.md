---
title: KB schema — node types, edge types, frontmatter, and linking convention
summary: Operating manual for the project's knowledge base — 5 node types, 13 edge types, YAML frontmatter schema, [[path]] link convention.
tags: [kb, schema, knowledge-architecture, operating-manual]
type: topic
last_updated: 2026-05-26
sources:
  - decisions/0031-knowledge-architecture-v2.md
  - decisions/0026-knowledge-architecture-truth-docs.md
---

# KB schema

The operating manual for `docs/current/` — the project's compiled, AI-native knowledge base. Authority: [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md). This file is itself an example of the schema it documents (it is a `topic` node with `summary` + `tags` + `sources` frontmatter and typed edges below).

**Audience.** Any agent or human authoring KB content. Agents reading content do not need this page — they query via `current-state-reader`.

**Edges**

- **defines:** [[../../../decisions/0031-knowledge-architecture-v2.md]]
- **part-of:** [[knowledge-architecture]]
- **references:** [[../../../decisions/0026-knowledge-architecture-truth-docs.md]]



## Node types

Five node types per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2. Each KB note picks exactly one. Choose by asking: "what *kind* of thing is this content about?"

### concept

An atomic idea — a glossary term, a rubric rule, a single named principle. Typical size: 50-100 LoC. Lives at `docs/current/concepts/<id>.md`. Examples (forthcoming in T1): `yagni`, `walking-skeleton-rule`, `closes-rule`. A `concept` note is the ONE canonical home of the idea — every other note that mentions the idea uses a `references` edge to it.

### entity

A named artifact in this project — a subagent, a skill, a hook, a tool. Typical size: ~150 LoC. Lives at `docs/current/entities/<id>.md`. Examples (forthcoming in T2-T4): `entities/reviewer.md`, `entities/slicer.md`, `entities/qa-tester.md`. An `entity` note synthesizes the artifact's role + tool boundaries + invocation contract; the artifact's own file (`.claude/agents/<name>.md` etc.) is the thin executable shell after migration.

### topic

A synthesis page that pulls multiple concepts/entities/decisions into a coherent picture. Typical size: 200-400 LoC; cap 500 (split into subdirectory if exceeded — future direction). Lives at `docs/current/topics/<id>.md`. Examples: this very file (`kb-schema.md`), `knowledge-architecture.md`, the existing flat `qa-automation.md` / `subagents.md` / `hooks.md` / `bootstrap.md` (backward-compat per ADR-0031 D6 — those four remain at `docs/current/<topic>.md` until T1-T4 migrate them into `topics/`).

### pattern

A reusable technique — a recipe for how to do a recurring kind of work. Typical size: 50-100 LoC. Lives at `docs/current/patterns/<id>.md`. Each pattern note covers What / Why / How / Anti-pattern / Examples-from-this-project. Examples: `patterns/walking-skeleton.md` (shipped in slice 1), forthcoming `cascade-doc-check`, `slice-grabbing`, `forward-block`.

### decision

An ADR. ALIAS to the existing `decisions/NNNN-*.md` tree per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 — **NOT a separate `docs/current/decisions/` directory**. ADRs ARE the decision node type; the query layer (`current-state-reader`) path-dispatches `decisions/*.md` when asked for a decision. Decision nodes are EXEMPT from the YAML frontmatter schema below per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D5 (they retain Status / Date / Supersedes / Extends headers per `decisions/README.md` *"What an ADR is"*).



## Edge types

Thirteen edge types per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D3 — 3 drift-critical edges (from RDF/SKOS/ADR convention) + 10 from the "Infinite Brain" YouTube pattern. Edges are expressed inside note bodies as `**EdgeType:** [[path/relative/to/docs-current-or-repo-root]]`. Use kebab-case (or snake_case — current-state-reader matches both — but prefer kebab in new content).

**Drift-critical edges:**

- **defines** — this note IS the canonical definition of the named concept (one outgoing `defines` edge per concept node). Mirrors RDF `rdfs:isDefinedBy`.
- **references** — this note cites or uses a concept defined elsewhere. Mirrors RDF `rdfs:seeAlso` / SKOS `skos:related`. The drift-detection workhorse.
- **supersedes** — this note replaces an older one (which gains a reciprocal `superseded-by` traversed in reverse, NOT a separate edge type). Mirrors this project's ADR supersession convention + W3C `dcterms:isReplacedBy`.

**Adopted from the "Infinite Brain" pattern:**

- **depends-on** — logical or functional dependency on the target.
- **part-of** — composition relation (reciprocal `has-part` in reverse traversal). Aligns with SKOS `skos:broader` / `skos:narrower`.
- **supports** — argumentative support for the target's claim.
- **contradicts** — argumentative opposition to the target's claim.
- **derived-from** — inspiration or source from which this note was synthesized.
- **related-to** — general association without a more specific edge type fitting. Aligns with SKOS `skos:related`.
- **preceded-by** — temporal predecessor (distinct edge type, NOT a reciprocal of `followed-by`).
- **followed-by** — temporal successor (distinct edge type, NOT a reciprocal of `preceded-by`).
- **authored** — provenance edge naming who/what produced this note.
- **tagged** — via YAML `tags:` frontmatter rather than a body edge; rare as explicit body edge.

Counting: each bullet above is one edge type; reciprocals (`superseded-by`, `has-part`) are the SAME edge traversed in the reverse direction by `impact-analyst` (future, T7), NOT separate edge types. Total = 13.



## YAML frontmatter schema

Every KB note under `docs/current/` (concept / entity / topic / pattern — but NOT `decision` per the carveout above) MUST open with YAML frontmatter delimited by `---` lines:

```yaml

title: <H1-equivalent string>
summary: <1-sentence string>
tags: [<list of kebab-case strings>]
type: <concept|entity|topic|pattern>
last_updated: <YYYY-MM-DD>
sources:
  - <path-or-URL>

```

**Required fields:** `title`, `type`, `last_updated`.

**Recommended fields:** `summary` (consumed by `current-state-reader` edge-resolution per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 — a missing `summary` degrades but does not break edge resolution), `tags` (kebab-case strings), `sources` (paths or URLs the note synthesizes from).

**Enum for `type`:** `concept`, `entity`, `topic`, `pattern`. The `decision` enum value is intentionally absent — decision nodes are path-dispatched from `decisions/*.md` rather than carrying frontmatter, per the carveout above and [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D5 trailing paragraph.

Future `audit-meta` extension `DOCS-11` will mechanically validate this schema (deferred per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) Future direction).



## Linking convention

Links between KB notes use double-bracket syntax: `[[path/relative/to/docs-current/]]`. Examples:

- From `docs/current/patterns/walking-skeleton.md` linking to a concept: `[[concepts/glossary/yagni]]` (resolves to `docs/current/concepts/glossary/yagni.md` when that file exists; edges may point to future content per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — the link-resolution check reports unresolved targets but does not block slice-1).
- From a topic synthesis linking to an ADR (decision node): `[[../../../decisions/0031-knowledge-architecture-v2.md]]` (paths to outside `docs/current/` are written as ordinary relative Markdown paths inside the `[[...]]` brackets).
- Edge syntax in note body: `- **references:** [[../../../decisions/0026-knowledge-architecture-truth-docs.md]]` — one edge per bullet, edge name + colon + space + bracketed path.

The `current-state-reader` parses `[[path]]` patterns and resolves each link's `summary:` frontmatter for display (per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 edge-resolution). When the target is a `decision` node (ADR), the reader returns the ADR's title line rather than a frontmatter `summary` (decision nodes lack frontmatter per carveout).



## Node-type selection guidance

When authoring a new KB note, pick the node type by asking: "what kind of thing is this content about?"

- A single named idea or term → **concept**.
- A specific named artifact in this project → **entity**.
- A coherent synthesis pulling multiple ideas/artifacts/decisions together → **topic**.
- A reusable how-to recipe → **pattern**.
- A design decision with trade-offs → **decision** (write an ADR; do NOT create a `docs/current/` file for it).

When ambiguous (e.g., is `walking-skeleton` a `concept` or `pattern`?), prefer the more specific type. Walking-skeleton is a `pattern` because it is actionable how-to with anti-pattern + examples; the `concept` glossary entry (forthcoming in T1) will `defines` the term and `references` the pattern note.



## Migration guidance (T1-T6)

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10, existing inlined content migrates into atomic notes over a sequence of follow-up PRDs:

- **T1** — Glossary migration (25 terms → atomic concept notes under `concepts/glossary/`).
- **T2** — Reviewer migration (largest subagent body → entity note + extracted rubric concepts).
- **T3** — Slicer / slicer-critic migration (pipeline topic synthesis page).
- **T4** — Remaining 8 subagents migration.
- **T5** — All 13 skills migration.
- **T6** — CLAUDE.md final slim (after content migrated; expected ~150 LoC end state).

During T1-T6 the codebase coexists in two modes: pre-migration content stays inlined in skill/subagent bodies, post-migration content lives as atomic notes with thin shell artifacts referencing them via `[[path]]` links + 1-sentence inline summaries (the anti-cryptic-body mitigation per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) Consequences).



## References

- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — D1 (compiler pattern), D2 (5 node types), D3 (13 edge types), D5 (frontmatter schema + decision-node carveout), D6 (current-state-reader extension), D10 (T1-T9 migration sequencing), D11 (CLAUDE.md slim targets), D12 (skill/subagent thinning targets).
- [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) — D2/D5/D6 preserved (R-TRUTH-DOC + truth-doc currency rule), D1/D3 superseded by ADR-0031.
- W3C SKOS: https://www.w3.org/2004/02/skos/
- Zettelkasten (Luhmann): https://zettelkasten.de/introduction/
- Karpathy LLM Wiki (April 2026): https://github.com/NicholasSpisak/second-brain
