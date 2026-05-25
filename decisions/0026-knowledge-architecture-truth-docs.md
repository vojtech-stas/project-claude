# ADR-0026: Knowledge architecture — per-topic materialized truth-docs + current-state-reader subagent + topic-aware UserPromptSubmit hook + R-TRUTH-DOC reviewer rule

- **Status:** Accepted
- **Date:** 2026-05-25
- **Supersedes:** none
- **Extends:** [decisions/README.md](README.md) *"What an ADR is"* + *"Why one file per decision"* §Immutability (ADR immutability preserved — truth-docs derive FROM ADRs and never edit ADRs); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (5-stage pipeline preserved — implementer step extended per D2 below); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 (macro-ADR placement — this ADR drafted alongside PRD-K per the documented pattern); [ADR-0004](0004-bypass-prevention.md) D1 (joint critic gate honored — PRD-K + ADR-0026 ship under joint prd-critic + adr-critic gate); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited by D7 below); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer reused by `current-state-reader` per D3 below — adds `TOPIC` + `SOURCES_READ` per-agent extensions); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc check extended — truth-docs are now cascade-docs); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule honored per D8 below — no new critic added; reviewer gains a new RULE not a new critic); [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 (implementer tool boundaries — D2 below extends responsibility scope without changing tool set); [ADR-0011](0011-subagent-quality-framework.md) D4 (audit-subagents 10-check rubric — `current-state-reader.md` must pass ALL-1..5 + GEN-1); [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (hook scope policy respected — D4 below is logging/validation/notification, not LLM skill invocation); [ADR-0022](0022-docs-first-kb-pattern.md) D1 (per-topic on-demand-load pattern — `current-state-reader` follows similar dispatch shape); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D5 (UserPromptSubmit nudge pattern — D4 below follows); [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 (hook scripts under `.claude/hooks/` — D4 below follows the same placement).

## Context

The user articulated the design pain (verbatim 2026-05-25): *"I want to figure out better how to store information... sometimes old ADRs can have different information to the new ones (we decided in time differently)... I want to ensure better the workflow to be more straightforward and that subagents are spawned when wanted... I want the context of the main orchestrator to bloat the lowest so that we can work for long tasks."*

The project today has 5+ knowledge storage surfaces:
- `CLAUDE.md` (~1300 lines auto-loaded preamble; cross-cutting rules + Map + glossary)
- `decisions/NNNN-*.md` (immutable ADRs per [decisions/README.md](README.md) *"What an ADR is"*; supersession via `decisions/README.md` Status column)
- `.claude/skills/*/SKILL.md` (procedural know-how, on-demand-loaded per description-match)
- `.claude/agents/*.md` (subagent contracts)
- `GLOSSARY.md` folded into CLAUDE.md per [ADR-0012](0012-glossary-consolidation-single-tier.md) + [ADR-0014](0014-skill-local-vocabulary-and-auto-fold.md)
- External state: GitHub Issues, git history, project board #2

Three compounding pains:

1. **Supersession-blindness.** ADRs are immutable; *active truth on a topic* requires walking a supersession chain across multiple ADRs + skills + CLAUDE.md cross-references. Today's qa-automation truth = `ADR-0020 D1+D2+D4-D10` PLUS `ADR-0020 D3 as narrowed by ADR-0025 D1` PLUS `qa-tester.md dual-mode contract` PLUS `qa-plan.md` PLUS `CLAUDE.md "How to run a QA plan" pipeline-operational-logic row`. No artifact says "this is the current state today."

2. **Main-orchestrator context bloat.** Agents reading source files inline for topic queries bloat main context; for long autonomous runs (multi-PRD sweeps, DAG-batched slices) context exhausts before work completes.

3. **Squishy subagent dispatch.** Main agent's choice to dispatch a reader subagent vs read inline depends on Claude's judgment; bulk reads land in main context, defeating slim-orchestrator goals.

The 2026-05-25 grill (Q2-Q5) locked the design:
- Q2 2A: pure materialized truth-docs (NOT atomic-notes/Karpathy-style, NOT MCP server now, NOT graph traversal)
- Q3 3A: mandatory implementer step + reviewer R-TRUTH-DOC enforcement (NOT hook-triggered, NOT regen-on-read, NOT user-invoked)
- Q4 4B: subagent reads + summarizes (NOT main reads directly; main never loads truth-doc inline)
- Q5 5C: UserPromptSubmit hook + topics.json keyword-detection injects additionalContext nudge (mechanical; not relying on Claude judgment)

This ADR codifies the resulting architecture. ADRs remain the immutable historical record; truth-docs are the derived per-topic active synthesis.

## Decisions

### D1: Per-topic materialized truth-docs at `docs/current/<topic>.md`

Each architectural topic has ONE `docs/current/<topic>.md` file containing the active synthesis of the relevant ADR chain + skills + subagent bodies + CLAUDE.md cross-references for that topic. ADRs remain immutable per [decisions/README.md](README.md) *"What an ADR is"* (*"Once accepted, it's frozen at the moment of decision … the old one is never edited"*) — truth-docs derive FROM ADRs; truth-docs never edit ADRs. The truth-doc IS the answer to "what is currently true about this topic?"

**Reasonable size:** ~50-150 lines per topic. Format:
- H1 topic title
- Status line (e.g., "Status: current as of 2026-05-25")
- Date line
- Active synthesis (prose; the canonical "what's true today")
- Sources section (link list to all ADRs/skills/agents/CLAUDE.md sections that contributed)

**Walking-skeleton scope:** slice 1 ships ONE truth-doc (slicer judgment which topic — likely `qa-automation` for freshness). Subsequent topics ship as separate small PRDs per D7 bootstrap-mode.

### D2: Mandatory implementer step + R-TRUTH-DOC reviewer rule

Every PR that touches `decisions/NNNN-*.md` MUST also touch the corresponding `docs/current/<topic>.md` (regenerate or amend in same PR). The implementer is responsible for identifying which truth-doc(s) the ADR affects.

**Enforcement:** the `reviewer` subagent gains a new rule **R-TRUTH-DOC** (D5 below) that mechanically grep-checks the PR diff. If `decisions/NNNN-*.md` changed AND no corresponding `docs/current/*.md` changed → BLOCK with mechanically-actionable finding citing the affected topic.

**Cascading-topic handling:** the `adr-critic` subagent gains responsibility (cascade-doc per D9 below) to flag "this ADR affects topics X, Y, Z" during PRD draft critic review — surfaces the candidate set for implementer judgment.

**Carveout:** PRs editing ONLY `decisions/README.md` index rows (e.g., flipping a Status column) without modifying any `decisions/NNNN-*.md` body do NOT trigger R-TRUTH-DOC.

**Rejected alternatives** (grill Q3):
- Hook-triggered regeneration (3B) — blocked by ADR-0015 D2 (hooks can't invoke skills); pure-script regenerator can't do LLM synthesis cleanly
- Regen-on-read (3C) — defeats the pre-computed slim-load benefit of D1
- User-invoked manual `/refresh-truth` skill (3D) — relies on user discipline; defeats the autonomy goal the user has consistently pushed for

### D3: `current-state-reader` subagent

One generic reader subagent at `.claude/agents/current-state-reader.md` parametrized by `<topic>` string.

**Tool boundaries:** Read, Glob, Grep ONLY. NO Agent (no nested spawn — honors no-nested-spawn rule per `/best-practice-subagents` Rule 6). NO Write/Edit (reader cannot modify any file).

**Behavior:** receives `<topic>` from caller; reads `docs/current/<topic>.md`; returns thin synthesis (≤15 lines) + canonical GENERATOR trailer per [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c.

**Per-agent trailer extensions:** `TOPIC` (the topic string echoed back), `SOURCES_READ` (integer count of files actually read — typically 1 for the truth-doc itself; may be higher if the topic's truth-doc references additional files the reader resolves).

**Role classification:** GENERATOR per [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c — reads + returns synthesis; no adversarial verdict. Per [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap: this is the 4th generator (slicer + implementer + qa-tester + current-state-reader); critic count unchanged at 6.

**Quality:** must pass `/audit-subagents` 10-check rubric per [ADR-0011](0011-subagent-quality-framework.md) D4. ALL-1..5 + GEN-1 apply; CRIT-* checks do not (classifier per ADR-0011 D3: filename does NOT end `-critic.md` and is NOT `reviewer.md` → generator).

### D4: UserPromptSubmit topic-nudge hook

A new hook script under `.claude/hooks/` (sibling to existing per [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 placement convention) fires on UserPromptSubmit. Reads `.claude/topics.json` (keyword→topic mapping defined per D5 below — but the JSON file itself, not the rule); for each topic where any keyword matches the user's prompt (case-insensitive grep, word-boundary aware), emits `hookSpecificOutput.additionalContext` instructing main agent:

> *"Topic '<topic>' detected in prompt. Dispatch `current-state-reader` subagent with topic=<topic> BEFORE answering. Do NOT read source files (ADRs / skills / subagent bodies) inline."*

**Multiple topic matches:** emit one combined nudge listing all detected topics.

**Soft-degrade:** exit 0 if `jq` missing (does not block prompt).

**Registration:** a SECOND UserPromptSubmit array entry in `.claude/settings.json` alongside the existing grill-nudge entry from [ADR-0023](0023-validation-and-notification-hooks-extension.md) D5. Implementer may alternatively extend the existing `user-prompt-submit.sh` to handle both nudge cases in one script (OQ in parent PRD).

**Scope policy:** complies with [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (logging / validation / **notification** only — this hook NOTIFIES via additionalContext; does not invoke skills or subagents directly; the hook's nudge causes main agent to invoke the subagent, which is the legitimate notification → action chain).

### D5: New reviewer rule R-TRUTH-DOC

The `reviewer` subagent at `.claude/agents/reviewer.md` gains rule **R-TRUTH-DOC**:

> **R-TRUTH-DOC.** If `git diff --stat origin/main..HEAD -- decisions/` shows any `decisions/NNNN-*.md` file changed AND `git diff --stat origin/main..HEAD -- docs/current/` shows no `docs/current/*.md` changed → BLOCK with finding *"ADR change without corresponding truth-doc update; per ADR-0026 D2 the implementer must update or regenerate `docs/current/<topic>.md` for the affected topic(s) in the same PR."* Carveout: PRs editing ONLY `decisions/README.md` (e.g., index-row Status amendments) without modifying any `decisions/NNNN-*.md` body do NOT trigger.

R-TRUTH-DOC is the 12th reviewer rule. Default-conservative-toward-BLOCK per [ADR-0009](0009-discipline-tightening.md) D3 asymmetric-default-BLOCK.

### D6: New CLAUDE.md cross-cutting rule #14

CLAUDE.md gains new cross-cutting rule #14:

> **Truth-doc currency.** Every PR that adds or modifies a `decisions/NNNN-*.md` file MUST also update the corresponding `docs/current/<topic>.md` (regenerate or amend) in the same PR; the reviewer's R-TRUTH-DOC enforces. The implementer identifies which topic(s) an ADR affects (`adr-critic` flags candidate topics during PRD critic review); the truth-doc is the per-topic active synthesis of the relevant ADR chain. Per [ADR-0026](decisions/0026-knowledge-architecture-truth-docs.md).

The rule sits alongside existing rules #1-13 in CLAUDE.md "Cross-cutting rules" — numbered #14 as next in the established sequence (CLAUDE.md rule-numbering is convention-by-precedent, not codified in any ADR).

### D7: Bootstrap-mode acknowledgment (per ADR-0004 D2)

New truth-docs bind FORWARD from the slice that ships them. Existing closed ADRs (#1-#25 at this ADR's draft time) and existing slices are NOT retroactively swept into truth-docs.

**Forward-only binding:**
- Slice 1 of PRD-K ships ONE initial truth-doc (slicer-picked topic)
- Subsequent PRDs whose work touches a topic without an existing truth-doc → that PRD ships the truth-doc alongside its other artifacts (one PRD per topic typically; trivial-lane I3 possible for very small topics)
- ADRs from before this ADR-0026 merge remain unswept until a future PRD relevant to that topic naturally touches the area
- R-TRUTH-DOC reviewer rule (D5) applies forward-only: only PRs MERGED AFTER this ADR ships are evaluated against the rule

**No retroactive sweep PRD required.** Per-topic backfill happens organically as PRDs land. Acceptable trade-off: at any given moment, some topics have truth-docs and some don't; the topics that do are guaranteed-current via D2 + D5.

### D8: 6-critic-cap honored per ADR-0008 D7

This ADR adds NO new critic. The `current-state-reader` is a GENERATOR per D3 (reads + returns synthesis; no adversarial verdict). The new R-TRUTH-DOC rule (D5) extends the existing `reviewer` critic's rubric — `reviewer` was already the 1st critic; adding a rule to its existing rubric does not change the critic count.

Project critic count remains 6 (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`).

Project subagent count moves from 9 (6 critics + 3 generators: slicer + implementer + qa-tester) to 10 (6 critics + 4 generators: slicer + implementer + qa-tester + current-state-reader).

### D9: Cascade-doc updates

- `.claude/agents/current-state-reader.md` — NEW subagent file (per D3)
- `.claude/agents/reviewer.md` — add R-TRUTH-DOC rule (per D5) + verdict template handling for the new rule
- `.claude/agents/adr-critic.md` — add "flag affected topics" responsibility (per D2)
- `.claude/hooks/user-prompt-submit-topic.sh` (or implementer's chosen name) — NEW hook script (per D4)
- `.claude/settings.json` — register the new UserPromptSubmit hook entry (per D4)
- `.claude/topics.json` — NEW keyword→topic mapping file (per D4); initial entry for slicer-picked topic
- `docs/current/<topic>.md` — ONE NEW truth-doc for the slicer-picked topic (per D1; walking-skeleton)
- `decisions/0026-knowledge-architecture-truth-docs.md` — this ADR file (NEW)
- `decisions/README.md` — ADR-0026 index row appended in numerical order
- `CLAUDE.md` — new cross-cutting rule #14 (per D6); Map row for `current-state-reader` subagent; new pipeline-operational-logic section "How to query current state" (small, points at the dispatch pattern)
- `README.md` — slicer judgment (cascade-doc check per ADR-0005 D3); likely not in slice 1 (README narrative doesn't enumerate per-topic surfaces in current shape)

### D10: Relationship to existing surfaces

The truth-doc surface is **additive**, not replacement:

- **ADRs** preserved as immutable history per [decisions/README.md](README.md) *"What an ADR is"* + *"Why one file per decision"* §Immutability unchanged. ADRs answer "why we decided X when." Truth-docs answer "what's true now about topic Y." Both have value; both persist.
- **Skills / subagents** bodies remain procedural know-how (per CLAUDE.md rule #7 "Practices are colocated"). Truth-docs cite skill behaviors but do not duplicate skill bodies — they synthesize active state across skills + ADRs.
- **CLAUDE.md** remains cross-cutting rules + auto-loaded preamble + Map + glossary. Rule #14 (per D6) adds the truth-doc currency contract. No CLAUDE.md content removal in slice 1 (CLAUDE.md slim is PRD-R, orthogonal).
- **Glossary** (in CLAUDE.md per [ADR-0012](0012-glossary-consolidation-single-tier.md)) remains vocabulary. Truth-docs may reference glossary terms; do not duplicate definitions.
- **`best-practice-*` skills** (per [ADR-0022](0022-docs-first-kb-pattern.md)) remain external-source distillations (docs.claude.com etc.). Truth-docs are internal-state synthesis. The two surfaces are structurally distinct: best-practice-* answers "what does Anthropic recommend?" while truth-docs answer "what's our current internal state?" Both auto-load on-demand via description-match (best-practice-* via skill description; truth-docs via the topic-nudge hook → reader-subagent dispatch chain).

## Consequences

### Positive

- **Supersession-blindness fixed.** ONE file per topic = canonical "what's true today." No more chain-walking to assemble active state.
- **Main-orchestrator slim preserved.** Reader subagent reads in isolated context; returns ≤15-line summary to main. Long autonomous tasks can sustain because per-topic queries cost ~15 lines of main context, not 300+.
- **Mechanical dispatch determinism.** UserPromptSubmit hook injects additionalContext; main agent sees the dispatch instruction inline in its context; cannot be silently skipped.
- **In-band enforcement.** R-TRUTH-DOC fires at PR review time alongside existing rules; failure visible immediately, not at consumption time.
- **Honors existing patterns.** Subagent + skill + hook + reviewer rule + CLAUDE.md cross-cutting rule are all established surfaces in this project — no new infrastructure category.
- **Walking-skeleton-friendly.** Single slice cuts every layer (subagent + ADR + hook + topics.json + reviewer rule + adr-critic responsibility + CLAUDE.md rule #14 + Map row + ONE initial truth-doc + dogfood evidence). Forward-only bootstrap-mode keeps blast radius small.
- **6-critic-cap unchanged.** Reviewer rule extension (not new critic); reader subagent is generator (not critic).
- **Composable with future PRDs.** Backfill of subsequent topic truth-docs happens organically as PRDs touch those topics; no separate sweep PRD required.

### Negative / Accepted

- **Implementer burden** — every ADR-touching PR adds one truth-doc edit. Mitigated by adr-critic flagging affected topics; trade-off accepted in exchange for guaranteed-current truth-docs.
- **Cascading-topic edge cases** — one ADR may affect 2+ topics; implementer judgment required to identify all. Mitigated by adr-critic flagging + reviewer enforcement; pathological cases captured per CLAUDE.md rule #11 if they arise.
- **Truth-doc content-correctness not mechanically verifiable** — R-TRUTH-DOC catches MISSING edits; cannot prove edit was semantically correct. Mitigated by adr-critic semantic review + future `/audit-currency` skill (separate PRD); acceptable trade-off given 6-critic-cap.
- **Topics.json keyword maintenance** — adding a new truth-doc requires adding keywords to topics.json. Small per-PRD increment; not a load-bearing cost.
- **No retroactive coverage of pre-merge ADRs** — accepted per D7 bootstrap-mode. Topics 2-9 backfill organically; some topics may not have truth-docs for weeks/months until a relevant PRD touches them.
- **Hook keyword false-positive risk** — keyword "QA" might fire when user mentions QA tangentially. Mitigated by word-boundary grep + the cost of one extra reader-subagent dispatch (~$0.001) being much lower than the cost of main-context bloat from missed dispatch. Asymmetric-cost favors over-firing.
- **Two on-demand-loaded knowledge surfaces** (`best-practice-*` skills + truth-doc-via-reader-subagent) — slightly more cognitive load to know which surface answers which question. Mitigated by D10's clear delineation (external-source distillation vs internal-state synthesis).

## Alternatives considered

- **Alt-A: Status quo + better hygiene.** Add `/audit-currency` skill flagging stale citations; richer `decisions/README.md` Status column; stricter `Supersedes`/`Extends` headers. Treats symptoms not cause; doesn't address main-context-bloat from chain-walking. Rejected per grill Q2.
- **Alt-B: Atomic-notes / Karpathy-style second brain.** Many small notes with bidirectional links; LLM-self-improving wiki. Optimizes for human exploration (Karpathy's vision targets human + LLM read/write). Our consumers are mostly agents needing deterministic answers; atomic-notes require traversal + on-the-fly synthesis at every query. Rejected per grill Q2 explicit second-pass deliberation.
- **Alt-C: Project-local MCP server indexing ADRs/skills/CLAUDE.md.** Right answer at ~2-3x current scale (~150+ artifacts) or once team forms. Premature at current ~50-file scale; consumer-fork friction. Rejected for now; documented as future direction.
- **Alt-D: Graph traversal + `/explain` skill (synthesize-on-read).** No new substrate; `/explain <topic>` walks Supersedes/Extends chains live. Always-fresh but every read costs full LLM synthesis; defeats the pre-computed-slim-load benefit of D1. Rejected per grill Q2.
- **Alt-E: RAG with vector DB (Chroma/Qdrant/pgvector).** Right tool at 1000+ unstructured docs OR when keyword grep is insufficient. Our corpus is ~50 structured markdown files with consistent vocabulary (glossary-enforced); grep already finds what we need exactly. Textbook search-at-scale-for-structured-small-corpus anti-pattern. Rejected.
- **Alt-F: Knowledge graph with explicit schema (Neo4j).** Massively over-engineered at our scale. Rejected.
- **Alt-G: Database-backed (Postgres + JSON columns).** Loses markdown readability + per-decision git history (entire reason ADRs are one-file-per-decision per [decisions/README.md](README.md) *"Why one file per decision"*). Rejected.
- **Alt-H: Hybrid (atomic notes WITH per-topic index docs).** Captures atomic-notes wins + truth-doc agent-determinism wins. Doubles artifact tier; premature at current scale. Documented as long-term hybrid direction; rejected for slice 1.
- **Alt-I: Hook-triggered regeneration (Q3 3B).** PostToolUse or post-merge hook detects `decisions/` changes; runs regenerator script. ADR-0015 D2 blocks skills/subagent invocation from hooks; pure script can't do LLM synthesis cleanly. Rejected.
- **Alt-J: Regen-on-read / lazy synthesis (Q3 3C).** Truth-docs not stored; reader-subagent synthesizes from ADRs at read time. Defeats D1's pre-computed-slim benefit; collapses to Alt-D. Rejected.
- **Alt-K: User-invoked `/refresh-truth` skill (Q3 3D).** Lowest implementation cost but relies on user discipline; defeats the autonomy goal the user has consistently pushed. Rejected.
- **Alt-L: Main agent reads truth-docs directly via on-demand skill load (Q4 4A).** Pattern proven by `best-practice-*` skills. Slim per-query but main still loads the truth-doc fully. Locked Q4 4B chose subagent-reads pattern for thinner main-context impact (≤15 line summary vs full 50-150 line truth-doc).
- **Alt-M: Description-only subagent dispatch + no hook (Q5 5A).** Trust Claude's auto-dispatch heuristic. Same failure mode the user explicitly flagged ("subagents spawned when wanted" failures). Rejected per grill Q5.
- **Alt-N: Truth-doc-correctness critic (catching wrong-edit not missing-edit).** Would breach ADR-0008 D7 6-critic-cap without justification meeting the meta-rule's "an existing critic's rubric cannot absorb the concern" bar. Defers to future `/audit-currency` skill per ADR-0011 D5 single-Markdown-advisory-report pattern. Rejected for this PRD.

## Open questions deferred

- **OQ-1: Initial-topic selection for slice 1.** Slicer picks (recommendation: `qa-automation`).
- **OQ-2: Hook file naming.** Implementer judgment within existing kebab convention (`<event>.sh`).
- **OQ-3: Hook combination vs separate files.** Implementer judgment — extend existing `user-prompt-submit.sh` OR add second hook script.
- **OQ-4: Keyword-match precision.** Word-boundary grep recommended; implementer judgment per topic for slice 1 topics.json entry.
- **OQ-5: Truth-doc regeneration mechanism.** Slice 1 ships manual implementer authoring; `regenerate-truth-doc` skill is candidate for follow-up PRD once 2-3 truth-docs exist and pattern stabilizes.
- **OQ-6: Truth-doc placement on Windows.** No platform-specific concern expected; implementer verifies.
- **OQ-7: Cascading-topic handling when ADR affects 2+ topics.** Implementer judgment + adr-critic flagging covers most cases; edge cases captured per rule #11.
- **OQ-8: `current-state-reader` summary format.** ≤15 lines per spec; exact shape (bullet list vs paragraph vs key-value) implementer judgment for slice 1; standardize if drift emerges.

## Future direction

- **Topic backfill PRDs.** As future PRDs touch un-truth-docced topics, they ship truth-docs alongside. Per D7 bootstrap-mode; no separate sweep PRD.
- **`/audit-currency` skill** (post-2-3 truth-docs). Periodic mechanical sweep checking truth-docs reference live (non-superseded) sources; flags drift. Sibling to `/audit-subagents` + `/audit-meta`. Honors 6-critic-cap (skill ownership not 7th critic).
- **`/regenerate-truth-doc <topic>` skill** (post-2-3 truth-docs). Codifies the regeneration pattern once it's stabilized; implementer invokes per D2 instead of authoring inline.
- **Project-local MCP server** (post-~2-3x scale or team-formation). Indexes truth-docs + ADRs + skills + CLAUDE.md; exposes `mcp__project__active(<topic>)` tool. Right answer at next-scale.
- **Hybrid (atomic notes + topic indexes)** (post-~150 artifacts). Atomic notes capture concepts; topic-index docs auto-generated synthesis over them. Captures both Karpathy wins and truth-doc determinism wins.
- **`best-practice-*` ↔ truth-doc cross-references.** Where a topic has both surfaces (e.g., `subagents` has `best-practice-subagents` external-distillation AND would have `subagents` truth-doc internal-state), the truth-doc may link to the best-practice skill and vice-versa.

## References

- 2026-05-25 grill Q2-Q5 — the decision provenance (Q-by-Q decisions locked verbatim with user)
- [decisions/README.md](README.md) *"What an ADR is"* + *"Why one file per decision"* §Immutability + *"Conventions"* §Filename — authoritative source for ADR immutability + filename/numbering convention (preserved per D10)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 — pipeline preserved (implementer step extends per D2)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement (this ADR drafted alongside PRD-K)
- [ADR-0004](0004-bypass-prevention.md) D1 — joint critic gate (PRD-K + ADR-0026 ship under it)
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy (D7 follows)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR trailer schema (D3 reuses with TOPIC + SOURCES_READ extensions)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 — cascade-doc check (D9 extends to truth-docs)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule (D8 honors)
- [ADR-0009](0009-discipline-tightening.md) D3 — asymmetric-default-BLOCK (R-TRUTH-DOC follows per D5)
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 — implementer tool boundaries (D2 extends responsibility scope without changing tool set)
- [ADR-0011](0011-subagent-quality-framework.md) D3/D4 — generator classifier + 10-check rubric (D3 subagent must pass)
- [ADR-0011](0011-subagent-quality-framework.md) D5 — single-Markdown-advisory-report pattern (cited in Alt-N rejection rationale)
- [ADR-0012](0012-glossary-consolidation-single-tier.md) — glossary single-tier (D10 references)
- [ADR-0014](0014-skill-local-vocabulary-and-auto-fold.md) — skill-local vocab + glossary-fold (D10 references)
- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 — hook scope policy (D4 respects)
- [ADR-0020](0020-qa-automation-writer-executor.md) — qa-automation source artifact for likely initial truth-doc
- [ADR-0022](0022-docs-first-kb-pattern.md) D1 — best-practice-* per-topic 4-section pattern (D10 delineates)
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) D5 — UserPromptSubmit grill-nudge precedent (D4 follows)
- [ADR-0023](0023-validation-and-notification-hooks-extension.md) D7 — hooks under `.claude/hooks/` (D4 follows placement)
- [ADR-0024](0024-root-cause-workflow-capture-discipline.md) D1/D3 — rule #13 root-cause-shape (cited for cascading-topic edge-case capture path)
- [ADR-0025](0025-qa-tester-ui-mode-playwright.md) — qa-automation source artifact (recent supersession of ADR-0020 D3; case study for D1 motivation)
- `.claude/agents/current-state-reader.md` — file created by PRD-K slice 1 per D3
- `.claude/agents/reviewer.md` — file edited by PRD-K slice 1 per D5
- `.claude/agents/adr-critic.md` — file edited by PRD-K slice 1 per D2
- `.claude/hooks/user-prompt-submit-topic.sh` (or implementer's chosen name) — file created by PRD-K slice 1 per D4
- `.claude/settings.json` — file edited by PRD-K slice 1 per D4
- `.claude/topics.json` — file created by PRD-K slice 1 per D4
- `docs/current/<topic>.md` — file created by PRD-K slice 1 per D1
- `decisions/README.md` — file edited by PRD-K slice 1 per D9
- `CLAUDE.md` — file edited by PRD-K slice 1 per D6 + D9
