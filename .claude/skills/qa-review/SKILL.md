---
name: qa-review
description: Main-agent clearing skill for QA residuals (ADR-0040 D4). Lists open needs-human-check issues, presents each as an AskUserQuestion card (recommendation + PRO/CON inferred from the criterion), and records the verdict — accept closes the issue as verified; reject relabels and captures a defect. Tools: Read, Bash, AskUserQuestion only (NO Write/Edit/Agent). Emits a GENERATOR trailer.
---

# /qa-review — QA residual clearing skill

This skill runs in **main-agent context** (so it can call `AskUserQuestion`). It clears the async `needs-human-check` queue produced by `/qa-plan` when `qa-tester` returns `PROVISIONAL` residuals (criteria the machine could not faithfully verify). Per [ADR-0040](../../../decisions/0040-qa-human-residual-model.md) D4, this is the human's cadence-controlled checkpoint — not a blocking gate, not a synchronous prompt at plan time.

The `needs-human-check` label (color `#FBCA04`) identifies GitHub issues that contain a QA residual: a criterion the machine attempted but could not settle. Each issue links the parent PRD and states exactly what to eyeball. This skill fetches those issues, renders each as a rich `AskUserQuestion` card, and records the verdict.

## When to invoke

- After one or more features have been QA'd and `/qa-plan` reported `PROVISIONAL_COUNT ≥ 1` and a `RESIDUAL_HEADLINE`.
- At the human's cadence — not blocking; the PRD may already be closed.
- Optionally scoped to a single PRD: `/qa-review #<N>` filters to issues mentioning PRD #N.

## Process

1. **List open `needs-human-check` issues.**

   ```bash
   gh issue list --label needs-human-check --state open --json number,title,body,url
   ```

   If zero issues → emit `RESULT: SUCCESS`, `REASON: no open needs-human-check issues`, `RESIDUALS_CLEARED: 0`, `RESIDUALS_PENDING: 0`. Done.

   If a PRD filter was given (`/qa-review #<N>`), filter the JSON list to issues whose body contains `PRD: #<N>` before proceeding.

2. **For each issue (in ranked order — top residual first, preserving the `/qa-plan` ranking):**

   a. **Read the issue body.** Extract: criterion text, "what to eyeball" description, PRD link.

   b. **Infer recommendation and PRO/CON options.** From the criterion text and the "what to eyeball" description, LLM-infer a concrete accept/reject recommendation with pros and cons specific to this criterion. Mirror the PRD #147 dogfood pattern — infer specific options, not generic "Accept / Reject". Use the option-label format `A / B` with the recommendation labeled first. Example options for a UI criterion: `A (RECOMMENDED): confirm renders correctly — PRO: feature verified; CON: none / B: flag as broken — PRO: surfaces real defect; CON: blocks PRD retroactively`.

   c. **Present via `AskUserQuestion`.** Call `AskUserQuestion` with:
      - `question`: a one-line summary of what to check (from the criterion + eyeball description).
      - `options`: the inferred accept/reject options (A/B format per the grill-me option format).
      - Include the issue number and PRD link in the question text so the human has context without leaving the card.

   d. **Record the verdict based on the human's choice:**

      **Accept (option A — verified):**
      - Comment on the issue: `gh issue comment <issue-number> --body "Verified by human via /qa-review on <YYYY-MM-DD>. Verdict: ACCEPTED — criterion confirmed. Closing."`
      - Close the issue: `gh issue close <issue-number> --reason completed`
      - Count as `cleared`.

      **Reject (option B — defect found):**
      - Comment on the issue explaining the rejection.
      - Relabel the issue from `needs-human-check` to `captured`: `gh issue edit <issue-number> --remove-label needs-human-check --add-label captured`
      - Capture a `captured`-labeled defect issue per CLAUDE.md rule #13 (3-part body shape):

        ```bash
        gh issue create --label captured \
          --title "QA defect: <criterion summary> (PRD #<N>)" \
          --body "## Symptom\n<what the human observed when eyeballing the criterion>\n\n## Root cause\n<inferred from criterion text — what the machine could not verify and why the human rejected it>\n\n## Proposed workflow change\n<the fix needed: re-open slice, adjust implementation, or accept as known limitation>"
        ```

      - Count as `rejected` (the original `needs-human-check` issue is now `captured` for the autopilot).

