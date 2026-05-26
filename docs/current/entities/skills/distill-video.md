---
title: distill-video — YouTube transcript → best-practices KB entry pipeline (per ADR-0019)
summary: Two-phase actionable wrapper (Fetch then Distill) around yt-dlp; takes a YouTube video ID, fetches the raw .vtt into docs/best-practices/transcripts/, distills a Markdown entry at docs/best-practices/<slug>-<video-id>.md following the slug + authority-chain conventions of ADR-0019; re-runs overwrite both artifacts.
tags: [skill, kb, generator, distill-video]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/distill-video/SKILL.md
  - decisions/0019-best-practices-kb-pattern.md
---

# /distill-video

The `/distill-video` skill is the **actionable wrapper around the fetch → distill → store pipeline** established by [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md). It encapsulates the YouTube-specific fetch tool (`yt-dlp`), the distill prompt, and the slug/citation conventions so the pattern stays a single source of truth per CLAUDE.md rule #7 (practices colocated).

## Role and responsibility

`/distill-video` runs in two phases:

### Phase 1 — Fetch
1. **Sanity check `yt-dlp`** — exit non-zero with installation guidance if missing. The `bootstrap.sh` warn-only check is for fresh-clone setup; the skill HARD-fails because it cannot proceed without the tool.
2. **Fetch raw transcript** to `docs/best-practices/transcripts/<video-id>.vtt` using the canonical yt-dlp command (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D3); rename the `<video-id>.en.vtt` output to strip the `.en` infix.
3. **VTT sanity check** — verify the file exists, is non-empty, starts with `WEBVTT`, and contains at least one timestamp cue. ANY failure → exit non-zero with a specific stderr message; do NOT proceed to Phase 2 with a malformed VTT.
4. **Fetch metadata** — title, uploader (channel), upload date, duration — for the citation block.

### Phase 2 — Distill
5. **Compute slug** per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D2: lowercase title; strip punctuation except spaces+hyphens; collapse whitespace; replace spaces with `-`; truncate to ≤60 chars at a word boundary; append `-<video-id>` suffix for uniqueness.
6. **Distill** the VTT into a Markdown artifact with intro paragraph (2-4 sentences naming video / channel / date / duration / URL / identified speakers), **5-10 bulleted best-practice recommendations** (imperative + `(HH:MM:SS)` timestamp citation + 1-2 sentences of context), and an authority block (Source URL + Channel + Upload date + Duration + Raw transcript link + Distilled-by attribution).
7. **Write the distilled `.md`** wholesale via `Write` (re-runs OVERWRITE per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) PRD-12 §3 non-goal — no versioning in Phase 1).

## Invocation contract

- **Caller:** the user via `/distill-video <youtube-video-id>` with an 11-character YouTube video ID (e.g., `GMIWm5y90xA`).
- **Input:** one 11-char YouTube video ID. Missing or malformed → `RESULT: INVALID_INPUT`.
- **Output:** two tracked artifacts (raw `.vtt` + distilled `.md`) plus the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) with `VIDEO_ID` and `SLUG` per-agent extensions.
- **Tool boundaries:** `Read` (VTT contents + existing distilled files), `Write` (distilled `.md` only), `Bash` (yt-dlp shell-out + rename + sanity-check greps). Forbidden: `Edit` (overwrite model), `Agent` (no recursive invocation; no `distill-critic` per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) Alt-G + [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap), `gh issue create` / `gh pr create` (the user commits + opens the PR), `WebFetch` (yt-dlp handles all network I/O).

## Default-conservative — fail loudly on malformed VTT

When the raw VTT is malformed, missing, or empty, the skill exits non-zero with a clear stderr message — it does NOT silently emit a placeholder `.md`. Per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) open question on VTT-encoding edge cases: surface the failure mode, don't hide it. Same discipline when the video has no captions available at all (operationally indistinguishable from a malformed-VTT outcome from the user's perspective).

## Authority chain (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D2)

`video → raw .vtt (audit trail) → distilled .md (canonical referenceable artifact)`. Both are tracked git artifacts; the raw VTT is kept for re-distillation safety if the prompt improves. Scope is locked to `@claude` + `@anthropic-ai` channels per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md); other channels need separate authority rationale + a separate PRD.

## Relationship to other skills and agents

- **Consumed by** the on-demand best-practice skills ([`best-practice-workflow`](best-practice-workflow.md), [`best-practice-subagents`](best-practice-subagents.md), [`best-practice-hooks`](best-practice-hooks.md)) as Tier-3 supplementary references per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 + D9.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — no `distill-critic`; quality validation is manual user review per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) Alt-G.
- **Authority:** [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) — D1 (fetch→distill→store pattern), D2 (doc tree shape + authority chain), D3 (yt-dlp as fetch tool), D4 (one-skill-per-fetch-tool pattern), D5 (walking-skeleton scope), D6 (manual cadence), D7 (bootstrap-mode), Alt-G (no distill-critic), Alt-H (no auto-install yt-dlp), Alt-I (raw transcript kept).

## Edges

- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[entities/skills/best-practice-workflow]]
- **related_to:** [[entities/skills/best-practice-subagents]]
- **related_to:** [[entities/skills/best-practice-hooks]]
- **related_to:** [[concepts/glossary/generator-trailer]]
