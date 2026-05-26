---
title: Knowledge architecture — the project's KB v2 design
summary: Synthesis of the project's AI-native knowledge base — Karpathy compiler pattern + Zettelkasten atomic notes + SKOS typed edges, with a 9-PRD migration roadmap.
tags: [knowledge-architecture, kb, drift-detection, second-brain]
type: topic
last_updated: 2026-05-26
sources:
  - decisions/0031-knowledge-architecture-v2.md
  - decisions/0026-knowledge-architecture-truth-docs.md
  - decisions/0017-audit-meta-consolidation.md
  - decisions/0018-boy-scout-reviewer-rule.md
---

# Knowledge architecture

The synthesis page for this project's KB design as of 2026-05-26. Authoritative spec lives in [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md); this page is the readable narrative + migration roadmap. Satisfies R-TRUTH-DOC per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D5 (preserved by ADR-0031 D16) — required by the slice 1 contract since this PR ships `decisions/0031-knowledge-architecture-v2.md`.

**Edges**

- **defines:** [[../../../decisions/0031-knowledge-architecture-v2.md]] (the architectural lock; this synthesis is the readable companion)
- **related-to:** [[../patterns/walking-skeleton.md]] (slice-1 dogfood pattern; the proof-of-concept this PR ships)
- **supersedes:** [[../../../decisions/0026-knowledge-architecture-truth-docs.md]] (D1+D3 superseded per ADR-0031 D16; D2+D5+D6 preserved)
- **part-of:** [[../../../CLAUDE.md]] (KB schema pointer added in slice 1; full reorganization deferred to T6)
- **references:** [[kb-schema.md]] (the operating manual; this synthesis assumes the schema is in scope)

## Why this architecture

Three converging pains drove the redesign:

1. **Chronic drift across storage surfaces.** Concrete recent case: `.claude/skills/grill-me/SKILL.md:25` referenced `GLOSSARY.md`, a file deleted by [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) on ~2026-05-16. The drift sat undetected ~10 days. The `/audit-meta` skill's `DOCS-6` check catches this exact pattern, but it is manual+advisory; the `R-BOY-SCOUT` reviewer rule per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md) only scans files in a PR diff, missing the systemic case where unrelated PRs leave stale references behind.
2. **Context bloat.** CLAUDE.md auto-loads ~700 LoC into every session; 13 skills × ~150 LoC + 10 subagents × ~250 LoC inline content that is only partly needed for any given turn. Main-agent context fills with rarely-used content.
3. **Information scatter.** Same facts inlined in CLAUDE.md + skill bodies + subagent bodies + ADRs; no canonical home per concept; new contributors search across many files.

[ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D7 + [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md) D7 explicitly deferred the "cadence" half of [#47](https://github.com/vojtech-stas/project-claude/issues/47) — exactly the gap that left the GLOSSARY.md drift undetected. The 2026-05-26 user grill mandate was: solve the root cause, not the symptom.

## The three foundations

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) Context, the architecture is a principled hybrid of three validated patterns:

### Karpathy's LLM Wiki (April 2026)

Andrej Karpathy publicly described a personal-second-brain pattern of `/raw` (immutable source material — transcripts, scrapes, papers) + `/wiki` (LLM-compiled synthesis on top) + `agents.md` (operating system / cross-cutting rules). Validated by Karpathy at ~100 articles and ~400K words without any RAG infrastructure — the markdown wiki IS the queryable substrate. The project adopts this directly per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D1: `docs/raw/` ships in slice 1 (may start empty), `docs/current/` extends to host the compiled wiki, `CLAUDE.md` is the agents.md equivalent.

### Zettelkasten (Niklas Luhmann, 1960s-onward)

The atomic-notes practice: each note holds ONE idea, with explicit links to other notes forming the conceptual graph. 60+ years of academic validation; widely used in personal knowledge management. The project adopts atomic-notes sizing (50-300 LoC per note per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D4) and the explicit-linking discipline.

### SKOS / RDF typed edges (W3C)

Semantic-graph standards define edge types like `rdfs:isDefinedBy`, `rdfs:seeAlso`, `skos:related`, `skos:broader`/`narrower`, `dcterms:isReplacedBy`. The project adopts the typed-edge concept (rather than untyped Markdown links) per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D3: 13 edge types total, with 3 drift-critical edges (`defines`, `references`, `supersedes`) derived from SKOS/RDF/ADR convention + 10 adopted from the "Infinite Brain" YouTube taxonomy.

## The five node types and thirteen edge types

Briefly (full operating manual in [kb-schema.md](kb-schema.md)):

- **5 node types:** `concept` (atomic ideas, ~50-100 LoC) / `entity` (named artifacts, ~150 LoC) / `topic` (synthesis pages, ~200-400 LoC) / `pattern` (reusable techniques, ~50-100 LoC) / `decision` (alias to existing `decisions/NNNN-*.md` ADRs).
- **13 edge types:** 3 drift-critical (`defines`, `references`, `supersedes`) + 10 from the "Infinite Brain" pattern (`depends-on`, `part-of`, `supports`, `contradicts`, `derived-from`, `related-to`, `preceded-by`, `followed-by`, `authored`, `tagged`).

Five node types chosen over a tighter 3 (concept/entity/topic) for richer expressiveness; over the YouTube pattern's 16 because 16 types are life-management taxonomy, not software-project. Thirteen edge types chosen over a tighter 5 (defines/references/supersedes/depends-on/part-of) per user direction; pruning unused edges is a future PRD if observed after 6 months.

## The current-state-reader subagent extension

Per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D3, the `current-state-reader` subagent reads `docs/current/<topic>.md` for the 4 existing flat truth-docs. [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 extends it (additive, backward-compatible):

- **Path-based dispatch:** caller passes `type=<concept|entity|topic|pattern>` + `name=<id>`; reader resolves `docs/current/<type>s/<name>.md`.
- **Edge resolution:** returned synthesis includes an `Edges:` section listing each `[[path]]` link with a 1-sentence summary read from the target's `summary:` frontmatter field.
- **Backward compat:** the 4 existing flat truth-docs (`qa-automation`, `subagents`, `hooks`, `bootstrap`) remain readable as `type=topic` — they retain their `docs/current/<topic>.md` paths until T1-T4 migrate them.
- **Tool boundaries unchanged:** Read, Glob, Grep only.

LoC growth is ~30 lines additive; well under the 300-LoC reviewer R-LOC cap.

## Bootstrap-mode and forward-binding

Per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2 and [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D13, the new KB structure binds **forward** from this PR's merge:

- Future content (new ADRs, new subagents, new concepts) is born into the new architecture.
- Existing content migrates over a sequence of follow-up PRDs (T1-T9 below).
- The 4 existing flat truth-docs continue working under `current-state-reader` backward-compat; migration to atomic-notes-where-appropriate happens in T1-T4 alongside their respective subagent/skill migrations.
- No retroactive sweep; no big-bang rewrite.

## The 6-critic-cap is honored

Per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7, the project caps at 6 critics (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`). All new agents introduced by PRD #242 and follow-ups are GENERATORS, not critics (per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D14):

- `kb-maintainer` (T8) — generator (compiles wiki; no adversarial verdict).
- `impact-analyst` (T7) — generator (returns ref-graph; no adversarial verdict).
- `knowledge-gateway` (T9) — generator (answers NL queries; no adversarial verdict).

Future contemplations of a `kb-critic` (e.g., atomic-note quality auditor) must justify per the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 meta-rule why an existing critic cannot absorb the concern.

## T1-T9 migration roadmap

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10, the migration sequences over 9 follow-up PRDs (~2-4 weeks of focused work). Each PRD is bounded to ONE content category; walking-skeleton honored per-PRD:

- **T1 — Glossary migration.** 25 CLAUDE.md glossary terms split into atomic `concept` notes under `concepts/glossary/<term>.md`. CLAUDE.md glossary section thinned to an index.
- **T2 — Reviewer migration + hooks topic synthesis.** Largest subagent first (biggest payoff). Reviewer body thinned; rubric rules extracted as `concept` notes; hooks topic synthesis added.
- **T3 — Slicer / slicer-critic migration + pipeline topic synthesis.** Mid-sized subagents; pipeline topic synthesis added.
- **T4 — Remaining 8 subagents migration in parallel batches.** All `.claude/agents/*.md` thinned to entity-shell form.
- **T5 — All 13 skills migration in parallel batches.** All `.claude/skills/*/SKILL.md` thinned.
- **T6 — CLAUDE.md final slim.** After all content has a KB home, CLAUDE.md slims to ~150 LoC: 13 cross-cutting rules + hierarchy + workflow improvements + Map index + Glossary index + KB-schema pointer. Heavy sections move to `docs/current/topics/git-workflow.md`, `topics/slicing.md`, `topics/output-shapes.md`, `topics/pipeline-stages.md`.
- **T7 — impact-analyst.** Generator subagent invoked by slicer-critic + reviewer; queries the KB edge graph for `references` + `defines` cascade analysis. Closes original PRD-S concern; closes the ADR-0017 D7 + ADR-0018 D7 cadence question for per-PR drift.
- **T8 — kb-maintainer.** Generator subagent realizing the Karpathy LLM-as-compiler insight; reads `/raw`, generates `/current` entries, sweeps edges. Closes the cadence question for periodic drift.
- **T9 — knowledge-gateway.** Generator subagent providing NL Q&A on top of KB + composed web search. Closes captured #221.

## Open questions deferred

Twelve open questions are deferred per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) "Open questions deferred", to be resolved in the relevant follow-up PRD (T1-T9). Notable: OQ-7 (decision-node treatment — currently aliased to `decisions/` rather than a separate `docs/current/decisions/`), OQ-8 (entity-note shape vs entity-file shape — slice-1 implementer chose to keep both, with the entity note as synthesis and the source file as executable shell), OQ-9 (`README.md` workflow-diagram update — deferred to T6 alongside CLAUDE.md major slim).

## Cross-references

- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — primary spec; all decisions D1-D17.
- [kb-schema.md](kb-schema.md) — the operating manual; node types, edge types, frontmatter schema, linking convention.
- [walking-skeleton pattern](../patterns/walking-skeleton.md) — slice-1 dogfood pattern note.
- [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) — superseded D1+D3, preserved D2+D5+D6 per ADR-0031 D16.
- [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D7 + [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md) D7 — cadence question partially answered per ADR-0031 D17.
- captured [#47](https://github.com/vojtech-stas/project-claude/issues/47) — drift detection cadence; T7+T8 close.
- captured [#221](https://github.com/vojtech-stas/project-claude/issues/221) — knowledge-gateway; T9 absorbs.
- Karpathy LLM Wiki (April 2026): https://github.com/NicholasSpisak/second-brain
- Zettelkasten (Luhmann): https://zettelkasten.de/introduction/
- W3C SKOS: https://www.w3.org/2004/02/skos/

## Walking-skeleton dogfood — what slice 1 actually proves

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D15 + this PR's body, slice 1 cuts every architectural layer end-to-end. This serves three purposes:

1. **Integration risk surfaces now.** If the path-dispatch contract in `current-state-reader` mismatches the directory structure in `docs/current/`, or if the frontmatter schema in `kb-schema.md` is wrong for the consumer (`current-state-reader` edge resolution reading `summary:`), slice 1 reveals it. Subsequent migration PRDs T1-T9 then iterate on the weakest stage rather than discovering the mismatch at T6.
2. **The schema is enforced by working example.** `walking-skeleton.md` is itself a `pattern` node with the required frontmatter + ≥2 typed edges + body in the 50-300 range. `knowledge-architecture.md` (this file) is itself a `topic` node with the required frontmatter + ≥3 typed edges + body in the 200-400 range. `kb-schema.md` is itself a `topic` node documenting the schema it conforms to. The schema is not theoretical — three live exemplars exist at merge.
3. **The edge-resolution check runs at PR time.** The PR body's Dogfood section grep-extracts every `[[path]]` link in `walking-skeleton.md` and reports each `test -f` result. Unresolved edges are visible (not blocking — per ADR-0031 D6 edges may point to future content). This proves the link-resolution machinery is wired even though most targets are forthcoming in T1-T9.

## How drift detection works in v2

Pre-v2 (the world ADR-0026 left us in): drift detection is reactive. Either `/audit-meta DOCS-6` is invoked manually, or `R-BOY-SCOUT` (per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md)) catches drift in files that happen to appear in a PR's diff. Systemic drift in untouched files goes undetected indefinitely.

Post-v2 (after T7 + T8 land): drift detection is constitutional. Every concept has one canonical `defines` edge target. Every reference is a typed `references` edge pointing at that target. To find all references to a concept, `impact-analyst` (T7) queries the edge graph. To detect broken references (target renamed or deleted), `kb-maintainer` (T8) sweeps periodically. Neither agent is a critic; both are generators per the 6-critic-cap honored by [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D14.

The reactive layers stay useful for non-KB drift (CLAUDE.md typos, ADR text issues, etc.). `R-BOY-SCOUT` is preserved per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md); `/audit-meta` is preserved per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md). The KB-edge mechanism is additive defense-in-depth.

## Why the markdown wiki beats vector DB / RAG at this scale

Karpathy is explicit in his April 2026 LLM Wiki framing: at <100K-token corpus scale, a flat markdown wiki is more transparent + auditable + vendor-free + cheaper than vector-DB / RAG infrastructure. The project's KB target after T1-T9 is ~50-100 atomic notes × ~50-300 LoC = ~25K-100K total tokens, well within the cutoff. RAG would add infrastructure dependency, opaque retrieval, version-pinning complexity, and embedding-staleness risk for no marginal benefit at this scale. Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) Alt-E rejected.

If the corpus later exceeds ~100K tokens (multi-year project growth), the markdown substrate remains portable — adding a vector layer ON TOP of the canonical markdown is straightforward; the converse (rebuilding from vector embeddings to markdown) is not. Forward-compatibility is preserved by construction.

## Why typed edges beat untyped markdown links

Untyped markdown links (`[walking-skeleton](walking-skeleton.md)`) tell you A points to B but not *why*. The typed-edge convention (`**references:** [[walking-skeleton]]`) carries the semantic relation, enabling:

- **Differential queries.** "Find all `defines` edges to `yagni`" returns exactly one canonical home. "Find all `references` edges to `yagni`" returns every place the concept is cited. These are different drift-detection questions answered by the same edge graph.
- **Reciprocal traversal.** `supersedes` traversed in reverse is `superseded-by`; `part-of` traversed in reverse is `has-part`. `impact-analyst` (T7) can answer "what depends on this ADR?" by reverse-traversing `references`.
- **Conflict detection.** `contradicts` edges explicitly mark disagreement; `supports` edges mark agreement. Future tooling can flag inconsistent edges at PR time.

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) Alt-N rejected: dropping the 3 drift-critical edges (keeping only the 10 YouTube edges) would defeat the original drift-detection goal.

## Relationship to existing project patterns

The KB v2 architecture composes with existing project patterns rather than replacing them. Specifically:

- **ADRs remain the decision substrate.** ADRs at `decisions/NNNN-*.md` are the `decision` node type in the KB graph; ADR immutability per `decisions/README.md` is preserved. No ADR was edited to ship slice 1; `ADR-0026` D1+D3 are SUPERSEDED by new ADR `ADR-0031` per the convention, not edited.
- **Subagents remain the execution substrate.** No subagent gains write-access to `docs/current/` in slice 1; `current-state-reader` stays read-only. Future `kb-maintainer` (T8) will write KB content but operates as a generator, not a critic — preserving the 6-critic-cap.
- **The reviewer remains the sole PR gate.** `R-TRUTH-DOC` (per [ADR-0026](../../../decisions/0026-knowledge-architecture-truth-docs.md) D5, preserved per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D16) generalizes from "PR touching `decisions/` must also touch `docs/current/<topic>.md`" to "...must also touch SOME `docs/current/` content (concept, entity, topic synthesis, pattern, or — for the existing 4 flat truth-docs — backward-compat path)". This PR satisfies the rule by touching `decisions/0031-knowledge-architecture-v2.md` AND `docs/current/topics/knowledge-architecture.md`.
- **The walking-skeleton rule remains the slicing constraint.** Slice 1 cuts all layers per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D15. Subsequent migration PRDs (T1-T9) honor walking-skeleton per-PRD (each PRD's slice 1 cuts all KB-touching layers for that PRD's scope).
- **The 4 existing flat truth-docs are backward-compat.** `qa-automation.md`, `subagents.md`, `hooks.md`, `bootstrap.md` remain at `docs/current/<topic>.md` (NOT under `topics/`) until T1-T4 migrate them. `current-state-reader` reads BOTH the flat path AND the new `topics/<topic>.md` path; legacy invocations work unchanged.

## What slice 1 explicitly does NOT do

Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 + the slice 1 issue's "Notes for the implementer" section, this PR does NOT:

- Migrate any glossary term (deferred to T1).
- Thin any subagent body beyond the additive `current-state-reader` extension (deferred to T2-T4).
- Thin any skill body (deferred to T5).
- Reorganize CLAUDE.md beyond adding the new ~10-LoC KB-schema section (full slim deferred to T6).
- Ship the `kb-maintainer`, `impact-analyst`, or `knowledge-gateway` subagents (deferred to T8/T7/T9).
- Ship CI integration for KB validity checks (blocked on [#63](https://github.com/vojtech-stas/project-claude/issues/63)).
- Ship the `audit-meta` `DOCS-11`/`DOCS-12` KB-validity checks (deferred).
- Update the `R-BOY-SCOUT` reviewer rule for edge-resolution checks (deferred).
- Update `.claude/topics.json` (kb-schema topic addition deferred to T6 alongside CLAUDE.md slim).
- Update `README.md` workflow diagram mentioning the KB layer (OQ-9 — default deferred to T6; slice 1 implementer judgment chose to defer).

## What the merge of this PR unlocks

After slice 1 merges, downstream contributors can:

- Create new atomic notes at `docs/current/<type>/<id>.md` using the schema documented in `kb-schema.md`.
- Add new typed edges to existing notes using the `**EdgeType:** [[path]]` convention.
- Query the KB via `current-state-reader` with `type=<type>` + `name=<id>` parameters (returns synthesis + resolved edges).
- Read backward-compatibly: existing 4 flat truth-docs still work via `current-state-reader topic=<name>`.
- Reference the schema in their own PR bodies (e.g., "this atomic note covers the X concept per `kb-schema.md`").

After T1-T6 land, contributors will additionally see:

- CLAUDE.md slimmed to ~150 LoC (cross-cutting rules + hierarchy + workflow improvements + indices + KB-schema pointer); heavy detail in `docs/current/topics/`.
- Subagent bodies thinned to ~50-100 LoC each (frontmatter + role identity + mandatory reading order + tool boundaries + 1-sentence-summary-per-`[[path]]`-link references); detailed rubric/edge-case content in `docs/current/concepts/` and `entities/`.
- Skill bodies thinned to ~50 LoC each (frontmatter + trigger conditions + top-level procedure); examples/templates in `docs/current/`.
- Glossary terms split into atomic concept notes; CLAUDE.md glossary section becomes an index.

After T7-T9 land, contributors will see:

- `impact-analyst` invoked at slicer-critic + reviewer time, surfacing cascade impact ahead of merge.
- `kb-maintainer` periodically validating edge integrity + frontmatter completeness; auto-compiling new content from `docs/raw/`.
- `knowledge-gateway` answering NL queries on top of the KB, optionally composing web search.

## Provenance and audit trail

This synthesis was produced by the `implementer` subagent in slice 1 of PRD #242, derived from `decisions/0031-knowledge-architecture-v2.md` (joint-critic-approved: `prd-critic` APPROVE round 1 + `adr-critic` APPROVE round 2 per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1). The round-1 `adr-critic` BLOCK findings (D-ID misattribution + D3 edge-count mismatch + D5 frontmatter carveout) were all addressed in round 2 — verifying the joint-gate mechanism caught and corrected substantive issues before the architectural lock landed.

The synthesis intentionally repeats key narratives from ADR-0031 in readable prose rather than linking out to the ADR for every reader. The ADR is the canonical decision record (immutable); this topic is the readable wiki page (mutable per the standard truth-doc currency rule). Drift between this page and the ADR — should it occur — is caught by `R-TRUTH-DOC` at the next PR touching either file.

## References

- 2026-05-26 user grill task (drift containment + second-brain framing).
- All ADRs cited above; PRD #242 body.
- VentureBeat coverage of Karpathy's pattern: https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an
- DAIR.AI Academy summary: https://academy.dair.ai/blog/llm-knowledge-bases-karpathy
- "Infinite Brain" YouTube creator's pattern (transcript at `tool-results/transcripts/z02Y-1OvWSM-clean.txt`).
