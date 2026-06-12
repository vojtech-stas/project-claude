# 0068 — Hygiene layer: diff-invisible state checks, secrets discipline, session-start context injection

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0057 D4 (the authorized-but-unimplemented fifth hook category — this ADR ships the implementing hook); ADR-0016 D4 (the log location decision for `.claude/logs/workflow-events.jsonl` — the file at that location gains size-capped archive-aside rotation in its canonical logger); ADR-0017 D3 (the docs-currency rubric family — hygiene checks join the same audit surface, implemented in the ADR-0064 D3 registry)

## Context

Three classes of rot are invisible to per-PR review because they never appear in a diff. First, workspace hygiene: untracked files accumulate under tracked directories (140+ in qa-proof/ today), the JSONL event log grows without rotation, remote branches outlive their PRs, and required labels exist only on the repo where someone remembered to create them (bootstrap.sh drifted from the live label set twice). Second, secrets: this repo has ZERO secrets coverage — an autonomous agent committing a token at machine speed is currently caught by nothing; the audit found none committed to date, which is luck, not control. Third, session-start blindness: a resumed session reconstructs state by ad-hoc `gh` queries or not at all — the `needs-human` escalation surface (I5) fired for the first time only when a human happened to look; ADR-0057 D4 authorized a context-injection hook category precisely for this and explicitly deferred the implementing hook to a later wave. This is that wave.

## Decisions

### D1 — Hygiene registry checks over diff-invisible state

New registry checks (per ADR-0064 D3, implemented once in dashboard/health.py): untracked file count+size under tracked directories (threshold WARN); workflow-events.jsonl size vs the rotation cap (FAIL when rotation is broken); stale remote branches (merged or >14 days inactive without an open PR); required-labels presence on the live repo (the label set bootstrap.sh declares — drift between them is the defect); dead API surface count (routes served but never fetched by the frontend, extending the audit that found 4). Each row reports honest day-one values. The canonical logger (`log-tool-event.sh`) gains size-capped rotation (archive-aside, never delete; cap documented in the script). Per ADR-0004 D2 (bootstrap-mode), binds forward from the checks' merge; pre-existing accumulation is the honest starting value, not a FAIL.

### D2 — Secrets discipline: grep gate + never-list rule

A secrets-shaped-string check (key/token/private-key patterns + entropy heuristic, with a tracked, reviewed allowlist for documented false positives) runs in BOTH `.githooks/pre-commit` (advisory speed) and `tools/ci-checks.sh` (the gate of record, per ADR-0042 D1). The never-list rule ships as prose IN the check's header and the allowlist file: a secret that reaches a commit is ROTATED immediately — allowlisting a real secret is the named anti-pattern. Per ADR-0004 D2, binds forward; history is not scanned retroactively (a one-shot historical scan is a captured follow-up, not a standing gate).

### D3 — SessionStart context-injection hook (implements ADR-0057 D4)

`.claude/hooks/session-start.sh` injects deterministic, read-only state at session start: open `needs-human` PRs/issues, in-flight assigned slices, captured-queue depth, capture-feed and dashboard freshness. Pure `gh`/`git` command output with graceful degradation (missing gh → inject a one-line warning, never block); NEVER invokes skills or subagents (rule #12's hard line, reaffirmed by ADR-0057 D4). Measurement (registry row): exactly one `session_context_injected` event per session_id in the event log — sessions without one make the resumed-session gap visible. Per ADR-0004 D2, binds forward from the hook's merge.

## Consequences

- Diff-invisible rot gets standing detectors; the secrets hole is closed before it is ever exploited; sessions start informed and the I5 escalation surface is surfaced automatically instead of by memory.
- Pre-commit gets marginally slower (one grep pass). The hook adds startup latency bounded by two `gh` calls. Rotation introduces an archive directory to manage (size-capped, append-only).
- **Cascade (per ADR-0005 D3):** CLAUDE.md rule #12's headline text is refreshed in the D3 implementing slice to name the five authorized categories (logging/validation/notification per ADR-0015 D2, tooling-spawn per ADR-0033 D1, context injection per ADR-0057 D4) — the current text predates two scope amendments. The slicer should also sweep subagent prompts that quote the old category list verbatim.

### Enforcement (rule #23)

Deterministic, per decision: D1 — the five hygiene registry rows themselves (each CLI-runnable via `--check`); D2 — the ci-checks secrets stage (induced-failure demonstrable: a fixture-pattern secret string must FAIL it) + pre-commit mirror; D3 — the one-injection-per-session registry row. Parsimony — mechanisms considered: audit-meta's DOCS-*/STRUCT-* rubric covers tracked-file structure, not untracked accumulation or remote-branch state (verified against the audit-meta rubric); the dead-API-surface row's own shadow is route-level drift — endpoints served but never consumed accumulating as false surface (the senior audit found 4) — and no existing registry row or audit-meta rubric line counts route liveness (verified against `--list` and the SKILL.md rubric); R-SECRETS in the reviewer rubric judges PR diffs at review time but autonomous commits need a pre-merge mechanical gate (CI is the gate of record); no existing mechanism observes session starts at all; all three land in existing surfaces (registry, ci-checks/pre-commit, hooks+settings.json) — no new agent. Shadow: silent workspace bloat, dead routes masquerading as live surface, a committed token caught by luck, resumed sessions acting on stale state.

## Alternatives considered

- **Full secret-scanning service (gitleaks/trufflehog dependency):** rejected — new external dependency for a repo whose secret surface is near-zero today; the grep+entropy+allowlist gate covers the autonomous-agent failure mode; revisit if false-negative evidence appears.
- **Injecting context via CLAUDE.md instead of a hook:** rejected — CLAUDE.md is static per-commit; the injection's value is live state at session start, which is exactly the category ADR-0057 D4 authorized.
- **Auto-pruning untracked files/branches:** rejected — destructive automation over un-reviewed state; detectors report, humans (or reviewed PRs) act.
- **Log rotation by deletion:** rejected — the event log is the measurement substrate (ADR-0016); archive-aside preserves history at bounded working-set size.

## References

- ADR-0057 D4 (authorizing decision), ADR-0015 D2 + ADR-0033 D1 (the prior scope categories named in the rule-#12 refresh), ADR-0016 D4 (log location), ADR-0017 D3 (audit surface), ADR-0064 D3 (registry single-source), ADR-0042 D1 (CI gate of record), ADR-0004 D2 (bootstrap-mode), issues #736 #729 #725, workflow-v2 synthesis §B18/§C1 (2026-06-12).
- Numbering note: co-submitted with the regression-memory ADR (one number below) and the fleet-economics ADR (one number above) in this wave's joint gate; all three ship together in slice 1 per ADR-0003 D8, keeping the sequence contiguous at merge.
