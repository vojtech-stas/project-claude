# Best-practices knowledge base

A curated, referenceable knowledge base of distilled best-practice recommendations from Anthropic-authoritative external sources. Established by [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) as Phase 1 of the multi-phase backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128) initiative.

## Why this exists

The project's subagents, skills, and CLAUDE.md conventions evolved organically across many shipped PRDs. They are internally consistent, but no external best-practice anchor validates them against Anthropic's own published Claude Code guidance. A concrete cost was paid by PR #134 shipping Claude Code hooks with the wrong schema — a defect caught only at runtime dogfood (PR #135 fix), which a written distilled reference from Anthropic's own hook-tutorial videos would have prevented.

This KB is that external anchor. Each entry is a distilled best-practice recommendation set extracted from one authoritative source (currently YouTube videos from `@claude` + `@anthropic-ai`), with a full citation back to the original so any disputed point can be re-verified.

## Structure (per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D2)

```
docs/best-practices/
├── README.md                                          # This file
├── <kebab-title-up-to-60-chars>-<video-id>.md         # Distilled entries (canonical referenceable artifacts)
├── ...                                                # one .md per source
└── transcripts/
    └── <video-id>.vtt                                 # Raw fetched transcripts (audit trail)
```

**Authority chain:** video → raw `.vtt` → distilled `.md`. Distilled `.md` files are the canonical artifacts referenced from `CLAUDE.md`, ADRs, and PR discussions; raw transcripts exist for citation audit and re-distillation if the distill prompt improves.

**Slug convention** (locked per ADR-0019 D2 + PRD-12 §5): kebab-cased video title truncated to ≤60 chars, with the video ID appended as suffix. Example: `code-with-claude-london-2026-opening-keynote-6amLO7I9xdg.md`. The video-ID suffix guarantees uniqueness even if two videos share a title.

## Authority sources (in scope)

Per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) + PRD-12 §3:

- **`@claude`** YouTube channel — https://www.youtube.com/@claude/videos
- **`@anthropic-ai`** YouTube channel — https://www.youtube.com/@anthropic-ai/videos

Other channels (community, third-party tutorials, conference recordings outside Anthropic events) are **out of scope** for this KB. Ingesting them would require its own authority rationale + a separate PRD.

## How to add a new entry

Use the `/distill-video` skill (see [`.claude/skills/distill-video/SKILL.md`](../../.claude/skills/distill-video/SKILL.md)):

```
/distill-video <youtube-video-id>
```

The skill fetches the raw `.vtt` to `transcripts/`, distills it into a Markdown entry at the slug path above, and emits the canonical [GENERATOR trailer](../../decisions/0005-output-shape-and-slicing-methodology.md) for downstream parsing.

**Prerequisites:** `yt-dlp` must be on `PATH`. `bootstrap.sh` step 6 warns when it is missing; install with `pip install yt-dlp`, `winget install yt-dlp.yt-dlp` (Windows), or `brew install yt-dlp` (macOS) before running the skill.

**Edge cases:** if the target video has no available auto-captions or its VTT is malformed, the skill exits non-zero with a clear stderr message — it does NOT silently emit a placeholder entry. Re-runs of `/distill-video <id>` overwrite the existing `.md` (no versioning in Phase 1; future PRD if demand surfaces).

## What this KB deliberately is NOT

- **Not a comprehensive video archive.** Only curated, distilled-with-intent entries land here. The raw transcripts directory is an audit trail for the distilled entries, not a bulk video dump.
- **Not auto-updated.** Per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D6, ingestion is manual via `/distill-video`. No scheduler, no GitHub Action, no cron. Auto-cadence is a future PRD once the KB outgrows manual maintenance.
- **Not gated by a critic.** Per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) Alt-G + the [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap, no `distill-critic` subagent exists. Quality validation is manual user review in Phase 1; Phase 2 (the future `audit-against-bp` skill per backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128)) will consume entries here against project conventions.
- **Not the only source of project conventions.** `CLAUDE.md` + `decisions/*.md` remain the binding sources; this KB is the external validation/inspiration layer. When a KB recommendation conflicts with a current ADR, a Phase 3 PRD authors an explicit supersession ADR — the KB entry alone does not change project rules.

## Phase relationship to backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128)

- **Phase 1 (this KB)** — fetch+distill+store pipeline + initial curated entries. Currently active.
- **Phase 2** — `audit-against-bp` skill that compares project artifacts against the distilled entries here, surfacing findings for human review. Future PRD.
- **Phase 3** — per-finding `apply-recommendations` PRDs that may supersede current ADRs when a best-practice conflict surfaces. Future per-finding PRDs.

See [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md) D8 for the full phase-relationship matrix.
