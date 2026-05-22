# ADR-0022: Docs-first per-topic best-practice skills + Phase 2' audit pattern

- **Status:** Accepted
- **Date:** 2026-05-22
- **Supersedes:** [ADR-0019](0019-best-practices-kb-pattern.md) D3 — specifically the yt-dlp-invocation text *"YouTube transcript fetch uses `yt-dlp --skip-download --write-auto-subs --sub-format vtt --sub-lang en`. Documented in bootstrap.sh as warn-only required dep"*. **D1 (fetch-distill-store 3-step pipeline) and D2 (`docs/best-practices/` tree structure) of ADR-0019 REMAIN IN FORCE** — only the mechanism-specific D3 bits are superseded.
- **Extends:** [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical/grep-only rubric pattern reused for future PRD-D `/audit-against-best-practices`); ADR-0011 D5 (single-Markdown-report advisory-only precedent reused); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap honored — best-practice skills + audit are skills, not subagents).

## Context

The project's KB initiative (backlog #128) pivoted 2026-05-22 from video-first (PRD #147 + killed PRD #171) to docs-first. Rationale: video distillations are Tier-3 noisy source. Official `docs.claude.com` is Tier-1. User feedback memory `feedback_source_priority.md` codifies the source-priority heuristic; user explicit ask: best-practices should be on-demand-loaded (matches Anthropic's own Skills guidance per slice #152 distillation). This ADR codifies the per-topic-skill + on-demand-loading pattern, preserves existing /distill-video + 5 video distillations as Tier-3 supplementary, and surgically supersedes ADR-0019 D3's yt-dlp-specific mechanism.

## Decisions

### D1: Per-topic best-practice skill body shape

Each `.claude/skills/best-practice-<topic>/SKILL.md` has 4 mandatory sections:

1. **Authoritative guidance** (from docs.claude.com): numbered list of rules; each rule has:
   - `**Rule:**` statement (1-2 sentences imperative)
   - `**Why:**` rationale (1 sentence)
   - `**Grep:**` regex pattern (optional; grep-compatible)
   - `**Target:**` glob pattern (optional; matches project files)
   - `**Authority:**` citation (docs.claude.com URL + section)

2. **Supplementary** (from existing video distillations under `docs/best-practices/`): pointers to per-video .md files (Tier 3 per D2).

3. **How to apply to this project**: concrete checks against current project files.

4. **Common pitfalls**: anti-patterns from docs + historical lessons.

**Audit-hook schema (for PRD-D `/audit-against-best-practices`):** `**Grep:**` field is grep-compatible regex; `**Target:**` field is glob pattern matching project files. Both fields mechanically parseable. PRD-D's audit skill greps Target paths for Grep patterns + reports PASS/FAIL per rule. Rules without both Grep+Target are judgment-only (excluded from mechanical audit). Extends [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical/grep-only rubric pattern) + D5 (advisory-only single-Markdown-report precedent).

### D2: Source tier priority

- **Tier 1**: `docs.claude.com` — structured, stable URLs, Anthropic-maintained.
- **Tier 2**: `anthropic.com/news` + `anthropic.com/research`. Future PRDs.
- **Tier 3**: video distillations under `docs/best-practices/` (PRD #147 artifacts). Demoted from primary to supplementary.

### D3: Per-topic skill location convention

`.claude/skills/best-practice-<topic>/SKILL.md` where `<topic>` ∈ {`workflow`, `subagents`, `hooks`, `claude-md-conventions`, `prompt-patterns`} (extensible). The PRD-14/#171 enumeration included a "skills" token; **removed from this ADR** to avoid recursive naming.

### D4: Audit consumability

Already defined in D1's audit-hook schema. PRD-D's `/audit-against-best-practices` skill is the consumer (matches /audit-subagents + /audit-meta pattern per ADR-0011 D5).

### D5: Hand-curated ingest

Each per-topic PRD's slice-1 implementer manually fetches via curl/Bash (implementer tool boundary doesn't include WebFetch) + distills rules + authors skill body per D1 spec. No shared `/distill-doc` helper in tier 1 (YAGNI).

### D6: Manual cadence + overwrite-on-rerun

Best-practice skill bodies static after authoring. On docs.claude.com updates, implementer manually re-fetches + overwrites in fresh PR. Matches [ADR-0019](0019-best-practices-kb-pattern.md) D6 /distill-video cadence.

### D7: ADR strategy across KB+audit PRDs

ONE foundational ADR-0022 in PRD-A. PRDs B + C extend without new ADRs (no novel decisions). PRD-D may have **its own ADR** if needed (numbering at-acceptance per ADR-0001 D8; no pre-allocation). PRDs E + F per scope.

### D8: Execution sequencing

