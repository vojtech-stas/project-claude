# ADR-0031: Knowledge architecture v2 — Karpathy compiler + atomic notes + typed edges + LLM-as-maintainer

- **Status:** Accepted
- **Date:** 2026-05-26
- **Supersedes:** [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1 (per-topic truth-doc pattern — extended from per-topic synthesis to atomic-notes-with-typed-edges KB per D1+D2 below); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D3 (current-state-reader contract — extended per D6 below to handle 5 node types + edge resolution; existing behavior preserved as backward-compat)
- **Extends:** [ADR-0017](0017-audit-meta-consolidation.md) D7 (deferred cadence question — partially answered per D17 below: cadence becomes kb-maintainer in T8 + impact-analyst in T7 + boy-scout for non-KB drift); [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 (sibling cadence answer per D17); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2 (mandatory implementer step + R-TRUTH-DOC introduction — preserved per D16; rule now applies to all `docs/current/` content); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D5 (R-TRUTH-DOC rule definition — preserved per D16); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D6 (CLAUDE.md cross-cutting rule #14 truth-doc currency — preserved per D16); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored per D14: all new agents are generators); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited per D13); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 (macro-ADR placement — ADR-0031 alongside PRD-T); [ADR-0001](0001-foundational-design.md) D6 (subagent pattern — extended with future kb-maintainer + impact-analyst + knowledge-gateway generators per D7/D8/D9); [decisions/README.md](README.md) *"What an ADR is"* (ADR immutability — preserved; no edits to prior ADRs).

## Context

PRD-T (this PRD) is the 18th major architectural decision in this project. The trigger: chronic drift across the project's many storage surfaces. Concrete recent instance: `.claude/skills/grill-me/SKILL.md:25` references `GLOSSARY.md`, a file deleted by [ADR-0012](0012-glossary-consolidation-single-tier.md) on ~2026-05-16 — drift sat undetected ~10 days. The `/audit-meta` skill's `DOCS-6` check would catch this drift exactly but is manual+advisory; the `R-BOY-SCOUT` rule ([ADR-0018](0018-boy-scout-reviewer-rule.md)) only scans diff'd files, missing the systemic case.

[ADR-0017](0017-audit-meta-consolidation.md) D7 + [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 explicitly deferred the "cadence" half of [#47](https://github.com/vojtech-stas/project-claude/issues/47) — pending CI per [#63](https://github.com/vojtech-stas/project-claude/issues/63) or alternative trigger. The user mandate 2026-05-26 declined "ship what's ready today" framing and asked for the architecturally correct answer regardless of today's substrate.

Beyond drift, the architecture has two related pains:
1. **Context bloat**: CLAUDE.md ~700 LoC auto-loads every session; 13 skills × ~150 LoC + 10 subagents × ~250 LoC consume significant context budget on inlined-but-rarely-used content
2. **Information scatter**: same facts inlined in CLAUDE.md + skill bodies + subagent bodies + ADRs; no canonical home per concept; new contributors must search across many files

Research (2026-05-26 grill, sources in PRD-T body §References):
- **Karpathy's LLM Wiki** (April 2026): LLM-as-compiler pattern with `/raw` (immutable sources) + `/wiki` (compiled synthesis) + `agents.md` (operating system). Validated at ~100 articles + 400K words without RAG.
- **Zettelkasten** (Luhmann, 1960s+): atomic notes with explicit linking; 60+ years of academic validation.
- **SKOS / RDF** (W3C): typed semantic edges as standard for knowledge graphs.
- **"Infinite Brain" YouTube pattern** (one AI architect, 2026): 16 node types + 10 edges + AI-as-maintainer; pet system, partially validated, useful starting taxonomy but with credibility caveats called out in the grill.
- **ADR conventions** (Nygard 2011): supersession/extension headers — already this project's vocabulary.

The PRD-T grill synthesized these into a principled hybrid: adopt Karpathy's compiler pattern + Zettelkasten atomic notes + SKOS-style typed edges, with a minimum viable taxonomy curated for THIS project's needs (5 node types + 13 edge types — superset of the YouTube pattern's 10 edges, with 3 drift-critical edges added per principled extension from RDF + ADR convention).

This ADR captures the architectural lock. Migration is sequenced over PRDs T1-T9; this ADR's slice 1 dogfoods the pattern end-to-end on ONE topic (the `walking-skeleton` pattern node) as walking-skeleton proof.

## Decisions

### D1: Compiler pattern — `/raw` (sources) + `/current` (compiled wiki) + `CLAUDE.md` (operating system)

Per Karpathy's LLM Wiki:
- `docs/raw/` — immutable source material (transcripts, scrapes, etc.). Nothing edited after landing.
- `docs/current/` — LLM-compiled wiki. Atomic notes synthesized from raw + agent reasoning + project decisions. The KB queryable substrate.
- `CLAUDE.md` — the "agents.md equivalent": operating system + cross-cutting rules + KB index.

Slice 1 creates `docs/raw/` (may be empty initially; structure-only) and extends existing `docs/current/`.

### D2: Five node types — concept / entity / topic / pattern / decision

`docs/current/` subdirectories:
- `concepts/<id>.md` — atomic ideas (glossary terms, rubric rules; ~50 LoC each)
- `entities/<id>.md` — named artifacts (subagents, skills, hooks; ~150 LoC each)
- `topics/<id>.md` — synthesis pages (qa-automation, hooks, pipeline; ~200-400 LoC each)
- `patterns/<id>.md` — reusable techniques (walking-skeleton, cascade-doc-check; ~50-100 LoC each)
- `decision` — ALIAS to existing `decisions/` ADRs (NOT a separate `docs/current/decisions/` directory). ADRs ARE the decision node type; query mechanism path-dispatches `decisions/*.md` when asked for a decision.

5 types chosen over a tighter 3 (concept/entity/topic) per user grill direction; over the YouTube pattern's 16 because over-vocabulary (16 types is life-management taxonomy, not software-project).

### D3: Thirteen edge types = 3 drift-critical + 10 from the YouTube "Infinite Brain" pattern

Edges expressed as `**EdgeType:** [[path]]` convention within note bodies. Each row below names ONE edge type; some edge types have an explicit reciprocal (parenthesized) for use in the inverse direction — the reciprocal is the SAME edge type traversed backward, NOT a separate type. Total = 13 edge types (3 + 10).

**Three drift-critical edge types** (added per principled extension from RDF + SKOS + ADR convention; without these, edge-graph drift detection regresses to grep-only):

1. `defines` — this note IS the canonical definition of the concept (one outgoing per concept; from RDF `rdfs:isDefinedBy`)
2. `references` — this note cites/uses the concept (from RDF `rdfs:seeAlso` / SKOS `skos:related`)
3. `supersedes` (reciprocal: `superseded-by`) — replaces (matches this project's ADR convention + W3C `dcterms:isReplacedBy`)

**Ten edge types from the YouTube "Infinite Brain" pattern** (adopted as-is per user grill Q3b choice; same vocabulary the video creator names):

4. `depends-on` — logical dependency
5. `part-of` (reciprocal: `has-part`) — composition (also aligns with SKOS `skos:broader` / `skos:narrower`)
6. `supports` — argumentative support
7. `contradicts` — argumentative opposition
8. `derived-from` — inspiration/source
9. `related-to` — general association (also aligns with SKOS `skos:related`)
10. `preceded-by` — temporal predecessor
11. `followed-by` — temporal successor
12. `authored` — provenance (who/what made this)
13. `tagged` — via YAML frontmatter `tags:` field; rarely used as explicit edge in note body

Counting convention: each row above is ONE edge type; reciprocals (`superseded-by`, `has-part`) are the SAME edge traversed in the reverse direction (queryable in either direction by impact-analyst per T7), not separate edge types. Items 10 (`preceded-by`) and 11 (`followed-by`) are listed as SEPARATE edge types per the YouTube pattern's original taxonomy, NOT as a reciprocal pair (consistent with the video creator's enumeration of `preceded_by` and `followed_by` as distinct items).

13 chosen over a tighter 5 (defines/references/supersedes/depends-on/part-of) per user grill direction (full Infinite Brain + drift-critical extensions); the taxonomy is INTENTIONALLY broader than minimum-needed-today. Edge-type pruning of unused edges is a future PRD if observed unused after 6 months.

### D4: Atomic-notes size policy — 50-300 LoC per note

Per Zettelkasten + Infinite Brain practice. Concepts/patterns lean small (50-100 LoC); entities are medium (~150 LoC); topics are larger (200-400 LoC). Topics exceeding 500 LoC SHOULD split into a subdirectory (future direction). Walking-skeleton dogfood (the slice 1 pattern note) is the size baseline.

### D5: YAML frontmatter schema (required on every KB note)

```yaml
---
title: <H1-equivalent string>
summary: <1-sentence string>
tags: [<list of kebab-case strings>]
type: <concept|entity|topic|pattern>
last_updated: <YYYY-MM-DD>
sources:
  - <path-or-URL>
---
```

Required: `title`, `type`, `last_updated`. Recommended: `summary`, `tags`, `sources`. Schema enforced by future `audit-meta` extension (DOCS-11, deferred).

**Carveout for the `decision` node type** (per D2): ADRs at `decisions/NNNN-*.md` are EXEMPT from this frontmatter schema — they retain their existing ADR convention (Status / Date / Supersedes / Extends headers per `decisions/README.md` "What an ADR is"). The `type: decision` enum value is therefore NOT included in the `type` field above; `decision`-typed query results are tagged by the query layer (current-state-reader per D6) based on path dispatch (`decisions/*.md` → `type: decision` in returned summary), not by frontmatter. The frontmatter `type` enum is restricted to the 4 node types whose files live under `docs/current/` (`concept`, `entity`, `topic`, `pattern`).

### D6: current-state-reader extension (additive, backward-compatible)

Per [ADR-0026](0026-knowledge-architecture-truth-docs.md) D3, current-state-reader currently reads `docs/current/<topic>.md`. PRD-T extends:
- **Path-based dispatch**: caller passes `type=<concept|entity|topic|pattern>` + `name=<id>`; reader resolves `docs/current/<type>s/<name>.md`
- **Edge resolution**: returned summary includes a "Edges:" section listing each `[[path]]` link with 1-sentence summary (read from the target's `summary:` frontmatter field)
- **Backward compat**: existing 4 truth-docs (qa-automation, subagents, hooks, bootstrap) remain readable as `type=topic`
- **Tool boundaries unchanged**: Read, Glob, Grep (no Bash; no Agent; no Write/Edit — read-only per ADR-0026 D3)

Extension is ADDITIVE; no breaking change. Subagent body adjustment in slice 1 (~30 LoC growth; remains under R-LOC cap).

### D7: kb-maintainer agent DEFERRED to PRD-T8

The "LLM-as-compiler" insight (Karpathy) requires an agent that reads `/raw` + queries + maintains `/current`. Per user grill Q3c, this agent is NOT in PRD-T. PRD-T8 (future) ships it as a generator subagent.

Until T8: manual compilation (human/implementer authors atomic notes; implementer adds entries during ADR-impacting PRs per R-TRUTH-DOC).

### D8: impact-analyst agent DEFERRED to PRD-T7 (was PRD-S)

Per grill sequencing, impact-analyst's job (find references to a concept) becomes trivial once typed edges exist — just query the edge graph by `references` and `defines` edges. PRD-T7 ships impact-analyst as a generator subagent invoked by slicer-critic + reviewer (per original PRD-S design, simplified now that KB exists as substrate).

### D9: knowledge-gateway agent DEFERRED to PRD-T9 (folds #221)

[#221](https://github.com/vojtech-stas/project-claude/issues/221) captured the "knowledge-gateway" idea: one subagent that owns KB reads + can search internet + answers NL queries on top of KB. PRD-T9 ships it as the evolved current-state-reader. Closes #221.

### D10: Migration sequencing — 9-10 PRDs over T1-T9

Per user grill Q5 (accept proposal):
- **T1**: Glossary migration (25 terms → atomic concept notes; CLAUDE.md glossary section → index)
- **T2**: Reviewer migration + hooks topic synthesis (largest subagent — biggest payoff first)
- **T3**: Slicer/slicer-critic migration + pipeline topic synthesis
- **T4**: Remaining subagents (8 more) migration in parallel batches
- **T5**: All 13 skills migration in parallel batches
- **T6**: CLAUDE.md final slim (after all content migrated)
- **T7**: impact-analyst (was PRD-S; consumes KB edge graph)
- **T8**: kb-maintainer agent (LLM-as-compiler per Karpathy)
- **T9**: knowledge-gateway / closes #221

Each PRD bounded to ONE content category; walking-skeleton honored per-PRD; forward-block if PRD-Tn fails.

### D11: CLAUDE.md slim targets — ~150 LoC after T6

**Stays in CLAUDE.md after T6:**
- 13 cross-cutting rules
- Hierarchy (PRD→Slice→PR)
- Workflow improvements I1-I6 + meta-rule
- Map (one-line index per item; details in KB)
- Glossary INDEX (term → KB concept path; no full defs)
- KB-schema pointer

**Moves from CLAUDE.md to KB (in T6):**
- Operational git workflow → `docs/current/topics/git-workflow.md`
- Slicing logic detail → `docs/current/topics/slicing.md`
- Output-shape standard detail → `docs/current/topics/output-shapes.md`
- Pipeline operational logic detail → `docs/current/topics/pipeline-stages.md`
- Full glossary definitions → `docs/current/concepts/glossary/<term>.md`

CLAUDE.md slice 1 (this PRD) adds ONLY the new "KB schema" section (~10 LoC). Major slim is T6.

### D12: Skill/subagent body thinning targets

**Skills (T5)**: ~50 LoC each — frontmatter (name/description) + trigger conditions + top-level procedure stays; domain knowledge + detailed examples + templates move to KB.

**Subagents (T2-T4)**: ~50-100 LoC each — frontmatter (name/description/tools/model) + role identity + mandatory reading order + tool boundaries enumeration + conduct guidelines stays; rubric details + edge case handling + output-format details move to KB (referenced via `[[path]]` with 1-sentence inline summary per link to prevent cryptic-body risk per Consequences).

### D13: Bootstrap-mode acknowledgment (per ADR-0004 D2)

- KB structure (5 node types, 13 edges, frontmatter schema, /raw vs /current split) binds **forward** from PRD-T merge
- Migration of existing content: sequenced via T1-T6 (NOT retroactive sweep; each PRD bounded to one content category)
- Future content (new ADRs, new subagents, new concepts): born into new architecture from PRD-T merge forward
- After T6 merges, ALL skill/subagent bodies use the thin architecture
- Existing 4 truth-docs (qa-automation, subagents, hooks, bootstrap) continue working under current-state-reader backward-compat per D6; migration to atomic-notes-where-appropriate happens in T1-T4 alongside their respective subagent/skill migrations

### D14: 6-critic-cap honored (per ADR-0008 D7)

All new agents introduced by PRD-T and follow-ups are GENERATORS, not critics:
- **kb-maintainer** (T8) — generator (compiles wiki; no adversarial verdict)
- **impact-analyst** (T7) — generator (returns ref-graph; no adversarial verdict)
- **knowledge-gateway** (T9) — generator (answers queries; no adversarial verdict)

Critic count remains 6 (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`).

Future PRDs that contemplate a `kb-critic` (e.g., atomic-note quality auditor) must justify per ADR-0008 D7 meta-rule why an existing critic cannot absorb the concern. Likely answer: reviewer's R-BOY-SCOUT can absorb edge-resolution checks; glossary-critic can absorb concept-note quality checks.

### D15: Cascade-doc updates

- `decisions/0031-knowledge-architecture-v2.md` — this ADR (NEW; slice 1)
- `decisions/README.md` — ADR-0031 index row in numerical order (slice 1)
- `docs/current/topics/knowledge-architecture.md` — NEW topic synthesis page (slice 1; R-TRUTH-DOC satisfaction)
- `docs/current/topics/kb-schema.md` — NEW schema doc (slice 1)
- `docs/current/patterns/walking-skeleton.md` — NEW dogfood pattern note (slice 1)
- `CLAUDE.md` — new "KB schema" section ~10 LoC (slice 1); major slim deferred to T6
- `.claude/agents/current-state-reader.md` — additive extension for new structure (slice 1)
- `README.md` — workflow diagram MAY need update mentioning KB layer (slice 1 implementer judgment; otherwise deferred to T6)
- `.claude/topics.json` — NOT updated in slice 1 (existing topic entries still valid; kb-schema topic added in T6 alongside CLAUDE.md slim)

### D16: ADR-0026 supersession (D1 + D3) and preservation (D2 + D5 + D6)

- **[ADR-0026](0026-knowledge-architecture-truth-docs.md) D1** (per-topic materialized truth-doc at `docs/current/<topic>.md`) — SUPERSEDED by D1+D2 here. Truth-doc pattern EXTENDED: `docs/current/topics/<topic>.md` for synthesis pages; atomic content in `concepts/entities/patterns/`. The "topic" remains the synthesis-page concept; "truth-doc" remains a valid term in this project's vocabulary specifically for `topics/*.md` synthesis files.
- **[ADR-0026](0026-knowledge-architecture-truth-docs.md) D3** (`current-state-reader` subagent) — SUPERSEDED by D6 here (extended for new directory structure + node-type dispatch + edge resolution; existing behavior preserved as backward-compat for the 4 existing truth-docs).
- **[ADR-0026](0026-knowledge-architecture-truth-docs.md) D2** (mandatory implementer step + R-TRUTH-DOC introduction — the responsibility-side framing of the rule) — PRESERVED. The implementer step still applies: PRs touching `decisions/NNNN-*.md` must also touch the corresponding `docs/current/` content (concept, entity, topic synthesis, or pattern — any KB content, not just `<topic>.md` files).
- **[ADR-0026](0026-knowledge-architecture-truth-docs.md) D5** (R-TRUTH-DOC reviewer rule — the rule-side definition + grep-shaped BLOCK trigger) — PRESERVED. Rule's mechanical trigger generalizes: `git diff --stat origin/main..HEAD -- decisions/ docs/current/` shows ADR change without ANY corresponding `docs/current/` change → BLOCK. The `docs/current/` half now spans `concepts/entities/topics/patterns/`, not just `topics/`.
- **[ADR-0026](0026-knowledge-architecture-truth-docs.md) D6** (CLAUDE.md cross-cutting rule #14 — truth-doc currency) — PRESERVED. Rule wording works for the extended KB; "the corresponding `docs/current/<topic>.md`" reads naturally as "the corresponding `docs/current/` content" under the broadened scope.

### D17: ADR-0017 D7 + ADR-0018 D7 (cadence question) PARTIALLY answered

The "post-merge sweep" question from [#47](https://github.com/vojtech-stas/project-claude/issues/47) has TWO complementary answers after PRD-T's follow-ups land:
1. **kb-maintainer** (T8) periodically validates KB integrity (edges resolve; frontmatter complete; LLM-compiles new content from `/raw`)
2. **impact-analyst** (T7) at slicer-critic + reviewer time catches per-PR drift via edge graph queries

These COMPLEMENT (not replace) the boy-scout rule (still useful for non-KB drift; ADR-0018 preserved in scope). #47 is not yet fully closed by PRD-T alone; PRD-T7 + T8 close it together.

## Consequences

### Positive

- **Drift containment at root**: each fact has ONE canonical home (the `defines` edge target). Drift = mechanically detectable via grep on `references` edges; impact-analyst (T7) automates this.
- **Context economy at scale**: CLAUDE.md slim + thin skill/subagent bodies after T6 = ~4-8x main-agent context reduction.
- **AI-first structure**: atomic notes + typed edges + Karpathy compiler pattern is validated practice for LLM-native KBs.
- **Forward-compatibility**: vendor-free Markdown; can later expose via MCP (#221 / T9), Obsidian, or any tool without re-platforming.
- **Walking-skeleton honored**: slice 1 cuts ALL layers (structure + content + reader + cascade-docs + ADR + dogfood).
- **6-critic-cap preserved**: all new agents are generators (kb-maintainer, impact-analyst, knowledge-gateway).
- **Bootstrap-mode honored**: forward-binding; migration sequenced per PRD; no retroactive sweep.
- **`docs/current/` directory boundary** (per grill Q2): simplest mental model for KB membership; no tag/registry drift.
- **Edge-type vocabulary is principled superset** (10 from YouTube + 3 drift-critical from RDF/ADR convention): not blind adoption.

### Negative / Accepted

- **Multi-PRD migration**: 9-10 PRDs over 2-4 weeks of focused work. Mitigated by per-PRD bounded scope + walking-skeleton per PRD.
- **Subagent invocation latency**: thin subagents fetch KB content per turn; 30-150s added latency for content-heavy turns (post-T2-T4). Mitigated by batch-fetch in current-state-reader (multiple paths in one invocation) + inline "Quick reference" of top-3 facts per subagent body.
- **Cryptic agent body risk**: very thin bodies require following links to understand. Mitigated by mandatory 1-sentence inline summary per `[[path]]` link (so a reader sees the gist without traversing).
- **KB-self-drift**: atomic notes can have stale edges (pointing to renamed/deleted notes). Mitigated by R-BOY-SCOUT extension (edge resolution check, future) + kb-maintainer (T8) periodic sweeps + audit-meta DOCS-11 (KB-frontmatter validity, future).
- **Tooling gap (no Obsidian backlinks)**: humans/agents grep for backlinks. Mitigated by impact-analyst (T7) as the backlink resolver for agents; humans can `grep -rE '\[\[concepts/glossary/prd\]\]' docs/` directly.
- **Node-type ambiguity**: some content sits at type boundaries (is `walking-skeleton` a `concept` or `pattern`? per grill: pattern). Mitigated by implementer judgment per migration PRD + documented in PR body.
- **13-edge taxonomy may be more than needed**: some edges (`supports`, `contradicts`, `preceded-by`, `followed-by`, `authored`, `tagged`) may see little use in software-project context. Accepted; edge-type pruning is a future PRD if observed unused after 6 months.
- **No CI integration**: KB validity checks remain advisory until [#63](https://github.com/vojtech-stas/project-claude/issues/63) (CI) ships. Mitigated by reviewer R-BOY-SCOUT inline application + kb-maintainer agent.
- **Migration period coexistence**: during T1-T6, the codebase has BOTH inlined skill-body content AND atomic notes. Mitigated by R-TRUTH-DOC enforcement + bounded per-PRD scope (one content category at a time, no mixing).

## Alternatives considered

- **Alt-A: Stay with truth-docs only (ADR-0026 unchanged)**. Rejected per user mandate — doesn't solve drift at the root; doesn't address context bloat; doesn't realize the "second brain" vision the user articulated.
- **Alt-B: Build PRD-S impact-analyst first; defer KB redesign**. Rejected per grill Q3 user choice — building drift detection against today's inlined-content architecture is "skeleton for a corpse" if the architecture is going to change foundationally.
- **Alt-C: 16 node types + 10 edges (full YouTube Infinite Brain pattern)**. Rejected per grill Q3a — 16 types is over-vocabulary for ~50 project concepts; some types don't apply to software-project context (e.g., `contact`, `bookmark`, `meeting`).
- **Alt-D: 3 node types + 5 edges (minimum viable, my Q3a/b recommendation)**. Rejected per user direction — chose 5 + 13 for richer expressiveness; pruning is future PRD if observed unused.
- **Alt-E: Vector DB / RAG infrastructure**. Rejected per Karpathy explicit guidance at <100K token scale; markdown wiki is more transparent + auditable + vendor-free; we have ~50-100 atomic notes target, well within his cutoff.
- **Alt-F: External MCP server (start with #221 as foundation)**. Rejected as premature; #221 deferred to T9 after KB structure proven; MCP exposure can be added later without re-platforming.
- **Alt-G: Single big-bang migration (one PRD migrates everything)**. Rejected per walking-skeleton rule — too large; high risk; loses incremental verification.
- **Alt-H: Tag-based filtering (no directory boundary)**. Rejected per grill Q2 — YAML frontmatter `kb:` tags drift; ambiguity for untagged files; two failure modes (real drift + tag drift).
- **Alt-I: Explicit registry (index.json lists KB members)**. Rejected per grill Q2 — registry becomes its own drift surface; same problem as decisions/README.md staleness.
- **Alt-J: 2 node types (note / topic)**. Rejected per grill Q3a — loses concept-vs-entity distinction useful for drift detection (different query shapes per type).
- **Alt-K: Hierarchical decomposition from day one (3B in grill)**. Rejected per grill Q3 — over-engineering for 4 existing truth-docs; threshold-split (current 3A choice) is sufficient until topics exceed 500 LoC.
- **Alt-L: Big-bang ADR consolidation (multiple ADRs instead of single ADR-0031)**. Rejected — all decisions are about ONE architectural shift; splitting creates dependency chains that obscure design.
- **Alt-M: Build kb-maintainer in PRD-T (don't defer)**. Rejected per grill Q3c — too much PRD-T scope; better to learn maintenance patterns through manual operation in T1-T6 before automating.
- **Alt-N: Adopt strict YT pattern 10 edges only (no drift-critical extensions)**. Rejected — would defeat the original drift-detection goal that motivated PRD-T (no `defines`/`references` edges = no edge-graph drift detection).

## Open questions deferred

- **OQ-1**: kb-maintainer trigger mechanism (post-merge hook? on-demand? scheduled?) — T8 grills
- **OQ-2**: impact-analyst severity policy (BLOCK vs REC at reviewer time) — T7 grills
- **OQ-3**: knowledge-gateway NL query interface (chat-style? structured query? voice?) — T9 grills
- **OQ-4**: backlink storage (computed on-the-fly vs cached as frontmatter field) — T7 implementation detail
- **OQ-5**: CLAUDE.md final size achievability (~150 LoC target) — T6 verifies
- **OQ-6**: per-skill thinning template — T5 implementer judgment per skill
- **OQ-7**: ADR `decision` node type — D2 chose alias to `decisions/` (no separate `docs/current/decisions/`); revisit if pattern confuses
- **OQ-8**: entity notes vs entity files (e.g., `entities/reviewer.md` vs `.claude/agents/reviewer.md`) — slice 1 implementer judgment; default: entity note SYNTHESIZES the agent's role + edges; agent file is the THIN executable shell after T2-T4
- **OQ-9**: Obsidian vs grep-only — orthogonal; users may add Obsidian config without changing KB substrate
- **OQ-10**: edge-type pruning if observed unused after 6 months — future PRD
- **OQ-11**: KB content versioning beyond `last_updated` (git history sufficient? need explicit version fields?) — defer
- **OQ-12**: Multi-language note support (assume English-only for now per project history) — defer

## Future direction

- **T1-T9 migration program** (sequenced per D10): glossary → reviewer → slicer/critic → remaining subagents → skills → CLAUDE.md slim → impact-analyst → kb-maintainer → knowledge-gateway
- **kb-maintainer (T8)** — Karpathy's LLM-as-compiler insight realized; reads `/raw`, generates `/current` entries, maintains edges
- **impact-analyst (T7)** — closes PRD-S concern via KB edge graph; replaces R-BOY-SCOUT-EXPAND idea (which is no longer needed once edges exist)
- **knowledge-gateway (T9)** — closes [#221](https://github.com/vojtech-stas/project-claude/issues/221); NL Q&A on top of KB + web search composition
- **audit-meta DOCS-11** (KB-frontmatter-validity check) — future PRD
- **audit-meta DOCS-12** (KB-edge-resolution check) — future PRD; could move to R-BOY-SCOUT extension
- **Optional MCP server exposure** of `docs/current/` — future
- **Optional Obsidian configuration** for human browsing — future
- **Edge-type pruning** if observed unused after 6 months — future PRD per OQ-10

## References

- 2026-05-26 user grill task (drift containment + second-brain framing)
- captured [#221](https://github.com/vojtech-stas/project-claude/issues/221) — knowledge-gateway (T9 absorbs)
- captured [#47](https://github.com/vojtech-stas/project-claude/issues/47) — drift detection cadence (T7+T8 close)
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) — superseded D1+D3 per D16; D2+D5 preserved
- [ADR-0017](0017-audit-meta-consolidation.md) D7 — cadence question extended per D17
- [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 — sibling cadence answer per D17
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap honored per D14
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode cited per D13
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement
- [ADR-0001](0001-foundational-design.md) D6 — subagent pattern extended via D7/D8/D9 generators
- [decisions/README.md](README.md) "What an ADR is" — ADR immutability preserved
- Karpathy LLM Wiki (April 2026): https://github.com/NicholasSpisak/second-brain
- VentureBeat: https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an
- DAIR.AI Academy: https://academy.dair.ai/blog/llm-knowledge-bases-karpathy
- Codersera: https://codersera.com/blog/karpathy-llm-knowledge-base-second-brain/
- Intelligent Living: https://www.intelligentliving.co/karpathy-llm-wiki-markdown-knowledge-base/
- MindStudio (LLM Wiki vs RAG): https://www.mindstudio.ai/blog/llm-wiki-vs-rag-internal-codebase-memory
- "Infinite Brain" video (transcript): `tool-results/transcripts/z02Y-1OvWSM-clean.txt`
- W3C SKOS: https://www.w3.org/2004/02/skos/
- Zettelkasten (Luhmann methodology): https://zettelkasten.de/introduction/
- ADR convention (Nygard 2011): https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
