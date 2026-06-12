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

## Conduct

**Run-to-done.** When multiple goals or PRDs are queued — either explicitly by the user ("build everything in the backlog") or by the run's own decomposition (a multi-slice PRD) — execute them consecutively to completion (merged + production-verified + closed) without pausing between goals. One wrap-up report at the end covers all goals. Stops mid-run are reserved exclusively for:
- Destructive or irreversible operations (branch deletion, ref rewrites, force-push) — confirm with the user before proceeding.
- Genuine user-only scope forks — when a design decision cannot be resolved from the grilled context and a wrong choice would require rework that cannot be corrected by later slices; name the specific fork and stop only for that decision.
- Round-3 strict-stops (rule #19 / I5) — a `needs-human` escalation after three BLOCK rounds; this overrides the run-to-done drive unconditionally.

**Reroute-when-blocked.** On a blocked path — an unregistered agent type, an unavailable tool, or stray environment state — the orchestrator reroutes before stopping:
1. **Substitute**: if a registered subagent type is unavailable, dispatch `general-purpose` with the role file loaded inline (per the `qa-tester` precedent for unregistered environments).
2. **Repair**: fix environment state (kill stray servers, run `bash tools/worktree-guard.sh branch-restore` to restore a drifted worktree, clean stale lock files) and retry.
3. **Re-decompose**: if the blocked path is a design dead-end, re-run the relevant pipeline stage with updated context.

In all three cases, capture the root cause per rule #13 (symptom + root cause + proposed workflow change as a `captured`-labeled issue) before continuing. Stopping without rerouting is a last resort, not a first response.

## Step-by-step procedure

### Step 0 — Live-feed self-check (capture honesty gate)

Before any pipeline work, verify the capture layer is alive for this session.
Read the tail of `workflow-events.jsonl` (last 200 lines) and count events whose
`session_id` matches `$CLAUDE_CODE_SESSION_ID` and whose `ts` is >= the current
session-start time. Use python3 (rule #12-compatible — reads a log file, does not
invoke hooks; per PRD #668 §2 orchestrator-level honesty):

```bash
python3 - <<'PY'
import os
log = os.environ.get("CLAUDE_PROJECT_DIR","") + "/.claude/logs/workflow-events.jsonl"
sid = os.environ.get("CLAUDE_CODE_SESSION_ID","")
try:
    lines = open(log, encoding="utf-8", errors="replace").readlines()[-200:]
    fresh = sum(1 for l in lines if sid and sid in l)
    print(fresh)
except Exception:
    print(0)
PY
```

**If count == 0:** state verbatim: "capture is dead (resumed-session class)" and
stamp this run `capture=dead`. Downstream verification CANNOT claim live hook-fire
evidence for this run; note it explicitly in the step 5 final report.

**If count > 0:** log "capture alive: N fresh events" and proceed.

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

**Guard:** Before invoking `/ship`, capture `EXPECTED=$(git rev-parse --abbrev-ref HEAD)`. After `/ship` returns, run `bash tools/worktree-guard.sh branch-restore "$EXPECTED"` to ff-restore the orchestrator's worktree if it drifted (per [ADR-0041](../../../decisions/0041-origin-main-source-of-truth.md) D1). After `/ship` reports slices merged, run `bash tools/worktree-guard.sh root-sync` to ff-sync the root repo to `origin/main` so the dashboard reflects live state (per ADR-0041 D3). Both guard calls soft-degrade — a guard failure is logged and execution continues.

Invoke [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md) with the grilled/concrete input as context. Pass `invoked_by: build` so `/ship` skips its own production-verify gate (dedup rule — step 5 owns the gate here).

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

**Guard:** Before each `qa-tester` or `implementer` dispatch below, capture `EXPECTED=$(git rev-parse --abbrev-ref HEAD)`; after the dispatch returns, run `bash tools/worktree-guard.sh branch-restore "$EXPECTED"` (ADR-0041 D1, soft-degrade).

**Dispatch** `qa-tester` in production-verify mode with `isolation: "worktree"` (ADR-0036):

Input to pass:
- The full PRD body (use PRD issue number from step 3's `PRD_URL`; fetch via `gh issue view <N> --json body`)
- The "Production check:" line extracted from PRD §2
- A merged diff summary (changed-path globs; derive from the implementation PRs in step 3's `IMPLEMENTATION_PRS`)

**Result handling (loop per ADR-0037 D5):**

The gate runs up to **3 rounds total**. Track round count; increment on each FAIL.

**PASS** (`PRODUCTION_VERIFY: PASS` in qa-tester's trailer):
- Extract `PROOF:`, `ROUTE:`, `ARTIFACTS:`, `PROOF_SOURCE:`, and `ENV:` from qa-tester's trailer.
- **Artifact-existence assertion (ADR-0061 D5 — orchestrator-enforced):** for each path in `ARTIFACTS:`, stat the file before accepting PASS:
  ```bash
  for artifact_path in <paths from ARTIFACTS: field>; do
    if [ ! -f "$artifact_path" ]; then
      echo "GATE FAIL: ARTIFACTS path does not exist: $artifact_path — verdict invalid"
      # treat as FAIL, re-dispatch (up to 3 rounds)
    fi
  done
  ```
  A `PRODUCTION_VERIFY: PASS` with a missing ARTIFACTS path is **verdict-invalid** — treat as a FAIL and loop (re-dispatch qa-tester). A missing artifact means the proof cannot be verified, per ADR-0061 D5 (issue #777 class).
- **PROOF_SOURCE validation (ADR-0061 D2):** validate `PROOF_SOURCE: <sid>@<ts>` before accepting PASS:
  1. Extract `sid` from `PROOF_SOURCE:` field.
  2. Assert `sid` exists in `.claude/logs/workflow-events.jsonl` (grep for the sid in the event window).
  3. Assert `sid` is NOT fixture-patterned: must not match `sess-test-*`, `fixture-*`, or `synthetic-*`.
  4. If validation fails → verdict invalid → treat as FAIL, re-dispatch.
- **ENV validation for browser routes (ADR-0061 D2):** when `ROUTE: browser`, validate `ENV: <sha>@<started_at>`:
  1. Extract `sha` from `ENV:` field.
  2. Fetch `/api/meta` and assert `sha` matches the dashboard's reported sha.
  3. If `sha` mismatches or `/api/meta` reports `stale: true` → verdict invalid → treat as FAIL, re-dispatch.
- **Block-on-missing-proof check (per ADR-0037 D3 — orchestrator-enforced blocking):** assert `PROOF:` is non-empty for the routed change type. If `PRODUCTION_VERIFY: PASS` but `PROOF:` is empty or absent, the feature is **NOT done** — treat this as a gate failure and block:
  - `browser` route: `PROOF:` MUST contain a screenshot path (`.png` or `.jpg`) AND an `inner_text:` excerpt. A browser change with no screenshot proof is not 'done'. Block with: `"PRODUCTION_VERIFY claimed PASS but PROOF: absent for browser route — screenshot proof required; not marking done."`
  - `hook-fire` route: `PROOF:` MUST contain `exit=` AND `log:` (or "log: N/A" if not declared). A hook change with no log-line proof is not 'done'.
  - `command-run` route: `PROOF:` MUST contain `exit=` AND `output:`. A skill/tool change with no output excerpt proof is not 'done'.
  - `static-check` route: `PROOF:` MUST contain `grep count=`. A static assertion with no grep-count proof is not 'done'.
  - If `PROOF:` is non-empty and matches the expected shape for the route, proceed to proof-posting. If proof-absent block occurs, log the failure and loop: re-dispatch `qa-tester` (round incremented); treat as a FAIL for the loop counter (up to 3 rounds per ADR-0037 D5).
- Surface the proof to the user: print `PROOF:` + `ASSERTIONS_CHECKED:` from qa-tester's trailer.
- Log a confirmation line: `"Production gate PASS (round <N>): feature verified in production."`
- **Proof-posting (per ADR-0049 D3 — orchestrator owns commit + comment; qa-tester stays read-only):**
  If qa-tester's `ARTIFACTS` trailer contains a proof image path (a `.png` or `.jpg` file), commit it to the PR branch and post a PR comment so the reviewer and user see the rendered proof inline:
  ```bash
  # <prd-num>  = PRD issue number (from step 3's PRD_URL)
  # <proof>    = the local path returned in qa-tester's ARTIFACTS field
  # <branch>   = the PR branch name (from implementer's BRANCH_NAME trailer)
  # <pr-num>   = PR number (from implementer's PR_URL trailer)
  # <slug>     = basename of the proof file (e.g. "architecture-live.png")

  git add qa-proof/<prd-num>/<slug>
  git commit -m "chore(qa): add visual proof for PRD #<prd-num>"
  git push

  # Post an inline PR comment with the rendered image.
  # raw.githubusercontent.com renders images directly in PR comments (unlike the
  # blob/?raw=true form which serves the file but does not render inline).
  # Derive the slug from origin so the URL is correct in any derived repo,
  # not just the template (issue #649).
  REPO_SLUG=$(gh repo view --json nameWithOwner -q .nameWithOwner)
  gh pr comment <pr-num> --body "![qa-proof](https://raw.githubusercontent.com/${REPO_SLUG}/<branch>/qa-proof/<prd-num>/<slug>)"
  ```
  If no proof image path is present (command-run or static-check route), skip the commit/comment and continue.
- **SendUserFile at wrap-up (per CLAUDE.md rule #20 + ADR-0037 D3):** After proof-posting, send each committed proof artifact to the user in chat — one `SendUserFile` call per artifact, with a caption tying it to the verified feature claim. This runs in main-agent context (the wrap-up is always main-agent), so `SendUserFile` is available. For each proof artifact in `qa-proof/<prd-num>/`:
  - **browser route:** `SendUserFile qa-proof/<prd-num>/<slug>` with caption `"PRD #<prd-num> — production-verified: [the PRD's Production check: line]"`.
  - **hook-fire / command-run / static-check routes:** no file to send (no image); instead print the `PROOF:` string inline in the summary beside the verified claim.
- **Visible-surface screenshot floor (run-to-done complement):** Regardless of proof route, if the shipped work has ANY user-visible surface — a dashboard tab, panel, graph, or report view — the wrap-up MUST capture a post-merge production screenshot from a fresh (restarted/live) environment per rule #20's freshness clause and `SendUserFile` it with a claim-tied caption. The route-scoped SendUserFile items above are the per-route minimum; this floor-raises them for visual work. Non-visual work: send the nearest visible artifact if one exists (e.g. a CLI output excerpt as an inline code block), else state honestly "no visual surface — nearest artifact: [quoted output]". Do NOT send a screenshot of a stale or pre-merge environment; restart the relevant server/dashboard before capturing.
- **Post-merge green-main step (ADR-0062 D3):** After all slices have merged (confirmed by `/ship` in step 3) and before marking the feature done, run the post-merge verification on actual merged main:
  1. `bash tools/ci-checks.sh` — must exit 0.
  2. `/api/meta` SHA smoke: `curl -s http://localhost:8765/api/meta | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('sha') else 1)"` — confirms dashboard reflects merged sha.
  3. On success, append a `main_green` event to the workflow event log via the canonical logger pattern:
     ```bash
     python3 -c "import json,datetime,subprocess; sha=subprocess.check_output(['git','rev-parse','origin/main']).decode().strip(); line=json.dumps({'v':2,'ts':datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),'event':'main_green','sha':sha,'src':'orchestrator'}); open('$(git rev-parse --show-toplevel)/.claude/logs/workflow-events.jsonl','a').write(line+'\n')"
     ```
  4. On failure: the suspect set = squash commits since the last `main_green` event (≤300 LoC slices make bisect degenerate); revert via the trivial lane (`hotfix/<short-desc>` branch); do NOT mark the PRD done until green.
  Per [ADR-0062](../../../decisions/0062-merge-integrity-green-main.md) D3.
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
- [ADR-0041](../../../decisions/0041-origin-main-source-of-truth.md) — D1 (post-dispatch leak-guard: capture branch + restore after each dispatch via `branch-restore`); D3 (root ff-sync after `/ship` merges via `root-sync`; only ff-only + clean-only + soft-degrade)
- [ADR-0033](../../../decisions/0033-tooling-spawn-hook-scope.md) — D1 (tooling-spawn carveout; dashboard-autostart.sh authorized)
- Sub-skills this skill chains: [`.claude/skills/grill-me/SKILL.md`](../grill-me/SKILL.md), [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md)
- qa-tester subagent (production-verify mode): [`.claude/agents/qa-tester.md`](../../agents/qa-tester.md)
- Dashboard autostart hook: [`.claude/hooks/dashboard-autostart.sh`](../../hooks/dashboard-autostart.sh) (ships PRD #345 slice 2, PR #350)
- Doc-generator: `dashboard/server.py --generate-readme` (ships PRD #348 slice 1, i.e., slice #361)
- Output-shape standard (GENERATOR trailer schema): per ADR-0005 D1c
- Full role synthesis lives in this file
