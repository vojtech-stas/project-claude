# ADR-0019: External-content ingestion pattern + `docs/best-practices/` doc tree

- **Status:** Accepted
- **Date:** 2026-05-21
- **Supersedes:** none
- **Extends:** [ADR-0001](0001-foundational-design.md) D8 (orientation artifacts — adds `docs/best-practices/` as a new doc tree alongside `CLAUDE.md`, `README.md`, `decisions/`); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc check — KB README is a new cascade-doc target); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 (bootstrap.sh — adds yt-dlp install-check); [ADR-0011](0011-subagent-quality-framework.md) D5 (single-Markdown-report precedent — KB entries follow a similar "tracked human-readable artifact" model).

## Context

PRD-12 (the PRD this ADR ships alongside) implements Phase 1 of backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128): a fetch+distill+store pipeline for incorporating Anthropic-authoritative external content (starting with `@claude` + `@anthropic-ai` YouTube channels) into a referenceable knowledge base under `docs/best-practices/`.

Today (2026-05-21) two concrete incidents motivate the external-anchor need:

1. PR #134 shipped Claude Code hooks with INCORRECT schema (caught only at runtime dogfood via PR #135 fix). Had we read Anthropic's own hook-tutorial videos first, we would have shipped correct schema in PR #134 — avoiding a full fix-cycle.
2. PRD evolution across 11+ shipped PRDs has produced internally-consistent patterns but no external validation that those patterns match Anthropic's own Claude Code guidance.

This ADR locks the Phase 1 pattern. Phase 2 (audit-against-bp skill) and Phase 3 (apply-recommendations PRDs) are future PRDs per D8 below.

## Decisions

### D1: External-content ingestion pattern — fetch → distill → store as referenceable .md

Project adopts a 3-step pipeline for incorporating external authoritative content:

1. **Fetch** raw source (transcript, doc, blog post) to `docs/best-practices/transcripts/` (or equivalent audit-trail location).
2. **Distill** raw source via the encapsulating skill (per D4) into a concise referenceable artifact.
3. **Store** distilled artifact under `docs/best-practices/<slug>.md` with explicit authority citation back to the source.

Distilled artifacts are tracked git-versioned canonical references. Raw source is tracked for citation audit-trail + re-distillation safety if the distill prompt improves.

### D2: New doc tree `docs/best-practices/`

A new top-level doc tree separate from `decisions/` (ADRs), future `docs/prds/` (PRDs), and root-level docs (`CLAUDE.md`, `README.md`). Structure:

- `docs/best-practices/README.md` — KB structure + authority sources + how-to-add
- `docs/best-practices/<topic-slug>.md` — distilled entries (each cites source video timestamp range)
- `docs/best-practices/transcripts/<video-id>.vtt` — raw fetched transcripts (audit trail)

Distilled .md files are the canonical referenceable artifacts; raw transcripts are not directly referenced in CLAUDE.md or other ADRs. Authority chain: video → raw .vtt → distilled .md.

### D3: yt-dlp as fetch tool for YouTube content

YouTube transcript fetch uses `yt-dlp --skip-download --write-auto-subs --sub-format vtt --sub-lang en`. Documented in bootstrap.sh as warn-only required dep (no auto-install — cross-platform package-manager complexity is a rabbit-hole). Rationale: actively maintained, handles auto-captions + PoToken, single-binary install, no API auth burden.

Future external sources (blog posts, docs, transcripts from other platforms) may use other fetch tools — yt-dlp is the YouTube-specific tool, not the general external-content fetch standard. The standard is "fetch raw with whatever tool fits, store under audit trail, distill via skill".

### D4: `/distill-video` skill encapsulates the YouTube distill prompt

Per CLAUDE.md rule #7 (practices colocated in own body). Single skill `.claude/skills/distill-video/SKILL.md` = single source of truth for the YouTube distill prompt. Future iteration happens by editing one SKILL.md. Skill input: YouTube video ID. Skill output: writes raw `.vtt` to transcripts dir + writes distilled `.md` to KB dir. Tool boundaries: Bash (yt-dlp shell-out), Read, Write.

