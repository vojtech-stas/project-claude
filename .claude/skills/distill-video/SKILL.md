---
name: distill-video
description: Fetch a YouTube video transcript via yt-dlp and distill it into a referenceable best-practices entry under `docs/best-practices/`. Input is one YouTube video ID. Output is two tracked artifacts (raw `.vtt` + distilled `.md`) following the slug + authority-chain conventions of ADR-0019. Use when adding a new entry to the project's external-content KB from an authorized source (`@claude` or `@anthropic-ai` YouTube channels per ADR-0019 scope). Re-runs OVERWRITE both artifacts.
---

# /distill-video — YouTube transcript → best-practices KB entry

Actionable wrapper around the project's fetch → distill → store pipeline established by [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md). Encapsulates the YouTube-specific fetch tool (`yt-dlp`), the distill prompt, and the slug/citation conventions so the pattern stays a single source of truth per CLAUDE.md rule #7.

**Authority chain** (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D2): video → raw `.vtt` (audit trail) → distilled `.md` (canonical referenceable artifact). Both are tracked git artifacts; the raw VTT is kept for re-distillation safety.

**Default conservative.** When the raw VTT is malformed, missing, or empty, the skill exits non-zero with a clear stderr message — it does NOT silently emit a placeholder `.md`.

Full role synthesis (two-phase contract, invocation contract, channel scope, edges): [entities/skills/distill-video](../../../docs/current/entities/skills/distill-video.md). Vocabulary: [generator-trailer](../../../docs/current/concepts/glossary/generator-trailer.md).

## When invoked

The user invokes `/distill-video <youtube-video-id>` with a single 11-character YouTube video ID (e.g., `GMIWm5y90xA`). The skill operates in two phases — Fetch then Distill — each with an explicit failure mode.

## Process

### Phase 1 — Fetch

1. **Sanity check yt-dlp** — `command -v yt-dlp` must return 0; if not, exit non-zero with stderr naming the installer (`pip install yt-dlp` / `winget install yt-dlp.yt-dlp` / `brew install yt-dlp`) per `bootstrap.sh` step 6.

2. **Fetch raw transcript** to `docs/best-practices/transcripts/<video-id>.vtt` (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D3):

   ```bash
   yt-dlp --skip-download --write-auto-subs --sub-format vtt --sub-lang en \
     --output 'docs/best-practices/transcripts/%(id)s.%(ext)s' \
     "https://www.youtube.com/watch?v=<video-id>"
   ```

   Rename the emitted `<video-id>.en.vtt` → `<video-id>.vtt` (strip `.en`) so the on-disk shape matches the [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D2 structure.

3. **VTT sanity check** — file exists AND non-empty AND starts with `WEBVTT` AND contains at least one `^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3} --> ` timestamp cue. ANY failure → exit non-zero with a specific stderr message; do NOT proceed to Phase 2.

4. **Fetch metadata** for the citation block:

   ```bash
   yt-dlp --print "%(title)s|%(uploader)s|%(upload_date)s|%(duration)s" "https://www.youtube.com/watch?v=<video-id>"
   ```

   Title drives the slug; the rest populates the citation block.

### Phase 2 — Distill

5. **Compute slug** per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D2: lowercase title → strip punctuation except spaces+hyphens → collapse whitespace → spaces→`-` → collapse runs of `-` → trim leading/trailing → truncate to ≤60 chars at a word boundary → append `-<video-id>` suffix. Final shape: `docs/best-practices/<slug>-<video-id>.md`.

6. **Read the VTT** via `Read`; for long talks (hundreds of KB) sample beginning + middle + end if the file exceeds the default window.

7. **Distill** into a Markdown artifact (prompt is intentionally MINIMAL per PRD-12 §6 — over-engineering distill sophistication is forbidden in Phase 1):
   - **Intro (2-4 sentences)**: name video, channel/uploader, upload date, duration, YouTube URL, identified speaker(s) (or "speaker not identified in auto-captions").
   - **5-10 bulleted recommendations**, each: imperative statement + `(HH:MM:SS)` timestamp citation + 1-2 sentences of context paraphrasing the speaker.
   - **Authority block** (single line each): `**Source:** <URL>` / `**Channel:** <uploader>` / `**Upload date:** YYYY-MM-DD` / `**Duration:** <H>h <M>m <S>s` / `**Raw transcript:** [<video-id>.vtt](transcripts/<video-id>.vtt)` / `**Distilled by:** /distill-video skill (per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md))`.

8. **Write the distilled `.md`** wholesale via `Write` to the computed slug path. Re-runs OVERWRITE (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) PRD-12 §3 — no versioning in Phase 1).

9. **Emit the GENERATOR trailer** below.

## Output format (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c, schema at [topics/output-shapes](../../../docs/current/topics/output-shapes.md))

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence>
ARTIFACTS: docs/best-practices/transcripts/<video-id>.vtt, docs/best-practices/<slug>-<video-id>.md
VIDEO_ID: <video-id>
SLUG: <slug>-<video-id>
```

- `SUCCESS` — both files written, all sanity checks passed.
- `STOPPED` — fetch failed (yt-dlp error, no captions, malformed VTT). `ARTIFACTS:` may list a partial VTT; the `.md` is NOT written.
- `INVALID_INPUT` — argument is not an 11-char YouTube video ID, or no argument supplied.

## Tool boundaries

**Allowed:** `Read` (VTT + existing distilled files), `Write` (distilled `.md` only), `Bash` (yt-dlp + rename + sanity-check greps).

**Forbidden:** `Edit` (overwrite model), `Agent` (no recursive invocation; no `distill-critic` per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) Alt-G + [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap), `gh issue create` / `gh pr create` (user commits + opens the PR), `WebFetch` (yt-dlp handles all network I/O).

## What this skill deliberately does NOT do

- Auto-install yt-dlp (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) Alt-H — `bootstrap.sh` warns only).
- Auto-fetch new videos on a cadence (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D6 — manual `/distill-video <id>` only).
- LLM-judge the distilled `.md` (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) Alt-G — Phase 1 manual review only).
- Version distilled content on re-runs (per PRD-12 §3 — overwrite semantics).
- Support fetch sources other than YouTube (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D4 — sibling skills like `/distill-blogpost` are the pattern for other sources).
- Ingest videos from channels outside `@claude` + `@anthropic-ai` (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) — other channels need their own authority rationale + separate PRD).
- Touch `CLAUDE.md`, `decisions/README.md`, or other index docs — the user commits the distilled `.md` and updates cascade-docs in the same PR.

## References

- Entity note (full role, invocation contract, edges): [entities/skills/distill-video](../../../docs/current/entities/skills/distill-video.md).
- [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) — D1 (fetch→distill→store), D2 (doc tree + authority chain), D3 (yt-dlp), D4 (one-skill-per-fetch-tool), D5 (walking-skeleton), D6 (manual cadence), D7 (bootstrap-mode), Alt-G (no distill-critic), Alt-H (no auto-install), Alt-I (raw transcript kept).
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR trailer shape.
- `docs/best-practices/README.md` — KB structure + authority sources + how to add a new entry via this skill.