Follows [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D3 DAG-batched dispatch. No new mechanism introduced. Dependency graph: PRD-A first; B + C parallel after A; D after A+B+C; E + F independent.

### D9: Existing video distillations preserved in place

**Existing 5 video distillations under `docs/best-practices/` are preserved in place — NOT migrated, NOT deleted, NOT modified by this ADR.** Existing /distill-video skill at `.claude/skills/distill-video/` is preserved as-is. ADR-0019 D2's `docs/best-practices/` tree structure REMAINS IN FORCE.

What changes: each new best-practice-<topic> skill body (D1) cites relevant video distillations in its "Supplementary" section per the Tier 3 demotion declared in D2.

### D10 (bootstrap-mode per [ADR-0004](0004-bypass-prevention.md) D2)

Binds FORWARD from slice-1 merge of PRD-A. Future PRDs (B/C/D/E/F) inherit the pattern. Future blocking variants declare own bootstrap-mode policy in introducing ADR; this ADR does NOT pre-emptively gate any merges.

### D11 (supersession of [ADR-0019](0019-best-practices-kb-pattern.md) D3, yt-dlp-specific bits only)

ADR-0019 D3 reads: *"YouTube transcript fetch uses `yt-dlp --skip-download --write-auto-subs --sub-format vtt --sub-lang en`. Documented in bootstrap.sh as warn-only required dep (no auto-install — cross-platform package-manager complexity is a rabbit-hole)."*

**Superseded** by: **fetch mechanism varies by source-tier** — videos use yt-dlp (existing /distill-video; preserved); docs use hand-curl (per D5); future external sources use whatever tool fits.

**ADR-0019 D1 (fetch-distill-store 3-step pipeline) and D2 (`docs/best-practices/` tree structure) REMAIN IN FORCE.** Surgical supersession. ADR-0019 status flips to "Accepted (D3 superseded by ADR-0022 D11)" per `decisions/README.md` immutability rules.

## Consequences

### Positive

- Closes wrong-source-priority error from earlier 2026-05-22 pivot.
- Zero CLAUDE.md bloat (on-demand-loaded skills).
- 5-6 future PRDs unblocked (clean DAG per D8).
- Audit consumability built-in (Grep+Target schema in D1 extends ADR-0011 D2's mechanical precedent).
- Honors ADR-0008 D7 6-critic-cap (skills not subagents; no new critics).
- Backward-compatible (D11 surgical; D9 preserves video pipeline).

### Negative / Accepted

- Hand-curated ingest (per-PRD implementer effort; mitigated by D1 explicit spec).
- Implementer needs curl workaround (acceptable per §5 PRD note).
- No shared topic-content extraction (small duplication if pages cited from multiple skills).
- D11 supersession adds ADR-history complexity (mitigated by D-ID-level + README footnote).

## Alternatives considered

- **Alt-A: Single shared `/best-practices` skill** — rejected per **Q2=2A** (auto-routing via per-skill descriptions cleaner).
- **Alt-B: Live-fetch via WebFetch every invocation** — rejected per **Q2=2A** (slow + expensive + no offline).
- **Alt-C: Store as `.md` under `docs/best-practices/sources/`** — rejected per **Q2=2A** (doesn't address CLAUDE.md-bloat concern).
- **Alt-D: One mega-PRD covering all topics + audit + cleanups** — rejected per **Q4=4A** (violates ADR-0003 D1 one-feature-per-PRD).
- **Alt-E: ADR per PRD (0022/0023/0024 for workflow/subagents/hooks)** — rejected per **Q5=5A** (80% duplication).
- **Alt-F: Audit as semantic LLM-judgment** — rejected per **Q7=7A** (non-deterministic; contradicts ADR-0011 D2).
- **Alt-G: Auto-capture audit findings as backlog items** — rejected per **Q8=8A** (noise dump; advisory-only matches ADR-0011 D5).
- **Alt-H: Strict sequential PRD execution** — rejected per **Q9=9A** (3x slower; B + C genuinely independent).
- **Alt-I: Shared `/distill-doc` helper skill in tier 1** — rejected per **Q10=10A** (YAGNI).
- **Alt-J: Delete existing video distillations as superseded** — rejected per **D9** (Tier-3 supplementary value).

## Open questions deferred

- Specific docs.claude.com URLs per topic — settled in PRD-A §5 (6 committed seed URLs).
- Future /distill-doc shared helper skill — defer.
- Tier 2 article ingestion — future PRD.
- PRD-D/E/F specifics — own grill cycles.
- Auto-fire post-CI #63 — future PRD.

## Future direction

- PRDs B + C parallel-dispatch after A merges
- PRD-D Phase 2' audit
- PRDs E + F cleanups
- Tier 2 ingestion PRDs
- /distill-doc shared helper PRD if refresh-friction surfaces
- Auto-fire cadence post-CI #63

## References

- [ADR-0001](0001-foundational-design.md) D8 (ADR numbering at-acceptance)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap honored)
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D3 (DAG-batched per D8)
- [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical/grep-only audit pattern extended into D1 schema), D5 (advisory-only single-report precedent), D7 (audit scope `.claude/agents/*.md` only — explains why PRD-A §2 C7 uses skill-targeted SKILL-1/2/3 checks not /audit-subagents)
- [ADR-0019](0019-best-practices-kb-pattern.md) D1 + D2 (preserved per D11), D3 (superseded per D11), D6 (manual cadence matched per D6)
- [ADR-0020](0020-qa-automation-writer-executor.md) D2 (LLM-extract trade-off precedent)
- Backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128) — multi-phase KB parent
- Closed PRD [#147](https://github.com/vojtech-stas/project-claude/issues/147) — Tier-3 video source
- Closed PRD [#171](https://github.com/vojtech-stas/project-claude/issues/171) — killed Phase 1.5 video-synthesis
- User memory `feedback_source_priority.md`
- User memory `feedback_grill_bulk_not_micro.md`
