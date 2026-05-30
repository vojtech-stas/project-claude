# ADR-0032: Workflow-only architecture — eliminate KB layer; sources canonical in skills + subagents + CLAUDE.md + ADRs

- **Status:** Accepted
- **Date:** 2026-05-30
- **Supersedes:** [ADR-0019](0019-best-practices-kb-pattern.md) D1 (external-content ingestion pattern — entirety; best-practices KB moved out of this template); [ADR-0019](0019-best-practices-kb-pattern.md) D2 (`docs/best-practices/` doc tree — entirety; deleted by this PRD); [ADR-0022](0022-docs-first-kb-pattern.md) D1 (per-topic best-practice skill 4-section body shape — entirety; topic skills `best-practice-{workflow,hooks,subagents}` retired); [ADR-0022](0022-docs-first-kb-pattern.md) D2 (source tier priority — entirety; Tier-3 video distillations under `docs/best-practices/` retired with the KB); [ADR-0022](0022-docs-first-kb-pattern.md) D3 (per-topic skill location convention `.claude/skills/best-practice-<topic>/SKILL.md` — entirety; no best-practice topic skills remain); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1 (per-topic materialized truth-doc surface at `docs/current/<topic>.md` — entirety; superseded by inlining content back into skill/subagent bodies); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2 (mandatory implementer truth-doc cascade step — entirety; no truth-docs to cascade to); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D3 (`current-state-reader` subagent — entirety; subagent retired); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D4 (UserPromptSubmit topic-nudge hook — entirety; hook retired); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D5 (R-TRUTH-DOC reviewer rule — entirety; rule removed from reviewer.md); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D6 (CLAUDE.md cross-cutting rule #14 truth-doc currency — entirety; rule removed from CLAUDE.md); [ADR-0031](0031-knowledge-architecture-v2.md) entirely (5-node KB taxonomy + 13 typed edges + YAML frontmatter + atomic-notes architecture + T1-T9 migration program — superseded by deletion; substrate gone)
- **Extends:** [ADR-0017](0017-audit-meta-consolidation.md) D3 (audit-meta docs-currency rubric — DOCS-5/6 literal-drift scope changed per D4 below; DOCS-1/2/3/4/7/8/9/10 preserved with adjusted file sets); [ADR-0018](0018-boy-scout-reviewer-rule.md) D2 (R-BOY-SCOUT trigger paths — adjusted per D3 below; `docs/current/` removed from the audit-relevant file pattern set since it no longer exists; `dashboard/*` retained per ADR-0033 D4); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy — cited by D7); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — preserved per D8); [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4 (generated-docs currency model — PRESERVED + reconciled per D11 below: README becomes a build artifact compiled from a template, consistent with D1's "README is the human-facing surface" — it is generated, not hand-maintained), [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D5 (R-DOCS-CURRENT reviewer rule — PRESERVED per D3/D11; it gates generated-README drift, a distinct concern from the retired R-TRUTH-DOC); [ADR-0033](0033-tooling-spawn-hook-scope.md) (dashboard tooling-spawn carveout — unaffected; `dashboard/*` non-runtime + R-BOY-SCOUT trigger retained); [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) (parallel-dispatch worktree isolation — unaffected); [decisions/README.md](README.md) "What an ADR is" (ADR immutability — preserved; this ADR supersedes earlier decisions via the standard supersession mechanism rather than editing them)

## Context

This repository's stated purpose: a **workflow template** for AI-coded Python projects using GitHub as the backbone (slicing, PR ceremony, senior-engineer practices applied to AI engineering). The original vision combined this workflow with a large external-content knowledge base (distilled YouTube videos + articles, atomic notes, typed edges, eventual LLM-as-compiler). After 6 weeks of building, the user has determined that **the two concerns belong in two separate projects**. The workflow template should be small, self-contained, and not carry the half-built KB layer.

The KB layer evolved over four ADRs:
- [ADR-0019](0019-best-practices-kb-pattern.md) (2026-05-21): introduced `docs/best-practices/` as the doc tree for distilled external content from authorized YouTube channels (`@claude`, `@anthropic-ai`).
- [ADR-0022](0022-docs-first-kb-pattern.md) (2026-05-22): pivoted to a "docs-first" pattern with Tier-1 on-demand best-practice topic skills (`best-practice-workflow`, `-hooks`, `-subagents`).
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) (2026-05-25): introduced `docs/current/<topic>.md` per-topic truth-docs, `current-state-reader` subagent, topic-nudge UserPromptSubmit hook, R-TRUTH-DOC reviewer rule, CLAUDE.md cross-cutting rule #14.
- [ADR-0031](0031-knowledge-architecture-v2.md) (2026-05-26): expanded to the full 5-node Karpathy-compiler architecture — atomic notes under `docs/current/{concepts,entities,topics,patterns}/`, typed edges, `docs/raw/` source layer, T1-T9 migration program shipping `kb-maintainer` (T8), `impact-analyst` (T7), and `knowledge-gateway` (T9) generator subagents to consume the substrate.

The T1-T6 portion of ADR-0031 D10 shipped between 2026-05-26 and 2026-05-29: glossary atomic notes (T1), reviewer + hooks migration (T2), slicer + pipeline-stages topic (T3), 7 remaining subagents migration (T4), 13 skills migration (T5), CLAUDE.md major slim 988→155 LoC (T6). T7-T9 (the three generator subagents that would actually **consume** the typed-edge substrate) **never shipped**.

The empirical observation, after dogfooding both architectures: Claude Code's runtime model loads CLAUDE.md + skills + subagents + hooks + settings.json. **None of these consume `docs/current/` at runtime.** The KB is a parallel surface that costs maintenance without delivering runtime value while T7-T9 remain unshipped. Concrete drift incidents this session (README staleness post-T6; captured #300 wrong-ADR-slug propagating to multiple atomic notes; the 11th GLOSSARY.md ref in `grill-me/SKILL.md` that pre-flight audits missed) are all downstream of "multiple synthesis surfaces hand-maintained in parallel" — exactly the duplication the KB layer creates without compensating value.

User-driven decision 2026-05-29: eliminate the KB layer entirely. Workflow template is the project. KB (if needed) is a separate project.

This ADR captures the architectural lock. The implementing PRD (PRD-W, posted alongside per ADR-0003 D8) ships the inlining + retirement + deletion + cascade-doc updates in 4 slices.

## Decisions

### D1: Target architecture — sources canonical in 4 surfaces

The workflow template has exactly four surfaces of operational content:

- **`README.md`** — human-facing explanatory document for newcomers / clients. Long-form, with diagrams. The primary "what is this project" surface. Per [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D4 it is a **generated build artifact**, compiled by the doc-generator from a static template (`README.template.md`, repo root — see D11) + the canonical filesystem surfaces. It is committed (so GitHub renders it) but never hand-edited; the human-authored prose lives in the template.
- **`CLAUDE.md`** — always auto-loaded by Claude Code at session start. Operating manual: cross-cutting rules + Map (index pointing to skills/subagents/hooks/scripts) + **full glossary inline** (no external definition files).
- **`.claude/skills/<name>/SKILL.md`** — self-contained. Full rubric, full mechanics, full reference material inline. The skill body IS the operating definition.
- **`.claude/agents/<name>.md`** — self-contained. Full role, full rules, full output spec inline.

Plus the existing non-content infrastructure:
- `.claude/hooks/` + `.claude/settings.json` (hooks; unchanged by this ADR)
- `decisions/NNNN-*.md` (immutable ADRs; this ADR adds; supersedes earlier ADRs but does NOT edit them)
- `bootstrap.sh` + `.githooks/` (setup tooling; unchanged)
- `tools/` (workflow tooling: `cascade-finder.py`; discovery substrate updated per D6)

**No `docs/` directory.** All KB-style content is either (a) inlined into one of the four canonical surfaces above, OR (b) moved to a separate project outside this template. The one non-KB file that lived under `docs/` — the ADR-0034 README template (`docs/readme.template.md`) — relocates to repo root as `README.template.md` so `docs/` can be deleted in full (`test ! -d docs`); see D11.

### D2: CLAUDE.md cross-cutting rule #14 (truth-doc currency) RETIRED

ADR-0026 D6's cross-cutting rule #14 ("Every PR that adds or modifies a `decisions/NNNN-*.md` file MUST also update the corresponding `docs/current/<topic>.md`") is RETIRED. There is no `docs/current/` to update. Rule numbering: rules 1-13 are preserved at their current numbers; rule #14 slot becomes empty (NOT renumbered — rules are referenced by number from many ADRs and skill/subagent bodies; renumbering would invalidate citations).

Future ADRs MAY introduce new rules at #15+; #14 remains explicitly retired as a historical marker.

### D3: R-TRUTH-DOC reviewer rule RETIRED; R-BOY-SCOUT trigger set adjusted

ADR-0026 D5's R-TRUTH-DOC reviewer rule (reviewer rule 12) is RETIRED. The rule fired on `decisions/NNNN-*.md` PRs that lacked an accompanying `docs/current/` update; with no `docs/current/`, the rule is meaningless.

Reviewer.md rule list after this ADR: rules 1-11 preserved at current numbers; rule 12 (R-TRUTH-DOC) removed. **R-DOCS-CURRENT (ADR-0034 D5, currently reviewer rule 13) is PRESERVED** — it is a distinct mechanism (it regenerates `README.md` and BLOCKs on generated-vs-committed drift; it has nothing to do with the retired KB truth-docs). Because R-DOCS-CURRENT is new (shipped 2026-05-30, with no external citations *by number*), it is **renumbered 13 → 12** to keep the hard-block rule list contiguous (1-12) rather than leaving a gap — the one safe renumbering, since R-TRUTH-DOC's old number 12 is the slot it fills. R-BOY-SCOUT remains the discretionary rule.

[ADR-0018](0018-boy-scout-reviewer-rule.md) D2's R-BOY-SCOUT trigger file set is adjusted: was `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `decisions/*.md`, `CLAUDE.md`, `README.md`, `dashboard/*` plus `docs/current/` files; now `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `decisions/*.md`, `CLAUDE.md`, `README.md`, `dashboard/*` (ONLY `docs/current/` removed — the `dashboard/*` trigger added by ADR-0033 D4 / PR #357 is RETAINED). The discretionary rule itself is preserved (still useful defense-in-depth against drift in the remaining surfaces).

### D4: /audit-meta DOCS-* rubric re-scoped

[ADR-0017](0017-audit-meta-consolidation.md) D3's docs-currency rubric:

- **DOCS-1 + DOCS-2** (ADR index ↔ on-disk ADRs bidirectional sync) — PRESERVED unchanged; `decisions/README.md` and `decisions/NNNN-*.md` still exist.
- **DOCS-3 + DOCS-4** (CLAUDE.md Map row references to `.claude/agents/` and `.claude/skills/` resolve) — PRESERVED unchanged.
- **DOCS-5 + DOCS-6** (literal-drift detectors: `N=3` in README; `GLOSSARY.md` anywhere in `*.md`) — RE-SCOPED. DOCS-5 scope unchanged (still README.md). DOCS-6 scope changed: was "all `*.md` files repo-wide excluding `.git/`"; now "CLAUDE.md + README.md + `.claude/agents/*.md` + `.claude/skills/*/SKILL.md` + `decisions/*.md`" (the four canonical surfaces from D1; `docs/` is gone).
- **DOCS-7** (every `[ADR-NNNN](decisions/NNNN-*.md)` citation resolves) — PRESERVED. Repo-wide scope unchanged; with `docs/` gone, the search set naturally shrinks.
- **DOCS-8** (supersession annotations in `decisions/README.md`) — PRESERVED unchanged.
- **DOCS-9** (CLAUDE.md glossary entry count ≤35) — PRESERVED unchanged; the inlined-glossary CLAUDE.md still has 22 entries (well under cap).
- **DOCS-10** (no `backlog`-label surfacing in `.claude/agents/` or `.claude/skills/`) — PRESERVED unchanged.

The atomic rule notes at `docs/current/concepts/rules/am-docs-*.md` (the calibrated rule bodies from PRD #334 / PR #336) are deleted with `docs/current/`; their content is inlined back into `.claude/skills/audit-meta/SKILL.md` per the implementing PRD's Slice 1.

### D5: Best-practices KB moves to a separate project; this template does not carry external-content distillations

ADR-0019 + ADR-0022 established `docs/best-practices/` as a doc tree for distilled YouTube transcripts from `@claude` + `@anthropic-ai` channels. The user's evaluation 2026-05-29: this is reference material that doesn't belong in a workflow template. External-content distillations are a separate concern (KB-building project, not workflow-template project).

`docs/best-practices/` is DELETED. The `distill-video` skill (which ingested videos into the KB) is RETIRED. The `best-practice-workflow`, `best-practice-hooks`, `best-practice-subagents` skills (which synthesized the KB into on-demand topic guidance) are RETIRED.

Future workflow-template contributors who want best-practices guidance use external sources directly (YouTube, blog posts, books) — the same way they would for any other tool.

### D6: cascade-finder discovery substrate change

[`tools/cascade-finder.py`](../tools/cascade-finder.py) (shipped 2026-05-29 via PR #339) discovers dependents via four passes: `edge` (parses `**<EdgeType>:** [[path]]` in `docs/current/**/*.md`), `grep-slug` (ADR-NNNN literals), `grep-filename` (basename matches), `grep-concept` (concept title strings).

With `docs/current/` deleted, the `edge` pass has no substrate. The implementing PRD's Slice 3 updates the tool:

- Remove the `edge` discovery pass entirely (substrate gone)
- Discovery substrate becomes: tracked `.md` files in `.claude/agents/`, `.claude/skills/`, `decisions/`, plus `CLAUDE.md`, `README.md`, plus shell scripts in `.claude/hooks/`, plus the tracked Python in `tools/`
- The three remaining passes (`grep-slug`, `grep-filename`, `grep-concept`) operate on this substrate
- The tool retains its advisory function; the typed-edge precision is lost (Phase 2 of the cascade plan, when proposed, would need a different mechanism — e.g., explicit dependency tags in skill/subagent frontmatter, or a hand-maintained `.claude/cascade-rules.yml` — but that's a future PRD)

### D7: Bootstrap-mode acknowledgment per ADR-0004 D2

- The architectural choice (no `docs/`; sources canonical in 4 surfaces) binds **forward** from ADR-0032 merge
- Existing skill/subagent inlining is performed in the implementing PRD's Slice 1 (one-time migration, not retroactive sweep of past PRs)
- Existing ADRs are NOT edited per ADR immutability; this ADR supersedes prior decisions via the standard supersession mechanism
- Future skills/subagents are born self-contained from ADR-0032 merge forward
- Existing best-practices distillations (`docs/best-practices/`) are deleted in Slice 3; the choice to delete (vs archive in a branch) is per ADR-0019 D5 — they're reproducible from the YouTube source if ever needed
- The `decisions/` ADRs remain authoritative for "why we made this decision"; this ADR is the latest

### D8: 6-critic-cap honored per ADR-0008 D7

The 6-critic-cap meta-rule states: promoting a 7th critic requires a new ADR explicitly justifying why an existing critic's rubric cannot absorb the concern.

This ADR retires no critic and introduces no critic. Critic count remains 6: `reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`. The retired surfaces (`current-state-reader`, `distill-video`, `best-practice-*`) are GENERATORS (skill/subagent body, advisory output), not critics. The 6-critic count is preserved.

### D9: Cascade-doc updates (this ADR's own cascade)

The implementing PRD's Slice 4 (this ADR's home slice) updates:
- `decisions/0032-workflow-only-architecture.md` — this ADR (NEW)
- `decisions/README.md` — row for ADR-0032 + supersession annotations on rows for ADR-0019, ADR-0022, ADR-0026, ADR-0031
- `.claude/agents/reviewer.md` — rule 12 (R-TRUTH-DOC) removed; rule body updates
- `CLAUDE.md` — cross-cutting rule #14 removed; rule list comment notes #14 retired per ADR-0032 D2

Slices 1-3 of the implementing PRD perform the rest of the cascade (inlining + retirement + deletion).

### D10: ADR immutability preserved

ADR immutability rule per `decisions/README.md` "What an ADR is": once accepted, an ADR is frozen at the moment of decision and is NOT edited. Status MAY flip from `Accepted` to `Superseded by ADR-NNNN`. The body of an old ADR is never edited.

This ADR honors that rule: ADR-0019, 0022, 0026, 0031 bodies are NOT edited. Their `decisions/README.md` index rows gain "Superseded by ADR-0032" annotations. Their Status headers (within their own files) may remain "Accepted" since the immutable rule doesn't require Status updates inside the file (the supersession is captured at the index level per the project's established pattern; ADR-0001 D9 superseded by ADR-0002 is the precedent — ADR-0001 still shows Status: Accepted in its body).

### D11: Coexistence with the ADR-0034 generated-docs model (post-#348 reconciliation)

[ADR-0034](0034-build-orchestrator-and-generated-docs.md) (shipped 2026-05-30, PRD #348) introduced after this ADR was first drafted: the `/build` orchestrator, the generated-README model (`README.md` compiled from a template by `dashboard/server.py --generate-readme`), the `R-DOCS-CURRENT` reviewer rule (D5), and the `.githooks/pre-commit` README-currency check (D6). The ADR-0034 template was placed at `docs/readme.template.md`. This ADR's "delete `docs/`" mandate (D1) therefore needs explicit reconciliation:

1. **The README template relocates** `docs/readme.template.md` → **`README.template.md` (repo root)** so `docs/` can be deleted in full while the generated-README model keeps working. The implementing slice updates the three ADR-0034 references to the template path: the generator (`dashboard/server.py --generate-readme`), the pre-commit check (`.githooks/pre-commit`), and the R-DOCS-CURRENT rule text in `reviewer.md`.
2. **R-DOCS-CURRENT is PRESERVED, not retired.** It and the retired R-TRUTH-DOC are unrelated: R-TRUTH-DOC gated ADR↔KB-truth-doc currency (the KB is gone); R-DOCS-CURRENT gates generated-README drift (still needed — README is still generated). The generated-docs currency model is *complementary* to the workflow-only architecture: it is precisely the mechanism that keeps the one remaining human-facing surface (README) drift-proof without a KB layer.
3. **The README rewrite** (removing the KB sections — `Knowledge base` H3, `docs/` bullets, ADR-0031 narrative) is performed by editing **`README.template.md`** (the source), then regenerating `README.md` — NOT by hand-editing `README.md` (which R-DOCS-CURRENT would BLOCK).
4. **Inventory-changing slices regenerate README**: retiring the KB skills (`distill-video`, `best-practice-*`) and the `current-state-reader` subagent changes the filesystem inventory the generator reads, so those slices regenerate `README.md` to keep it current (and to pass R-DOCS-CURRENT).

The doc-generator's filesystem-reading scope (`.claude/{agents,skills,hooks,settings.json}` + `decisions/` + the template) never read `docs/current/`, so the KB deletion does not otherwise affect it.

## Consequences

### Positive

- **Self-contained operational units**: each skill/subagent has full rubric + mechanics inline. No external-file dependency to operate.
- **Reduced drift surface**: ~150 atomic notes deleted; ~5000 LoC of parallel-maintained content gone. Drift is structurally less likely.
- **Faster context load**: skill/subagent invocation loads ONE file, not 5-10 atomic notes.
- **Simpler mental model**: contributors learn 4 surfaces instead of 4 surfaces + KB layer with 5 node types + 13 edge types + frontmatter schema.
- **Honest about T7-T9**: the deferred subagents (impact-analyst, kb-maintainer, knowledge-gateway) were the value-delivery mechanism of ADR-0031; without them, the substrate was pure cost. This ADR acknowledges that.
- **6-critic-cap preserved**: no architectural pressure to add new critics.
- **Bootstrap-mode honored**: forward-binding; one-time migration in implementing PRD.
- **Best-practices separation**: workflow template stays focused on workflow; external-content KB-building goes to its own project where it can be built without compromising this template.

### Negative / Accepted

- **Loses the typed-edge KB query capability**: the elegant `[[path]]` edge graph from ADR-0031 D3 is deleted with the substrate. Accepted because no consumer ever shipped to use it.
- **cascade-finder Phase 1 (just shipped) loses its primary discovery pass**: the `edge` pass becomes inert when `docs/current/` is gone. The tool retains its three `grep-*` passes; Phase 2 (when proposed) would need a different precision mechanism (e.g., explicit dependency tags). Reduced utility but tool not deleted.
- **Reverses ~6 weeks of T1-T6 migration effort**: the inlining work moves content back where it came from. Sunk cost; the user has determined the move was wrong direction; this is the correction.
- **Critic + skill bodies grow back**: thinning effort partially undone. reviewer.md may exceed 1000 LoC. Mitigated by `reviewer.md` R-LOC canonical scope explicitly excluding agent body markdown.
- **Loses `current-state-reader` topic-aware context injection**: the topic-nudge hook (ADR-0026 D4) that auto-loaded relevant truth-docs is gone. Replaced by: CLAUDE.md auto-loads + skill descriptions match prompts. Less precise but simpler.
- **Loses the structured glossary index pattern**: ADR-0012 D1's consolidated single-tier glossary inline in CLAUDE.md becomes its own surface again; no external glossary files. Mitigated by the inline-glossary CLAUDE.md being smaller than the pre-ADR-0012 two-tier setup.
- **Documentation discoverability for newcomers**: a newcomer reading the codebase loses the `docs/current/topics/` synthesis pages. README.md inherits the explanatory burden (rich newcomer onboarding). Mitigated by README rewrite (PR #333 already significantly improved README; further enrichment possible in future PRDs).

## Alternatives considered

- **Alt-A: Finish ADR-0031 by shipping T7-T9 (impact-analyst + kb-maintainer + knowledge-gateway)**. Rejected per user mandate (2026-05-29): "we have tackled this incorrectly... the knowledge base should be maybe only for some short-term and long-term memory... we have to separate these two things into two different projects." Significant additional work (~3 PRDs) for unclear value at the project's current scale (~30 ADRs, ~24 skills+subagents). The KB substrate without consumers has been pure cost for 4 weeks.
- **Alt-B: Hybrid — keep some atomic notes (e.g., glossary stays separate; rules inlined)**. Rejected: creates ambiguous boundaries ("which content stays in atomic notes, which moves back?"). Cleaner to be all-in either direction. User chose all-in workflow-only.
- **Alt-C: Status quo with audit-meta blocking enforcement (Option X / Y from this session's earlier analysis)**. Rejected: treats symptoms (drift detection) rather than root cause (maintenance cost of the KB layer). The user's session-end analysis converged on root-cause vs symptom — Architecture B from earlier discussion.
- **Alt-D: Archive `docs/` in a separate branch (e.g., `archive/kb-v2`) instead of deleting**. Rejected: archive branches are a maintenance burden of their own; git history preserves all `docs/` content anyway (anyone needing it can `git checkout main~10 -- docs/`). Clean deletion is simpler.
- **Alt-E: Build a `docs/memory/` for legitimate KB use cases (session-summaries, decision-trail, long-running context)**. Deferred (rabbit-hole per PRD §6): the user mentioned "the knowledge base should be maybe only for some short-term and long-term memory" but immediately said "we have to separate these two things into two different projects." A small `docs/memory/` could be added later if a legitimate use case appears; not added in this ADR.
- **Alt-F: Keep `docs/best-practices/` as reference material; only delete `docs/current/`**. Rejected per user mandate (2026-05-29): "best practices also don't have to be even in this repository." External content distillations don't belong in a workflow template.
- **Alt-G: Rename `docs/best-practices/` to `references/` or `reading-list/` at repo root**. Rejected: the user explicitly said this content belongs in a separate project, not a renamed location. Renaming doesn't address the concern.
- **Alt-H: Continue thinning skill/subagent bodies via Phase 2 of the cascade plan (auto-update + LLM propagator) instead of inlining back**. Rejected: assumes the KB v2 architecture is right; user determined it's wrong.
- **Alt-I: Multi-PRD migration spread over weeks (one slice per surface category)**. Rejected per user mandate ("let's delete now the knowledge base"): single PRD with 4 slices is the appropriate scope; matches the ADR-0031 D10 "9-step migration" pattern in scope but inverted in direction.
- **Alt-J: Keep ADR-0031 typed-edge architecture and rebuild around it after current-state-reader retirement**. Rejected: typed edges have no consumer (T7-T9 deferred); maintaining them is pure cost.

## Open questions deferred

- **OQ-1**: Future `docs/memory/` (short-term + long-term memory) for legitimate KB use cases — deferred per Alt-E above. May be added in a future PRD if a use case appears.
- **OQ-2**: cascade-finder Phase 2 precision mechanism (typed-edge replacement) — deferred per D6 above. Options when proposed: explicit dependency tags in YAML frontmatter of skill/subagent bodies, OR hand-maintained `.claude/cascade-rules.yml`, OR LLM-based reference analysis. Future PRD.
- **OQ-3**: Whether to add a `R-SOURCE-CASCADE` reviewer rule replacing R-TRUTH-DOC at the skill/subagent level — deferred. The reviewer's existing R-SCOPE + R-BOY-SCOUT cover most cases.
- **OQ-4**: Whether to retire the calibrated `/audit-meta` rules from PR #336 (since their full mechanics inlined into SKILL.md from atomic notes) — handled in implementing PRD Slice 1 (atomic notes deleted; SKILL.md carries the patterns directly).
- **OQ-5**: Documentation for newcomers — should README rich onboarding grow further to compensate for retired topic syntheses? Future PRD if needed.
- **OQ-6**: Whether to retain `tools/` directory at all (or move `cascade-finder.py` elsewhere) — kept; `tools/` is a clean home for workflow tooling.
- **OQ-7**: Whether `glossary-add` + `glossary-fold` skills should be retired (they served the index-pattern glossary) — kept; they still work for the inline-glossary CLAUDE.md (add a term = add a bullet; fold = bulk add).

## Future direction

- **Workflow-only template stabilizes**: subsequent PRDs focus on workflow quality (more critics' rubrics refined, more hooks for safety, more pipeline robustness), not KB.
- **Separate KB project**: the user's external-content KB-building project lives elsewhere; this template can be one input to that project but is no longer the home.
- **cascade-finder Phase 2 (if proposed)**: precision mechanism per OQ-2.
- **`docs/memory/` (if proposed)**: legitimate KB use cases per OQ-1.
- **`R-SOURCE-CASCADE` rule (if proposed)**: per OQ-3.
- **CLAUDE.md cross-cutting rule #14 slot**: explicitly retired per D2; future ADRs may add rules at #15+.

## References

- 2026-05-29 session — user-driven evaluation of both architectures; session-end decision to eliminate the KB layer entirely
- Implementing PRD-W (posted alongside per ADR-0003 D8) — 4 slices: (1) inline load-bearing KB content into critics/skills/CLAUDE.md, (2) retire KB-dependent machinery, (3) delete `docs/` + update README/CLAUDE.md/cascade-finder, (4) this ADR-0032 + retire R-TRUTH-DOC + retire cross-cutting rule #14
- [ADR-0019](0019-best-practices-kb-pattern.md) D1+D2 — superseded entirely per Supersedes header
- [ADR-0022](0022-docs-first-kb-pattern.md) D1+D3 — superseded entirely
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1-D6 — superseded entirely
- [ADR-0031](0031-knowledge-architecture-v2.md) — superseded entirely (all 17 decisions D1-D17 retired with the KB substrate)
- [ADR-0017](0017-audit-meta-consolidation.md) D3 — DOCS-* rubric scope adjusted per D4
- [ADR-0018](0018-boy-scout-reviewer-rule.md) D2 — R-BOY-SCOUT trigger file set scope adjusted per D3
- [ADR-0024](0024-root-cause-workflow-capture-discipline.md) — CLAUDE.md rule #13 root-cause capture; preserved (workflow-only-friendly)
- [ADR-0028](0028-pretooluse-spec-gate.md), [ADR-0029](0029-stop-reviewer-signoff-gate.md), [ADR-0030](0030-windows-gitbash-hardening.md) — recent hooks; preserved
- [ADR-0033](0033-tooling-spawn-hook-scope.md) (dashboard tooling-spawn carveout), [ADR-0034](0034-build-orchestrator-and-generated-docs.md) (`/build` orchestrator + generated-docs currency — reconciled per D11; R-DOCS-CURRENT preserved; template relocated to repo root), [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) (parallel-dispatch worktree isolation) — all shipped 2026-05-29/30, all preserved, none KB-coupled
- [decisions/README.md](README.md) "What an ADR is" — ADR immutability rule honored per D10
- Karpathy LLM Wiki (April 2026), Zettelkasten (Luhmann), SKOS/RDF, "Infinite Brain" YouTube pattern — sources cited in ADR-0031 §Context for the original architectural choice; this ADR's reversal does not invalidate those sources, only the architectural inference for this project's scale
- PR #339 (cascade-finder MVP, merged 2026-05-29) — substrate-change addressed per D6
- PR #336 (/audit-meta calibration, merged 2026-05-29) — rubric-scope adjustment per D4
