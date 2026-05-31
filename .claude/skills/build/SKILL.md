---
name: build
description: Full-lifecycle orchestrator — one command from idea to merged + verified PR. Use when user says "/build", "build this", "implement this", "let's ship", or wants to drive a feature all the way through from idea to production-verified done. Chains dashboard-autostart → grill (conditional) → /ship → doc-regeneration → production-verify gate (mandatory, blocking per ADR-0037 D1). Thin conductor per ADR-0034 D1; sub-skills remain standalone.
tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# /build — full-lifecycle orchestrator

Chains five stages — dashboard-check → grill (conditional, ADR-0034 D3) → `/ship` → regenerate-docs → production-verify gate (mandatory, blocking, ADR-0037 D1) — so the human drives a feature from raw idea to merged + production-verified done with one command. Thin per ADR-0034 D1: `/build` owns ONLY the chaining logic and checkpoint transitions; each sub-skill handles its own domain. Sub-skills remain individually invocable (ADR-0034 D2).

**The production-verify gate (step 5) is MANDATORY and blocking.** A feature is NOT "done" until `qa-tester` returns `PRODUCTION_VERIFY: PASS`. Per ADR-0037 D1.

Full design rationale: [ADR-0034](../../../decisions/0034-build-orchestrator-and-generated-docs.md) D1-D3.

## When NOT to use this skill

- Already mid-grill with unsettled design — let `/grill-me` finish, then run `/build <that-context>`.
- For trivial one-line fixes — use the `hotfix/<thing>` trivial lane (I3); `/build` is for feature-sized work.
- When only one pipeline stage needs rerunning — invoke that sub-skill directly (`/ship`, `/qa-plan`, etc.).

## Step-by-step procedure

### Step 1 — Ensure dashboard running (idempotent)

Invoke `.claude/hooks/dashboard-autostart.sh` as a subprocess so the human can watch the build live:

```bash
bash "${CLAUDE_PROJECT_DIR}/.claude/hooks/dashboard-autostart.sh"
```

This checks `localhost:8765`; spawns the dashboard if absent; no-ops if already up. Authorized by ADR-0033 D1 (tooling-spawn carveout). If the script fails or is missing, emit a one-line warning and continue — the dashboard is observability-only; its absence does not block the build.

### Step 2 — Assess + grill (conditional, ADR-0034 D3)

Auto-assess the input concreteness. Ask: **"Is there enough here to write a mechanically-verifiable PRD §2 without more questions?"**

Concreteness signals (any combination suffices):
- A GitHub issue number with a symptom + root-cause + proposed-fix body
- A structured spec with acceptance criteria
- A grilled conversation with all major design questions resolved
- A CLAUDE.md slice body or equivalent with "What ships" and "Acceptance criteria"

**If vague** (open idea, vague noun-phrase, no acceptance criteria visible): announce `"Input is vague — invoking /grill-me"` then invoke [`.claude/skills/grill-me/SKILL.md`](../grill-me/SKILL.md). Wait for the grill to complete. If the user stops the grill early without a settled design, STOP with `RESULT: STOPPED, REASON: grill incomplete — re-run /build when design is settled`.

**If concrete**: announce `"Input is concrete — skipping grill, proceeding to /ship"` and proceed immediately to step 3. **Do NOT ask a blocking "grill or skip?" confirmation question** (ADR-0034 D3 / 5A).

### Step 3 — Ship (autonomous middle)

Invoke [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md) with the grilled/concrete input as context.

`/ship` internally runs: `to-prd → prd-critic (+ adr-critic) → to-issues → slicer → slicer-critic → implementer (DAG-parallel) → reviewer (auto-merge)`. Do NOT reimplement any of that logic here (ADR-0034 D1).

**Result check:** if `/ship` returns `RESULT: STOPPED` or `RESULT: INVALID_INPUT`, surface the reason and STOP. Do not proceed to step 4 on a failed ship.

Capture the terminal `/ship` GENERATOR trailer for inclusion in the final report:
- `PRD_URL`, `SLICE_COUNT`, `IMPLEMENTATION_PRS`, `BLOCKED_SLICES`.

### Step 4 — Regenerate docs

Run the doc-generator as a subprocess so the PRs arrive doc-current:

```bash
python "${CLAUDE_PROJECT_DIR}/dashboard/server.py" --generate-readme
```

