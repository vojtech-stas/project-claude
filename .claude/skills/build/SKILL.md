---
name: build
description: Full-lifecycle orchestrator — one command from idea to merged + verified PR. Use when user says "/build", "build this", "implement this", "let's ship", or wants to drive a feature all the way through from idea to QA. Chains dashboard-autostart → grill (conditional) → /ship → doc-regeneration → /qa-plan. Thin conductor per ADR-0034 D1; sub-skills remain standalone.
tools:
  - Bash
  - Read
  - Glob
  - Grep
---

# /build — full-lifecycle orchestrator

Chains five stages — dashboard-check → grill (conditional, ADR-0034 D3) → `/ship` → regenerate-docs → `/qa-plan` — so the human drives a feature from raw idea to merged + verified PR with one command. Thin per ADR-0034 D1: `/build` owns ONLY the chaining logic and checkpoint transitions; each sub-skill handles its own domain. Sub-skills remain individually invocable (ADR-0034 D2).

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

### Step 5 — QA (HITL acceptance)

Invoke [`.claude/skills/qa-plan/SKILL.md`](../qa-plan/SKILL.md) against the PRD that `/ship` created (use the `PRD_URL` from step 3's trailer to derive the PRD issue number).

`/qa-plan` runs: LLM-extract §2 criteria → dispatch `qa-tester` → render JUDGMENT rows via `AskUserQuestion` → auto-close PRD on all-PASS + all-judgment-ACCEPT.

**Result check:** capture the `PRD_DISPOSITION` field from `/qa-plan`'s trailer for the final report.

## Output

After step 5, emit the canonical **GENERATOR trailer** as a fenced code block:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "full lifecycle complete; PRD #N closed; <M> slices merged">
ARTIFACTS: <PRD URL, comma-separated implementation PR URLs>
SHIP_RESULT: <RESULT field from /ship's trailer>
PRD_DISPOSITION: <PRD_DISPOSITION from /qa-plan's trailer, or "not-reached" if pipeline halted before step 5>
BLOCKED_SLICES: <from /ship's trailer; empty if none>
```

## References

- [ADR-0034](../../../decisions/0034-build-orchestrator-and-generated-docs.md) — D1 (thin orchestrator), D2 (sub-skills atomic), D3 (grill-conditional + no blocking question), D7 (doc-generator), D10 (generator is subprocess-invoked, not hook-spawned)
- [ADR-0033](../../../decisions/0033-tooling-spawn-hook-scope.md) — D1 (tooling-spawn carveout; dashboard-autostart.sh authorized)
- Sub-skills this skill chains: [`.claude/skills/grill-me/SKILL.md`](../grill-me/SKILL.md), [`.claude/skills/ship/SKILL.md`](../ship/SKILL.md), [`.claude/skills/qa-plan/SKILL.md`](../qa-plan/SKILL.md)
- Dashboard autostart hook: [`.claude/hooks/dashboard-autostart.sh`](../../hooks/dashboard-autostart.sh) (ships PRD #345 slice 2, PR #350)
- Doc-generator: `dashboard/server.py --generate-readme` (ships PRD #348 slice 1, i.e., slice #361)
- Output-shape standard (GENERATOR trailer schema): per ADR-0005 D1c
- Full role synthesis lives in this file