3. **Emit the GENERATOR trailer** (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c):

```
RESULT: SUCCESS | INVALID_INPUT
REASON: <one sentence — e.g., "3 residuals reviewed: 2 accepted, 1 rejected and captured">
ARTIFACTS: <comma-separated URLs of captured defect issues, or empty>
RESIDUALS_CLEARED: <integer — accepted + closed>
RESIDUALS_REJECTED: <integer — relabeled captured>
RESIDUALS_PENDING: <integer — issues not yet reviewed in this run, if any>
```

`RESULT: SUCCESS` when all presented residuals receive a verdict (regardless of accept/reject outcome). `RESULT: INVALID_INPUT` only on missing inputs (no `gh` access, malformed filter).

## Tool boundaries

Per [ADR-0040](../../../decisions/0040-qa-human-residual-model.md) D4: **`Read`**, **`Bash`** (gh CLI for issue list/comment/close/edit/create), **`AskUserQuestion`** (verdict rendering — main-agent-only; this is why `/qa-review` is a skill, not a subagent).

Explicitly **NOT**:
- **`Write` / `Edit`** — this skill never modifies tracked files. All mutations are GitHub issue state changes via `gh` CLI.
- **`Agent`** — no subagent dispatch. The clearing loop is sequential (one `AskUserQuestion` at a time) — parallelism would break attribution. Skills dispatch subagents; this skill's work is main-agent-native.
- Any `gh pr *` commands — this skill operates on issues only, not PRs.

## Conduct

- **One card at a time.** Present residuals sequentially, highest-value first. Do not batch multiple `AskUserQuestion` calls into a single prompt — each criterion deserves its own focused card.
- **Infer specific options.** Generic "Accept / Reject" cards are a fallback. Prefer criterion-specific options that name the concrete thing to confirm or flag.
- **Record every verdict.** Never silently discard a human response. Accept → close (the issue is done). Reject → relabel + capture (the autopilot handles the rest per CLAUDE.md rule #11).
- **Default-conservative on "what to eyeball."** If the criterion text is ambiguous, surface the ambiguity in the `AskUserQuestion` question text rather than guessing what to verify.

## References

- [ADR-0040](../../../decisions/0040-qa-human-residual-model.md) — D4 (this skill: main-agent, `AskUserQuestion`, accept→close / reject→relabel+capture, no new critic, 6-critic cap honored).
- [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D4 (writer owns audit-trail; this skill closes/relabels but does not post the original residual — that's `/qa-plan`'s job).
- [ADR-0025](../../../decisions/0025-qa-tester-ui-mode-playwright.md) D3/D4 (PROVISIONAL_PASS as residual signal origin; auto-capture pattern mirrored).
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap — honored; this is a skill, not a critic).
- [ADR-0024](../../../decisions/0024-root-cause-workflow-capture-discipline.md) D1 + D3 — CLAUDE.md rule #13 root-cause-capture discipline; reject path captures follow the 3-part body shape.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — canonical GENERATOR trailer schema.
- [`.claude/agents/qa-tester.md`](../../agents/qa-tester.md) — executor that produces PROVISIONAL residuals (returned as data, not posted by the executor).
- [`.claude/skills/qa-plan/SKILL.md`](../qa-plan/SKILL.md) — writer that queues PROVISIONAL residuals as `needs-human-check` issues and surfaces the headline.
- PRD [#474](https://github.com/vojtech-stas/project-claude/issues/474) — parent PRD for the QA residual model; this skill ships in slice #475.
