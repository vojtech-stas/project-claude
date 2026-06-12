# 0057 — Hook fail-loud contract + capture-liveness gate + context-injection scope

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0015 D2 (hook scope list — adds a failure contract and a fifth permitted category); ADR-0033 D1 (which added tooling-spawn as the fourth category to the same list)

## Context

The telemetry layer is the dashboard's ground truth, and it dies silently. Measured failures: hooks dead for 5 days with zero indication (a `jq` ENOEXEC swallowed by exit-0 silence, qa-proof/forensics autopsy); 31% of v2 sessions are boundary-only (session_start/stop with nothing between); resumed and worktree sessions never register hooks (6 PRs merged on 2026-06-11 inside a ~9-hour zero-event window); the 2026-06-11 audit (#726) proved the enforcement hooks fail OPEN — `pre-tool-edit.sh` reads only the first 4096 bytes so any large Edit/Write skips the rule #10 gate, its allowlist is a raw-stdin substring match bypassable by payload CONTENT, `stop-reviewer-gate.sh` never reads stdin (ignores `stop_hook_active`, hard-blocks on transient gh failures), and the canonical fixture sid `sample-session-id` escapes both fixture filters (rule #21 violation channel). ADR-0015 defined the hook scope (logging/validation/notification) but no failure contract: a hook that crashes, truncates, or mis-parses simply vanishes from the record.

## Decisions

### D1 — Fail-loud beacon contract for all hooks

Every hook script MUST: (a) emit its attempt beacon BEFORE any parsing or branching (attempt-before-parse ordering), so a crash after the beacon is visible as attempt-without-ok; (b) on any internal error emit an `ERROR` beacon line carrying `session_id` and the failure class to `hook-fires.jsonl` rather than exiting silently; (c) parse FULL stdin with python3 (already a hard dependency of the canonical logger) — never `head -c` truncation, never raw-substring matching against the whole payload; gating decisions match extracted JSON fields (e.g. `tool_input.file_path`), not stdin text; (d) prefer truncate-and-steer over silent drop when payloads exceed log-friendly sizes (store a bounded excerpt plus lengths, never zero bytes).

### D2 — Gate-hook failure semantics

Enforcement hooks (PreToolUse gates, Stop gates) distinguish three outcomes: ALLOW, DENY (policy decision on successfully-parsed input), and ERROR (infrastructure failure — parser crash, missing dependency, dead gh). On ERROR a gate MUST fail open for the user action but fail LOUD in telemetry (D1's ERROR beacon): a broken gate must not lock the user out of their own repo, and must not pretend it evaluated anything. `stop-reviewer-gate.sh` MUST read stdin and honor `stop_hook_active` (the loop guard) before any other logic. Fixture session ids (`sample-session-id` joins the existing fixture-sid patterns) are filtered at every reader AND at the gate hooks (rule #21).

### D3 — Capture-liveness gate in orchestrator skills

`/ship` and `/build` step 0 formalize the capture self-check (already prototyped in /ship): count this session's events in `workflow-events.jsonl`; stamp the run `capture=live|dead`; a `capture=dead` run cannot claim live hook-fire evidence anywhere downstream (qa-tester routes and wrap-up reports must carry the stamp). The dashboard exposes per-session liveness (sessions with hook feed / total — the capture SLO) so the resumed-session blind spot is a visible badge, not tribal knowledge.

### D4 — Scope amendment: context injection (fifth category)

ADR-0015 D2's permitted hook scope — logging / validation / notification, extended to a fourth category (tooling-spawn) by ADR-0033 D1 — gains a **fifth category: context injection**. A SessionStart hook MAY inject deterministic, read-only command output (e.g. open `needs-human` PRs, in-flight assigned slices, captured-queue depth, capture/dashboard freshness) into session context. The hard line is reaffirmed and unchanged: hooks NEVER auto-invoke skills or subagents (rule #12); ADR-0033 D1's tooling-spawn carveout is untouched. This decision authorizes the category now; the implementing hook ships in a later wave (synthesis C1) under this scope.

### D5 — Bootstrap-mode binding

Per ADR-0004 D2 (bootstrap-mode): D1 and D2 bind at the merge of this wave's hook-hardening slice, which itself retrofits the existing hook fleet to the contract — hooks added after that merge must conform from birth; in-flight sessions running pre-merge hook bodies are grandfathered until their next session start. D3 binds at the merge of the /ship + /build SKILL.md edit. D4 authorizes a category and requires no retrofit. No retroactive sweep of historical telemetry.

## Consequences

- Telemetry death becomes a red badge within one session instead of a 5-day forensic discovery; the dashboard's "is the workflow used" claim gains an honest denominator.
- Gate hooks stop being silently bypassable by payload size or content echoes; their failure mode is explicit and logged.
- Slight hook complexity increase (python3 parsing everywhere); acceptable — python3 is already required by the canonical logger and bootstrap now checks it (#755).

### Enforcement (rule #23 — established by the co-submitted no-rule-without-a-check ADR shipping in the same slice-1 PR)

Deterministic: a health.py hook-integrity check (attempt-vs-ok beacon ratio per hook, ERROR-beacon surfacing, capture SLO row); negative-path proof obligation for hook-touching PRs (induced-failure beacon shown) lands in the wave-2 verification table. Shadow: silent telemetry death / fail-open gates. Existing-mechanism check: ADR-0015 defines scope but no failure contract; nothing else covers it.

## Alternatives considered

- **Fail-closed gates on infrastructure error:** rejected — a dead `gh` would lock every stop; availability of the human's own repo outranks gate strictness, and the loud ERROR beacon preserves auditability.
- **Rewrite hooks in python entirely:** deferred — the contract is language-agnostic; shell+python3-parse meets it with smaller diffs.
- **External watchdog process for hook liveness:** rejected — sprawl; the dashboard already polls the logs and can compute liveness from existing data.

## References

- ADR-0015 (scope being amended), ADR-0016 (event log), rule #12/#21 (CLAUDE.md), issues #726/#746/#673, qa-proof/forensics event-pipeline autopsy, workflow-v2 synthesis §B5/§C1 (2026-06-12).