Future ingestion patterns for other external sources may add sibling skills (e.g., `/distill-blogpost`) — each gets its own SKILL.md. The pattern is "one skill per fetch-tool + distill-prompt pair", not "one mega-distill skill".

### D5: Walking-skeleton scope — slice 1 cuts through every layer + ONE video distilled

Per ADR-0001 D10 (walking-skeleton) and CLAUDE.md rule #2: slice 1 of the implementation PRD MUST cut through every layer — bootstrap.sh + skill + doc tree + ADR + Map row + README cascade-doc + at least ONE video distilled. Horizontal layering ("infrastructure-only slice 1, video distillation in slice 2") is forbidden — slice 1 produces a real `.md` to prove the pipeline ran end-to-end. Slice 2 extends to the remaining 4 curated videos.

### D6: Manual re-fetch cadence only — no auto-scheduler

`/distill-video <id>` is invoked manually per video. No periodic scheduler, no GitHub Action, no cron job. Rationale: walking-skeleton; auto-cadence is genuinely YAGNI for a 5-video KB. If dogfood proves manual cadence too slow once the KB scales beyond ~20 entries, a future PRD adds auto-fetch infrastructure (likely scheduled GitHub Action once backlog #63 CI lands).

### D7 (bootstrap-mode per [ADR-0004](0004-bypass-prevention.md) D2)

The fetch+distill+store pattern binds **FORWARD from slice-1 merge**. No retroactive ingestion of pre-existing external sources (e.g., the Matt Pocock skills repo per the user's reference memory — out of scope until a separate PRD chooses to ingest it). Future external-source PRDs may extend this pattern but must declare their own bootstrap-mode policy.

Future blocking variants of this pattern (e.g., a reviewer rule requiring every new ADR to cite a `docs/best-practices/` source if applicable) would require their own bootstrap-mode policy in the ADR that introduces them; this ADR does NOT pre-emptively gate any merges.

### D8: Phase-relationship to backlog #128 + sibling backlog items

- **#128 Phase 2 (audit-against-bp skill)** — deferred future PRD; natural extension of [ADR-0011](0011-subagent-quality-framework.md)'s `/audit-subagents` skill. Phase 2's audit-against-bp rubric will consume the `docs/best-practices/<slug>.md` artifacts this ADR produces.
- **#128 Phase 3 (apply-recommendations PRDs)** — deferred per-finding future PRDs. May supersede current ADRs (e.g., [ADR-0005](0005-output-shape-and-slicing-methodology.md) output shapes, [ADR-0009](0009-discipline-tightening.md) mindset framing) IF best-practices conflict surfaces with current patterns. Phase 3 PRDs author their own supersession headers per `decisions/README.md` immutability rules.
- **Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) (post-PRD audit cadence)** — independent; cadence half waits on backlog #63 CI per [ADR-0018](0018-boy-scout-reviewer-rule.md) D7.
- **Backlog [#70](https://github.com/vojtech-stas/project-claude/issues/70) (improver-critic pair)** — independent domain (source-code improvement, not external-content ingestion).

## Consequences

### Positive

- **External anchor for project conventions** — Phase 2 audit-against-bp lands as natural follow-up; Phase 3 applies recommendations.
- **Walking-skeleton-pure** — slice 1 ships ONE distilled video end-to-end; slice 2 extends to 4 more. Iterative learning instead of big-bang.
- **Re-distillation safety** — raw transcripts kept; if distill prompt improves, can re-run cheaply.
- **Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap** — no new critic added; quality validation is manual for Phase 1.
- **No new infrastructure surface** beyond yt-dlp dep — reuses existing skill + Bash + Write tools.

### Negative / Accepted

- **yt-dlp as external dep** — accepted; warn-only check in bootstrap.sh keeps friction low. If yt-dlp breaks (YouTube API changes), pipeline halts gracefully.
- **Manual distillation quality** — no automated quality validation in Phase 1; user manually reviews distilled .md files. Accepted because automated quality is a Phase 2/3 concern (audit-against-bp skill).
- **Scope drift risk** — 50-65 curated videos exists; resisting "just distill them all" requires discipline. Mitigated by D5 walking-skeleton lock + Phase-PRD decomposition.
- **`docs/best-practices/` becomes an [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D7 surfacing-convention concern over time** — when KB grows, glossary terms emerging from KB entries should be surfaced via `/glossary-add`. Deferred until pattern materializes.

## Alternatives considered

- **Alt-A: YouTube Data API instead of yt-dlp** — rejected; OAuth burden + per-day quota; yt-dlp avoids both.
- **Alt-B: Manual download + commit transcripts directly** — rejected; not automatable; can't easily re-distill across many videos.
- **Alt-C: Single mega-PRD covering Phases 1-3** — rejected; PRDs are feature-sized per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1; Phase 2/3 are distinct features.
- **Alt-D: Store KB content in CLAUDE.md directly** — rejected; CLAUDE.md is for project conventions, not external-source distillations; would bloat the auto-loaded context.
- **Alt-E: Store KB content in `decisions/`** — rejected; ADRs are immutable project-decisions; KB entries are mutable distillations of external sources (re-distillation may update content).
- **Alt-F: Use a single `/distill-content` skill parameterized by source-type** — rejected; YAGNI for one fetch tool; sibling skills as new sources land is cleaner per D4 future direction.
- **Alt-G: Add a `distill-critic` subagent for quality gating** — rejected; breaches [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap without justification; manual review for Phase 1, audit-against-bp skill for Phase 2.
- **Alt-H: Auto-install yt-dlp in bootstrap.sh** — rejected; cross-platform package-manager complexity (npm/brew/winget/apt vary); warn-only check + user-installed yt-dlp is correct boundary.
- **Alt-I: Skip raw transcripts, distill-only storage** — rejected; loses citation audit trail + can't re-distill cheaply if prompt improves; small storage cost is worth it.
- **Alt-J: Ship the full 50-video curated subset in one PRD** — rejected; violates walking-skeleton + R-LOC; future PRDs expand scope organically.

## Open questions deferred

- **Distilled-content versioning when prompts evolve** — overwrite vs version-stamp on re-distillation? Defer until first re-distillation actually happens.
- **VTT-encoding edge cases for some videos** — surfaced if hit during slice 1-2; not pre-empted.
- **R-BOY-SCOUT trigger path expansion to `docs/best-practices/*.md`** — future [ADR-0018](0018-boy-scout-reviewer-rule.md)-supersession PRD if patterns warrant it.
- **Cross-video deduplication infrastructure** — observe organically in slice 2; don't pre-emptively build.

## Future direction

- **Phase 2 (audit-against-bp skill)** — extends [ADR-0011](0011-subagent-quality-framework.md) `/audit-subagents`; consumes this ADR's `docs/best-practices/` artifacts.
- **Phase 3 (apply-recommendations PRDs)** — per-finding future PRDs; may supersede [ADR-0005](0005-output-shape-and-slicing-methodology.md) / [ADR-0009](0009-discipline-tightening.md) if best-practices conflict surfaces.
- **Auto-fetch cadence PRD** — schedule yt-dlp via GitHub Action post-#63 CI; depends on dogfood proving manual cadence too slow.
- **Sibling distill-* skills** — `/distill-blogpost`, `/distill-docs-page`, etc., as external-source diversity grows.

## References

- [ADR-0001](0001-foundational-design.md) D8 (orientation artifacts — extended), D10 (walking-skeleton — cited in D5)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 (PRD shape), D8 (macro-ADRs ship with PRD)
- [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D7)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D3 (cascade-doc check — KB README is a new cascade-doc target)
- [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) D7 (surfacing convention — relevant for future glossary terms emerging from KB)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 (bootstrap.sh — adds yt-dlp install-check), D7 (6-critic-cap honored)
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2/D5 (slice-1 walking-skeleton implementer dispatch)
- [ADR-0011](0011-subagent-quality-framework.md) D5 (single-Markdown-report precedent), Phase 2 candidate
- [ADR-0018](0018-boy-scout-reviewer-rule.md) D2 (trigger paths — future expansion to `docs/best-practices/*.md` deferred)
- Backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128) — multi-phase parent
- Anthropic YouTube: https://www.youtube.com/@claude/videos + https://www.youtube.com/@anthropic-ai/videos
