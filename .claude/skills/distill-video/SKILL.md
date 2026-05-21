---
name: distill-video
description: Fetch a YouTube video transcript via yt-dlp and distill it into a referenceable best-practices entry under `docs/best-practices/`. Input is one YouTube video ID. Output is two tracked artifacts (raw `.vtt` + distilled `.md`) following the slug + authority-chain conventions of ADR-0019. Use when adding a new entry to the project's external-content KB from an authorized source (`@claude` or `@anthropic-ai` YouTube channels per ADR-0019 scope). Re-runs OVERWRITE both artifacts.
---

This skill is the actionable wrapper around the project's fetch → distill → store pipeline established by [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md). It encapsulates the YouTube-specific fetch tool (`yt-dlp`), the distill prompt, and the slug/citation conventions so the pattern stays a single source of truth per CLAUDE.md rule #7 (practices colocated).

**Authority chain** (per ADR-0019 D2): video → raw `.vtt` (audit trail) → distilled `.md` (canonical referenceable artifact). Both are tracked git artifacts; the raw VTT is kept for re-distillation safety if the prompt improves.

**Default conservative.** When the raw VTT is malformed, missing, or empty, the skill exits non-zero with a clear stderr message — it does NOT silently emit a placeholder `.md`. Per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) open question on VTT-encoding edge cases: surface the failure mode, don't hide it. The same exit-non-zero discipline applies when the video has no captions available at all (operationally indistinguishable from a malformed-VTT outcome from the user's perspective: no usable transcript → no honest distillation).

## When invoked

The user invokes `/distill-video <youtube-video-id>` with a single 11-character YouTube video ID (e.g., `GMIWm5y90xA`). The skill operates in two phases — Fetch then Distill — each with an explicit failure mode.

## Process

### Phase 1 — Fetch