If the generator exits non-zero, emit a warning with the error output and continue — doc-regeneration failure is a soft error at this step (the reviewer's `R-DOCS-CURRENT` rule is the hard gate). If it exits zero, confirm `README.md` updated (note byte count).

### Step 5 — Production-verify gate (MANDATORY, blocking — per ADR-0037 D1)

This step replaces the former optional `/qa-plan` tail with a **mandatory blocking production-verification gate**. A feature is NOT "done" until it passes.

**Dispatch** `qa-tester` in production-verify mode with `isolation: "worktree"` (ADR-0036):

Input to pass:
- The full PRD body (use PRD issue number from step 3's `PRD_URL`; fetch via `gh issue view <N> --json body`)
- The "Production check:" line extracted from PRD §2
- A merged diff summary (changed-path globs; derive from the implementation PRs in step 3's `IMPLEMENTATION_PRS`)

**Result handling (loop per ADR-0037 D5):**

The gate runs up to **3 rounds total**. Track round count; increment on each FAIL.

**PASS** (`PRODUCTION_VERIFY: PASS` in qa-tester's trailer):
- Surface the proof to the user: print `PROOF:` + `ASSERTIONS_CHECKED:` from qa-tester's trailer.
- Log a confirmation line: `"Production gate PASS (round <N>): feature verified in production."`
- Mark the feature done; proceed to output.

**FAIL** (`PRODUCTION_VERIFY: FAIL` in qa-tester's trailer) — and `round < 3`:
- Surface the failure proof to the user (REASON + PROOF + ASSERTIONS_CHECKED from qa-tester's trailer).
- Re-dispatch the **implementer** (isolated, ADR-0036) with the proof of what broke: `"Production gate FAIL (round <N>): <reason>. Proof: <proof>. Fix the production failure and push a new commit to the same branch; the gate will re-run."` The implementer opens a new PR (or force-updates the existing branch if appropriate — the slice is still open) and the reviewer merges it.
- Re-run step 3 (ship the fix) → re-run step 4 (regen docs) → re-run step 5 (production-verify again).

**FAIL on round 3** — escalation per ADR-0037 D5 / CLAUDE.md I5:
- Apply `needs-human` label to the parent PRD: `gh issue edit <PRD_NUMBER> --add-label needs-human`
- Post a summary comment on the parent PRD: `gh issue comment <PRD_NUMBER> --body "Production gate FAIL after 3 rounds. Feature is blocked. Proof of last failure: <REASON> | <PROOF> | Assertions: <ASSERTIONS_CHECKED>. Human review required."`
- Return `RESULT: BLOCKED` in the /build trailer.

**One gate per feature:** do NOT double-run this gate if `/ship` is also wired to gate (slice #454). The gate in `/build` is sufficient; `/ship` standalone gating is slice #454 scope.

**INVALID_INPUT from qa-tester:** surface the reason and STOP — do not loop on malformed input.

## Output

After step 5, emit the canonical **GENERATOR trailer** as a fenced code block:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT | BLOCKED
REASON: <one sentence — e.g., "full lifecycle complete; PRD #N production-verified; <M> slices merged">
ARTIFACTS: <PRD URL, comma-separated implementation PR URLs>
SHIP_RESULT: <RESULT field from /ship's trailer>
PRODUCTION_VERIFY: <PASS | FAIL | not-reached>
PROOF: <proof string from qa-tester's trailer, or "not-reached">
BLOCKED_SLICES: <from /ship's trailer; empty if none>
```

`RESULT: SUCCESS` when all slices merged AND production gate PASS.
`RESULT: BLOCKED` when production gate fails after 3 rounds (needs-human applied).
`RESULT: STOPPED` when any earlier stage halts (grill incomplete, /ship failure).

## References

- [ADR-0037](../../../decisions/0037-production-verification-gate.md) — D1 (mandatory blocking gate per feature), D3 (orchestrator-enforced; qa-tester stays a generator), D5 (failure loop ≤3 rounds + needs-human escalation), D6 (bootstrap-mode)
- [ADR-0034](../../../decisions/0034-build-orchestrator-and-generated-docs.md) — D1 (thin orchestrator), D2 (sub-skills atomic), D3 (grill-conditional + no blocking question), D7 (doc-generator), D10 (generator is subprocess-invoked, not hook-spawned)
- [ADR-0036](../../../decisions/0036-worktree-isolation-all-dispatches.md) — isolated dispatch of qa-tester + implementer
- [ADR-0033](../../../decisions/0033-tooling-spawn-hook-scope.md) — D1 (tooling-spawn carveout; dashboard-autostart.sh authorized)
- Sub-skills this skill chains: [`.claude/skills/grill-me/SKILL.md`](../grill-me/SKILL.md), [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md)
- qa-tester subagent (production-verify mode): [`.claude/agents/qa-tester.md`](../../agents/qa-tester.md)
- Dashboard autostart hook: [`.claude/hooks/dashboard-autostart.sh`](../../hooks/dashboard-autostart.sh) (ships PRD #345 slice 2, PR #350)
- Doc-generator: `dashboard/server.py --generate-readme` (ships PRD #348 slice 1, i.e., slice #361)
- Output-shape standard (GENERATOR trailer schema): per ADR-0005 D1c
- Full role synthesis lives in this file
