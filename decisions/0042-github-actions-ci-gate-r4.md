# ADR-0042: GitHub Actions mechanical-CI gate + R4 (required status checks); reviewer auto-merge

- **Status:** Accepted
- **Date:** 2026-06-01
- **Extends:** [ADR-0002](0002-autonomous-merge-policy.md) D9-revised (the reviewer auto-merge **policy** — this ADR realizes its "branch protection deferred to slice 7" note; the APPROVE-gates-merge discipline is preserved) + [ADR-0004](0004-bypass-prevention.md) D3 (the workflow enforcement stack — this ADR adds the **required-status-checks** layer, the CI gate, to the stack). Builds on [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 (`bootstrap.sh` scope, which explicitly deferred CI + the status-checks + non-author-review protections to "PRD-CI" — this is that PRD; note ADR-0008 D6's own R3/R4 *labels* are reversed vs ADR-0004's canonical numbering — see the Context caveat). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic) and [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (no human gates between stages).
- **Supersedes:** [ADR-0002](0002-autonomous-merge-policy.md) D9-revised's reviewer **merge command** specifically — this ADR's D3 changes `gh pr merge --squash` to `gh pr merge --squash --auto` (merge-when-checks-pass / async until CI passes). Only the command changes; the APPROVE-gates-merge discipline + `--squash` mode are unchanged (which is why the broader D9-revised *policy* is Extended, not superseded).

## Context

The autonomous pipeline runs **locally**: the Claude Code orchestrator (`/ship`, `/build`) dispatches the `reviewer` subagent in-session, which reviews and auto-merges via `gh pr merge --squash` using the owner's `gh` token ([ADR-0002](0002-autonomous-merge-policy.md) D9-revised). Two gaps remain, both explicitly deferred by prior ADRs to "PRD-CI" / "slice 7":
1. **No server-side check gate.** Every mechanical check (settings.json validity, dangling ADR links, ≤72-char commit subjects, README currency) runs only locally during a `/ship` run. Nothing re-verifies on GitHub; a PR that bypassed the local pipeline lands unchecked.
2. **"No direct push to main" is partly soft.** `bootstrap.sh` step 5 already applies branch-protection **R1** (require PR / no direct push) + **R2** (no force-push, no deletion), but **R4 (required status checks)** is `null` — so a PR can merge with no enforced check gate.

**R-numbering caveat (a pre-existing codebase inconsistency).** The R-labels are used in two conflicting ways in the existing artifacts: [ADR-0004](0004-bypass-prevention.md) line 57 (the ADR that *defines* the R-stack) says **R3 = required approving reviews, R4 = required status checks**; but [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6, `bootstrap.sh`'s comments, AND backlog #63's body all label them in the **reverse** order (R3 = status checks, R4 = non-author review). This ADR adopts **ADR-0004's numbering** (the defining ADR) and, to stay unambiguous regardless of label, refers to each mechanism by **name** throughout:
- **R1** = require PR / no direct push (already applied by bootstrap step 5).
- **R2** = no force-push / no deletion (already applied).
- **R3** = required **approving reviews** (non-author review) — needs a separate reviewer identity; **deferred** (D4).
- **R4** = required **status checks** — the CI gate; **enabled by this ADR** (D2).

(The conflicting R-labels across ADR-0004 vs ADR-0008/bootstrap are a separate drift worth a follow-up cleanup; flagged, not fixed here.)

Grill (2026-06-01, Q1–Q5) scoped this deliberately small: **mechanical CI only (the AI reviewer stays local), enforce R4 (required status checks) + the already-present R1, defer R3/bot-identity to a future PRD.**

## Decisions

### D1: A GitHub Actions mechanical-CI gate

A `.github/workflows/ci.yml` (GitHub-hosted runner) fires on `pull_request` events and runs a tracked, CLI-runnable check script (e.g. `tools/ci-checks.sh`) covering the **deterministic** checks: `settings.json` validity (`python -m json.tool`), README regen-clean (`dashboard/server.py --generate-readme` + `git diff --exit-code README.md`), ≤72-char + Conventional-Commits subjects over the PR's commit range, dangling-ADR-link resolution, and `decisions/README.md` ↔ `decisions/*.md` index consistency. The workflow + script are **tracked files** — they persist on clone (unlike branch protection, a server setting). The [`/audit-meta`](.claude/skills/audit-meta/SKILL.md) + [`/audit-subagents`](.claude/skills/audit-subagents/SKILL.md) skills stay as-is for interactive/local use (they are Claude-interpreted, not CLI-runnable); CI implements a script version of their highest-value mechanical checks. Some logical overlap is intentional — CI **enforces**, the skills **advise**.

### D2: Enforce R4 (required status checks) on `main`

Extend `bootstrap.sh` step 5 (the existing R1+R2 branch-protection call) to set `required_status_checks` to require the CI check from D1. R1 (require PR / no direct push) + R2 already hold; this adds R4, completing the merge gate: `main` can only advance via a PR whose CI check is green. Applied via `gh api` by the **owner** (admin), **after** the CI workflow is live on `main` and has produced a named check run (sequencing — D-watchlist). `enforce_admins` stays `false` (the owner retains an emergency override; the autonomous flow honors the gate via D3's `--auto`, so the override is never exercised in normal operation). This realizes [ADR-0002](0002-autonomous-merge-policy.md)'s "slice 7" deferral and adds the R4 layer to the [ADR-0004](0004-bypass-prevention.md) D3 enforcement stack.

### D3: Reviewer merges with `--auto` (merge-when-checks-pass)

With R4 enabled, the local reviewer can no longer merge instantly (CI may still be running). On **APPROVE**, the reviewer runs `gh pr merge --squash --auto` — GitHub completes the merge once the CI check passes. A **red-CI PR never merges, even on reviewer APPROVE** (the verdict and CI both gate). The merge becomes **async** (completes seconds-to-minutes after the verdict); the orchestrator reports "merge queued" and downstream production-verify waits for the actual merge. This adjusts [ADR-0002](0002-autonomous-merge-policy.md) D9-revised's `gh pr merge --squash` call to add `--auto`; the APPROVE-gates-merge discipline is unchanged.

### D4: Defer R3 (required approving reviews / non-author) + bot identity to a future PRD

R3 (a required approving review from a non-author) is **not enabled**. Enabling it requires a **separate reviewer identity** — a bot GitHub account + token — because the local reviewer merges under the owner's token (author == merger), so R3 would permanently block every autonomous merge. The **local AI reviewer is the de-facto non-author gate** (it reviews every PR before merge); it is simply not GitHub-enforced. [ADR-0002](0002-autonomous-merge-policy.md) anticipated the bot at "slice 7", but bot identity is a heavier, separable concern (a second account, `ANTHROPIC_API_KEY`/token in repo secrets, cost-per-PR, and re-implementing the reviewer as a CI-callable job). This ADR consciously defers it; a future "reviewer-in-CI + bot identity" PRD can add R3 when the fully-cloud loop is wanted.

### D5: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. The R4 enable is a one-time owner action performed **after** this PRD's slices merge (enabling R4 mid-PRD would block this PRD's own pipeline merges). No retroactive sweep.

## Consequences

**Positive:**
- A server-side mechanical gate catches drift the local pipeline missed; a visible green/red check on every PR.
- `main` is hard-protected: a stray `git push origin main` is rejected by GitHub, and a red-CI PR cannot merge — discipline becomes enforcement.
- The CI workflow + check script persist on clone (tracked files); the protection config is reproducible via the bootstrap script.
- Deliberately small: no API key in CI secrets, no bot account, no cost-per-PR.

**Negative:**
- The reviewer's merge becomes async (`--auto`) — the orchestrator must treat "merge queued" as not-yet-merged and wait for CI before production-verify.
- A sequencing hazard: R4 must be enabled only after the CI check exists on `main`, else GitHub blocks all merges waiting for a check that never ran (D-watchlist; the enable is the last, owner-run step).

**Neutral:**
- Net new artifacts: a workflow file + a CI check script + a bootstrap addition. No new critic, no new dependency, no new subagent. R3/bot deferred (D4).

## Alternatives considered

- **Alt-A (chosen):** mechanical CI only + R4 (status checks) + reviewer `--auto`; defer R3/bot.
- **Alt-B: full reviewer-in-CI (Claude via Anthropic API in GitHub Actions) + bot identity + R3+R4.** Rejected (Q1): needs `ANTHROPIC_API_KEY` in secrets (exfiltration surface), a bot account, cost-per-PR, and re-implementing the reviewer as a CI job — large lift for low marginal value, since the local orchestrator already dispatches the reviewer on every PR.
- **Alt-C: no-direct-push only, no required checks.** Rejected (Q2): a red-CI PR could still merge — the checks would be advisory, not a gate.
- **Alt-D: keep instant merge, exclude admins from protection.** Rejected (Q4): the required-check gate would be bypassable by the exact identity that does all the merging — advisory again.

## References

- Grill 2026-06-01 Q1–Q5. Backlog [#63](https://github.com/vojtech-stas/project-claude/issues/63) (the capture — note its R3/R4 labels are reversed vs the canonical ADR-0004 numbering used here).
- [ADR-0002](0002-autonomous-merge-policy.md) D9-revised (reviewer auto-merge; "branch protection deferred to slice 7" realized here; `--auto` adjustment). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode), D3 (enforcement stack — R4 added), line 57 (canonical R1–R4 numbering). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D6 (bootstrap deferred CI/R3/R4 to PRD-CI), D7 (6-critic cap honored). [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (no human gates).
- `.github/workflows/ci.yml` (new), `tools/ci-checks.sh` (new), `bootstrap.sh` step 5 (R4 added), `.claude/agents/reviewer.md` (`--auto`), `decisions/branch-protection-config.json` (the reference payload, updated with required_status_checks).