1. **Sanity check yt-dlp** — `command -v yt-dlp` must return 0; if not, exit non-zero with stderr `"yt-dlp not on PATH; install per bootstrap.sh step 6 (pip install yt-dlp / winget install yt-dlp.yt-dlp / brew install yt-dlp)"`. (The warn-only check in `bootstrap.sh` is for fresh-clone setup; the skill HARD-fails because it can't proceed without the tool.)

2. **Fetch raw transcript** to `docs/best-practices/transcripts/<video-id>.vtt`. Canonical command (per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D3):

   ```bash
   yt-dlp --skip-download --write-auto-subs --sub-format vtt --sub-lang en \
     --output 'docs/best-practices/transcripts/%(id)s.%(ext)s' \
     "https://www.youtube.com/watch?v=<video-id>"
   ```

   yt-dlp emits the file as `<video-id>.en.vtt`; rename to `<video-id>.vtt` (strip the `.en` infix) so the on-disk shape matches the ADR-0019 D2 structure `transcripts/<video-id>.vtt`.

3. **VTT sanity check** — verify the renamed file:
   - exists, AND
   - is non-empty (`-s <path>`), AND
   - starts with `WEBVTT` on line 1 (literal grep), AND
   - contains at least one timestamp cue line (regex `^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3} --> `).

   If ANY of these fails → exit non-zero with stderr describing which check failed (e.g., `"VTT sanity: file empty"`, `"VTT sanity: missing WEBVTT header"`, `"VTT sanity: no timestamp cues found — likely no auto-captions available for this video"`). Do NOT proceed to Phase 2 with a malformed VTT.

4. **Fetch metadata** for the distilled artifact's citation block:

   ```bash
   yt-dlp --print "%(title)s|%(uploader)s|%(upload_date)s|%(duration)s" \
     "https://www.youtube.com/watch?v=<video-id>"
   ```

   Capture title, uploader (channel), upload date (YYYYMMDD), duration (seconds). The title drives the slug; the rest populates the citation block.

### Phase 2 — Distill

5. **Compute slug** per ADR-0019 D2 + PRD-12 §5 convention:
   - Take the fetched title; lowercase it.
   - Strip punctuation EXCEPT spaces and hyphens; collapse runs of whitespace to single spaces; replace spaces with `-`; collapse runs of `-` to single `-`; trim leading/trailing `-`.
   - Truncate to **≤60 characters** at a word boundary (don't cut mid-word).
   - Append `-<video-id>` suffix to guarantee uniqueness.
   - Final shape: `docs/best-practices/<kebab-title-up-to-60-chars>-<video-id>.md`. Example: title `Code with Claude London 2026: Opening Keynote` + video ID `6amLO7I9xdg` → `code-with-claude-london-2026-opening-keynote-6amLO7I9xdg.md`.

6. **Read the VTT** via the `Read` tool (the file may be hundreds of KB for long talks; sample beginning + middle + end if the file exceeds the Read tool's default window).

7. **Distill** the VTT contents into a Markdown artifact. The distill prompt is intentionally MINIMAL (per PRD-12 §6 rabbit-hole — over-engineering distill sophistication is forbidden in Phase 1):

   - **Intro paragraph (2-4 sentences)**: name the video, the channel/uploader, the upload date, the duration, the YouTube URL. State who the speaker(s) appear to be if identifiable from the captions; if not, say "speaker not identified in auto-captions".
   - **5-10 bulleted best-practice recommendations** extracted from the transcript content. Each bullet:
     - States the recommendation as an imperative (e.g., "Build for emerging model capabilities, not just what works today").
     - Cites a `(HH:MM:SS)` timestamp where the recommendation is voiced in the video. If the recommendation spans multiple sections, cite the most representative single timestamp.
     - Adds 1-2 sentences of context paraphrasing what the speaker said and why it matters.
   - **Authority block** at the bottom (single-line each):
     - `**Source:** https://www.youtube.com/watch?v=<video-id>`
     - `**Channel:** <uploader>`
     - `**Upload date:** <YYYY-MM-DD>` (reformat from the YYYYMMDD yt-dlp emits)
     - `**Duration:** <H>h <M>m <S>s` (derived from the seconds count)
     - `**Raw transcript:** [`<video-id>.vtt`](transcripts/<video-id>.vtt)` (relative link)
     - `**Distilled by:** /distill-video skill (per [ADR-0019](../../decisions/0019-best-practices-kb-pattern.md))`

8. **Write the distilled `.md`** to the computed slug path via the `Write` tool. Re-runs OVERWRITE existing content (per PRD-12 §3 non-goal — no versioning in Phase 1).

9. **Emit the GENERATOR trailer** (below) with paths to both artifacts.

## Output format (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c)

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence>
ARTIFACTS: docs/best-practices/transcripts/<video-id>.vtt, docs/best-practices/<slug>-<video-id>.md
VIDEO_ID: <video-id>
SLUG: <slug>-<video-id>
```

- `RESULT: SUCCESS` — both files written, all sanity checks passed.
- `RESULT: STOPPED` — fetch failed (yt-dlp error, no captions available, malformed VTT). `REASON:` cites the specific failure; `ARTIFACTS:` may list a partial VTT if one was downloaded; the `.md` is NOT written.
- `RESULT: INVALID_INPUT` — the supplied argument is not an 11-char YouTube video ID, OR no argument was supplied.

`VIDEO_ID` and `SLUG` are per-agent extensions to the canonical trailer (per ADR-0005 D1c).

## Tool boundaries

Allowed: `Read` (for VTT contents + existing distilled files), `Write` (for the distilled `.md` only), `Bash` (for yt-dlp shell-out + the rename + the sanity-check greps).

Forbidden:
- **`Edit`** — distilled artifacts are written wholesale on each run (per re-distillation overwrite semantics); incremental edits would conflict with the overwrite model.
- **`Agent`** — this is a skill, not a critic; no recursive subagent invocation. Quality validation is manual user review in Phase 1 (per ADR-0019 + the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap rejecting a `distill-critic`).
- **`gh issue create`** / **`gh pr create`** — the skill writes tracked files but does NOT open a PR or issue. The user (or a future orchestrator) commits + opens the PR.
- **`WebFetch`** — yt-dlp handles all network I/O; no direct HTTP fetches from the skill body.

## What this skill deliberately does NOT do

- Does NOT auto-install yt-dlp (per ADR-0019 Alt-H rejection — cross-platform package-manager complexity is a rabbit-hole; `bootstrap.sh` warns only).
- Does NOT auto-fetch new videos on a cadence (per ADR-0019 D6 — manual `/distill-video <id>` only; auto-fetch is a future PRD post-#63 CI).
- Does NOT validate the distilled `.md` quality with an LLM judge (per ADR-0019 Alt-G rejection — Phase 1 manual review only; Phase 2's `audit-against-bp` skill is the future quality layer).
- Does NOT version distilled content on re-distillation (per PRD-12 §3 non-goal — overwrite semantics; future PRD if version-stamping demand surfaces).
- Does NOT verify YouTube timestamp citations against the live video (per PRD-12 §6 rabbit-hole — best-effort in prompt; no curl-based link-validity checker).
- Does NOT support fetch sources other than YouTube (per ADR-0019 D4 — sibling skills like `/distill-blogpost` are the pattern for other sources, not parameter-extension of this one).
- Does NOT ingest videos from channels outside `@claude` + `@anthropic-ai` (per ADR-0019 + PRD-12 §3 — other channels need their own authority rationale + separate PRD).
- Does NOT touch `CLAUDE.md`, `decisions/README.md`, or other index docs — the user commits the distilled `.md` and updates any cascade-doc indices in the same PR.

## References

- [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) — D1 (fetch→distill→store pattern), D2 (doc tree shape + authority chain), D3 (yt-dlp as fetch tool), D4 (one-skill-per-fetch-tool pattern), D5 (walking-skeleton scope), D6 (manual cadence), D7 (bootstrap-mode), Alt-G (no distill-critic), Alt-H (no auto-install), Alt-I (raw transcript kept).
- [ADR-0001](../../../decisions/0001-foundational-design.md) D8 (orientation artifacts — KB is a new doc tree alongside CLAUDE.md / README.md / decisions/), D10 (walking-skeleton — slice 1 ships one distilled video end-to-end).
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer shape this skill emits), D3 (cascade-doc check — KB README is a new cascade-doc target).
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D6 (bootstrap.sh hosts the warn-only yt-dlp check), D7 (6-critic-cap — no `distill-critic` here).
- `bootstrap.sh` step 6 — fresh-clone yt-dlp warn-only check.
- `docs/best-practices/README.md` — KB structure + authority sources + how to add a new entry via this skill.
- Backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128) — multi-phase parent (Phase 2 audit-against-bp + Phase 3 apply-recommendations are deferred future PRDs).
