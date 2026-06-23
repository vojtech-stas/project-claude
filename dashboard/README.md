# project-claude workflow dashboard

Local web visualizer for the project's autonomous pipeline.

## Backend modules

The backend is split into flat sibling modules under `dashboard/`; `server.py` is a thin HTTP facade that re-exports everything:

| Module | Responsibility |
|---|---|
| `server.py` | HTTP request handler, named re-exports for all `/api/*` routes, module-level globals (caches, locks, `KNOWN_CRITICS`) |
| `live.py` | Live-progress cache + background refresh, `/api/live-progress` + `/api/live-poll` polling, capture-pill state |
| `discovery.py` | Skill/agent/hook/ADR filesystem discovery for `/api/pipeline` and the component graph |
| `health.py` | `check_docs1`–`check_docs11` docs-currency checks + STRUCT-1..10 structure checks (formerly `/audit-meta`, absorbed PRD #919 slice #920) + AS-AUDIT aggregate subagent-prompt check (formerly `/audit-subagents`, registered PRD #919 slice #921) + substrate checks (`check_capture_slo`, `check_hook_integrity`, `check_isolation_group`, `check_rule_coverage`, `check_critic_health`, `check_spec_coverage`) + verification-integrity checks (`check_blind_dispatch_rate`, `check_residual_ratio`, `check_proof_presence`, `check_merge_integrity`, `check_capture_shape`, `check_green_main`, `check_silent_drift`) + registry-integrity check (`check_parity`) + two-tier promotion checks (`check_release_ready`, `check_branch_topology`) + hygiene/session-start checks (`check_untracked_size`, `check_log_rotation`, `check_stale_branches`, `check_required_labels`, `check_dead_routes`, `check_session_injection`, `check_r_sensitive_detector`) + liveness/integrity checks (`check_stale_server`, `check_promotion_lag`, `check_hook_liveness`, `check_proof_integrity`, `check_meta_tripwire`), TTL-cached `/api/health`. **Check registry CLI:** `python dashboard/health.py --check <ID>` runs a single check headlessly (exit 0 = PASS/WARN, exit 1 = FAIL, exit 2 = unknown ID); `python dashboard/health.py --list` prints all registered IDs. Per ADR-0064 D3. |
| `events.py` | Workflow-event log reading (`/api/runs`), byte-cursor incremental poll, session grouping |
| `workitems.py` | GitHub Issues fetch via `fetch_workitems()` — used server-side by `/api/status` open_work counts |
| `readme_gen.py` | README regeneration logic (`--generate-readme` CLI flag) |
| `pipeline_spec.py` | Pipeline topology spec (SPEC v2 nodes + edges) for `/api/pipeline` |
| `gh_cache.py` | Shared in-memory TTL+timeout wrapper for all `gh` CLI calls (PRD #993): `gh_fetch(args, *, ttl, timeout)` runs `gh` via `subprocess.run(timeout=...)`, caches stdout by normalized command key, degrades to last-known "stale" value (or "computing" sentinel) on timeout/failure. Thread-safe; `GhResult` carries `fetched_at`+`source` for honest "as of" display. Timeout default 5s; TTL per-call-site. Prevents any single slow `gh` call from blocking the request path. |
| `_gitfiles.py` | Git-tree file enumeration: `git_ls_files()` lists tracked files via `git ls-files` so discovery functions use the git index rather than `os.walk` or `glob`, avoiding false positives from untracked/generated files and working correctly in worktree-isolated sessions. Used by `discovery.py` and `health.py` for reliable path enumeration. |
| `collector.py` | PRD-run artifact collection from GitHub API; `--compare` golden-run mode |
| `comparison.py` | Run-vs-spec edge comparison, `run_pass` verdict, downloadable JSON report; violation detectors include `merged_without_ci` (non-trivial PR merged without SUCCESS `ci` statusCheckRollup — bootstrap-mode: PRs predating ADR-0042 are grandfathered); failed/not-found collection returns `run_pass: false` plus an explicit `error` (and `not_found: true`) field — never a vacuous PASS |
| `runtime_observer.py` | Runtime observation layer (ADR-0055): reads v2 workflow-events.jsonl within a PRD's time window and evaluates all 24 runtime-tier edge predicates (user→skill, critic-dispatch, sequence-ordering, verdict-return, bash-evidence, conditional-advisory classes); returns per-edge states (`runtime-confirmed` / `runtime-unobserved` / `not-observable` / `not-exercised`) + a `coverage_strip` summary; never touches `run_pass` or violations |
| `transcript.py` | Session transcript reader (PRD #898): resolves the active Claude Code session transcript JSONL + subagent JSONL files, normalises records into v2 event shape; `get_session_events()` powers `/api/session-live`; `build_firing_tree()` / `get_session_firing()` powers `/api/session-firing`; `get_runtime_reading()` powers `/api/runtime-reading`; `resolve_dispatch_to_prd(n)` maps a slice/PR number to its parent PRD via the gh issue hierarchy (body-parse + disk cache at `.claude/cache/prd-correlation-cache.json` + in-process TTL cache; degrades to `#N (gh unavailable)` when gh is offline; disk cache is permanent/gitignored — warm calls return in <3s); `build_firing_tree()` returns `nested_groups` (PRD → slice → dispatch nesting using `_get_prd_subissue_slices()` for structural correlation), `research_other` (Explore/Plan/general-purpose/claude-code-guide dispatches segregated from workflow nodes), and a `partial` flag per PRD node (set when gh sub-issues include slices absent from the current transcript); CLI: `--self` (event count + last 5 events) and `--firing` (dispatch tree grouped by parent PRD) |

## Usage

Run from the **project root**:

```bash
python dashboard/server.py
```

Then open `http://localhost:8765` in any modern browser.

## Tabs

- **Architecture** — pipeline mermaid diagram with evidence-tier styling (github/runtime/unmeasurable edges) + auto-discovered component graph (skills, agents, hooks, ADRs). Includes a per-run Trail comparison panel: run picker, per-edge states (confirmed/missing/not-reached/not-exercised/unexpected for github-tier; `runtime-confirmed`/`runtime-unobserved`/`not-observable`/`not-exercised` for runtime-tier), violation detectors (unreviewed-merge, no-closes-slice, slice-no-pr), and repo rollup (PASS/FAIL per run PASS definition in ADR-0053 D3). Each comparison view shows (a) a **Coverage strip** summarising `43 declared = 17 github + 24 runtime + 2 unmeasurable-by-design` with per-state counts (confirmed / runtime-confirmed / not-reached / not-exercised / runtime-unobserved / not-observable / unmeasurable) and a zero-`not-evaluated` assertion; (b) a **runtime observation summary** line (`N confirmed · M unobserved · K not-observable · J not-exercised · 2 unmeasurable`) reflecting the `runtime_observer.py` pass over the PRD's window events; (c) a prominent banner: when the comparison payload carries `error` or `not_found` (collection failure), `_renderErrorBanner()` renders a **"PRD #N NOT FOUND"** or **"Collection ERROR"** banner (styled `trail-golden-banner fail`) and never shows a PASS state; otherwise a **declared == measured: PASS/FAIL banner** (derived from `run_pass`) plus a **Download report** link. Runtime states use ADR-0055 D4 liveness gating: if the capture feed is dead (no events in PRD window), all 24 runtime edges read `not-observable` (never `runtime-unobserved`). Click any node to view its file.
- **Live** — two-lane real-time view of agent work in flight (PRD #680):
  - **Lane A — run progress (artifact-fed, hook-independent):** polls `/api/live-progress` (backed by `dashboard/collector.py`) to show the most recent open PRD's per-slice stage states (PRD posted, slices open/closed, PR open/merged, reviewer verdict rounds, production-verify) with timestamps. Works even when Claude Code hooks are dead (e.g. resumed sessions never register hooks — a known Claude Code behavior).
  - **Lane B — session chat transcript (hook-fed, incremental):** polls `/api/live-poll?cursor=<cursor>` with an opaque file-identity cursor (`<mtime>:<byte-offset>`; legacy bare-int cursors force a reset) against `.claude/logs/workflow-events.jsonl`. Reads only appended bytes (O(delta)), resets cursor on truncation. Groups events by `session_id`; default selection is the most recent session with ≥1 event. Renders as a chat transcript: `user_prompt` events appear as user bubbles (blue left-border, prompt excerpt); `session_stop` events with `assistant_tail` appear as assistant bubbles (green left-border, labeled "turn end"); tool beats (`skill_invoke`, `agent_start`, `agent_complete`, `bash_complete`, `grill_qa`) render as indented compact rows between bubbles. `agent_complete` rows show an APPROVE/BLOCK badge when their `tail` field contains a fenced `VERDICT:` line (live enrichment only — authoritative verdicts remain GitHub comments per ADR-0053 D1). Chronological order (oldest at top); auto-scrolls to newest only when already at the bottom (never yanks a scrolled-up reader). Every row expands on click to show the full captured payload inline (no re-fetch). Filter chips — **All / Chat / Tools** — hide tool beats or bubbles client-side.
  - **Status pills:** capture pill (`LIVE — last event Ns ago` when fresh; `INACTIVE — this session never registered hooks` when dead) and collector pill: `ok` state (blue, gh succeeded and found an open PRD), `empty` state (muted, gh succeeded but no open PRD — "No open PRD"), `error` state (red, gh CLI unavailable — "gh CLI unavailable — check auth/PATH"), `auth_dead` (red, unauthenticated), `OFFLINE — showing cached trails` (amber). Honest degradation: Lane A runs independently when Lane B is inactive.
- **Health** — A real-time honesty board: each check verifies that one workflow invariant actually holds right now (docs in sync, rules enforced, hooks live, no drift). The board is green only when the guarantee is real, not when prose claims it (make-real goal, PRD #927). Checks are grouped under human-readable section headers — "Docs in sync", "Rules enforced", "Hooks live", "No drift", "Verification integrity", "Release gates", "Session hygiene" — derived from a per-check `group` field in `health.py`'s `_CHECK_GROUP_MAP` (slice #931). Includes: DOCS-1..DOCS-11 docs-currency grid, STRUCT-1..STRUCT-10 structure grid (both formerly `/audit-meta`; now run automatically inside `codebase-critic` per-PRD pass, per PRD #919 slice #920), AS-AUDIT aggregate subagent-prompt quality row (formerly `/audit-subagents`; now runs automatically in CI CHECK 18 via `python3 dashboard/health.py --check AS-AUDIT`, per PRD #919 slice #921), substrate health rows (CAPTURE-SLO, HOOK-INTEGRITY, ISOLATION-GROUP, RULE-COVERAGE, CRITIC-HEALTH, SPEC-COVERAGE), verification-integrity rows (BLIND-RATE, RESIDUAL-RATIO, PROOF-PRESENCE, MERGE-INTEGRITY, CAPTURE-SHAPE, GREEN-MAIN, SILENT-DRIFT), registry-integrity row (PARITY), cascade-finder status. **Click any row** to open a description popup sourced from each check function's docstring (slice #966 / PRD #957 — universal click + docstring descriptions replace the former DOCS/AS-only detail panel with shared panel for all 8 groups). **Per-check enrichment fields** (PRD #957): each check result carries `description` (from docstring — slice #966), `data_state` ∈ {pass, actionable, no-data} (slice #967), `purpose_group` (one of 6 headings: "Docs in sync", "Rules enforced", "Telemetry live", "Verification integrity", "Isolation/hygiene", "Release gates" — slice #968), and `what_to_do` (action text for actionable checks — slice #968). **Purpose-group UI** (slice #968): the Health tab renders checks under ≥5 purpose-group headings before the legacy group grids; CAPTURE-SLO + HOOK-INTEGRITY + HOOK-LIVENESS appear as a single "Telemetry live" composite row (rollup = worst actionable sub-signal; no-data excluded from rollup). Registered-but-UI-invisible checks (BRANCH-TOPOLOGY, FRONTMATTER-COVERAGE, META-TRIPWIRE, RELEASE-READY) are explicitly excluded from `PURPOSE_GROUP_MAP` with a code comment. All rows are also accessible headlessly via the **registry CLI**: `python dashboard/health.py --check <ID>` (exit 0 = PASS/WARN, exit 1 = FAIL, exit 2 = unknown ID) and `python dashboard/health.py --list` (print all registered IDs, one per line). Per ADR-0064 D3.
  - **CAPTURE-SLO** — sessions with ≥1 non-boundary event / total over the last 20 sessions from `workflow-events.jsonl`; red when <50% live (captures the resumed-session blind spot as a visible badge per PRD #763 §2 cr.7). Window N=20 is the implementer's choice, documented here.
  - **HOOK-INTEGRITY** — attempt-vs-ok beacon ratio per hook name from `hook-fires.jsonl`; red when any hook's ok count < attempt count (indicates silently-dropped executions) or when `status: ERROR` beacons are present.
  - **ISOLATION-GROUP** — orphaned dirs under `.claude/worktrees/` (dirs no longer registered in `git worktree list`); prune-drift worktrees (0-ahead + clean); red on orphans, amber on prune-drift only.
  - **RULE-COVERAGE** — ratio of CLAUDE.md section-1 numbered rules that name a deterministic check or carry `(advisory)` tag; always WARNs (never FAILs) until the wave-3 retrofit pass (per ADR-0056 D3); pre-existing rules ≤22 are grandfathered per ADR-0008 D8; lists unchecked-and-untagged rules above the bootstrap cutoff as "NEW unchecked-untagged".
  - **SPEC-COVERAGE** — per PRD: `|cited §2 criteria in slice Covers: lines| / |total §2 criteria|`; orphan (uncovered) + phantom (nonexistent) counts; bind-forward from slicer/slicer-critic prompt merge per ADR-0066 D2. Registry key: `SPEC-COVERAGE`. Per slice #798.
  - **DOCS-11** — dead-citation check: citations of superseded ADR decisions in `.claude/` runtime prompts lacking superseding references, modulo a documented seeded allowlist; live values honest. Per ADR-0064 D2. Registry key: `DOCS-11`.
  - **PARITY** — registry IDs == declared IDs == CI-consumed IDs; standing parity alarm per ADR-0064 D3; DOCS-*/STRUCT-* IDs declared in `codebase-critic.md` (post slice #920); AS-AUDIT is registered directly in CHECK_REGISTRY (post slice #921, no separate declared-ID source); FAIL on orphan CI-consumed IDs (CI calls a check the registry doesn't have); WARN on declared IDs not in the registry. Registry key: `PARITY`.
  - **Verification-integrity card** — evaluators from ADR-0060/0061/0062/0063/0066 (slices #783, #797, #799):
    - **BLIND-RATE** — fraction of `agent_start` events in `workflow-events.jsonl` whose `input` field begins with `BLIND-REVIEW`; pre-migration denominator labeled honestly; bind-forward ADR-0060 D5.
    - **RESIDUAL-RATIO** — (JUDGMENT + EXTRACT_FAILED) / total QA-plan rows across closed PRDs; measures whether EARS-shaped criteria reduce extraction residuals over time (ADR-0066 D1 drop-criterion). Registry key: `RESIDUAL-RATIO`. Per slice #797.
    - **PROOF-PRESENCE** — per merged non-trivial PR above the bind-forward threshold: changed-path globs classify the mandatory proof class (ADR-0061 D1 route table); the PR body + comment trail is grepped for route-appropriate proof tokens (browser: `.png`/`inner_text:`; hook-fire: `exit=`; command-run: `exit=`; static: `grep count=`); rolling rate reported; missing PRs named.
    - **MERGE-INTEGRITY** — scans last 10 closed PRDs' PR comment trails for `behind-retried: N` patterns (ADR-0062 D1 MERGE_STATUS field); honest zero when no BEHIND races have been recorded.
    - **CAPTURE-SHAPE** — `root-cause`-labeled issues: 3-heading regex (`**Symptom:**` / `**Root cause:**` / `**Proposed:**`) conformance fraction + named non-conformers; evidence-presence sub-metric (fenced/quoted block in Symptom section); unlabeled-candidate counter (3-section `captured` issues missing the label — surfaced only, never auto-relabeled). Per ADR-0063 D1/D2/D3.
    - **GREEN-MAIN** — last `main_green` event sha + lag (`git rev-list <sha>..origin/main --count`) + age since event timestamp; red on lag > 0 or stale > 24h. Per ADR-0062 D3.
    - **SILENT-DRIFT** — PRDs whose body changed post-first-dispatch without a matching `## AMENDMENT <n>` comment (target 0); data from GitHub issue edit history API with graceful WARN fallback when the API is unavailable/rate-limited; PRDs predating slice #799's merge are grandfathered per ADR-0004 D2. Registry key: `SILENT-DRIFT`. Per ADR-0066 D3 / slice #799. **API reliability note:** the GitHub issues timeline API (`/issues/:number/timeline`) requires `token` scope and is subject to rate limiting; `WARN` is the expected result when the API is unavailable or returns an empty history. During the bind-forward ramp-up period (first weeks after slice #799 ships) most PRDs will show no edit history, so `WARN` is normal — `FAIL` only triggers once a body-edit-without-amendment is positively detected.
  - **Regression-memory card** — test suite health + quarantine + eval rows (wave 4, ADR-0067; slices #822, #825, #828):
    - **TESTS-COLLECTED** — count of test items collected in `tests/`; prefers pytest, falls back to stdlib unittest; PASS when count > 0; FAIL when suite exists but is empty; WARN when `tests/` not present. Per ADR-0067 D1.
    - **TEST-ORDERING** — % of `fix/*` PRs (post-activation) where a test-touching commit precedes the fix commit (bias isolation per ADR-0067 D2); grandfathers PRs predating slice #816 (R-PROVE activation); WARN on no post-activation fix PRs yet. Registry key: `TEST-ORDERING`.
    - **QUARANTINE-SLA** — quarantine register size + oldest-entry age from `tests/quarantine.txt`; FAIL when any entry is >30 days old (SLA breach); WARN when entries exist within SLA; PASS when empty. Entries carry `[quarantined: YYYY-MM-DD]` date tags for age tracking. Per ADR-0067 D4.
    - **EVAL-REVIEWER** — last eval pass rate for `reviewer` critic from `tests/evals/results.json`; WARN on no-run (honest no-baseline bucket); WARN when stale >14 days or pass rate <1.0; PASS when rate == 1.0 and fresh. Per ADR-0067 D5.
    - **EVAL-PRD-CRITIC** — same as EVAL-REVIEWER but for `prd-critic`. Per ADR-0067 D5.
    - **EVAL-SLICER-CRITIC** — same as EVAL-REVIEWER but for `slicer-critic`. Per ADR-0067 D5.
  - **Hygiene + session-start card** — workspace hygiene and session-injection rows (wave 4, ADR-0068; slice #826):
    - **UNTRACKED-SIZE** — count + total size of untracked files under tracked dirs (e.g. `qa-proof/`); WARN when count exceeds threshold (honest day-one accumulation is the starting value per ADR-0004 D2). Per ADR-0068 D1.
    - **LOG-ROTATION** — `workflow-events.jsonl` size vs 5 MB rotation cap; WARN when >80% of cap (proactive notice); FAIL when at or above cap with no rotation archive (rotation is broken). Per ADR-0068 D1.
    - **STALE-BRANCHES** — remote branches that are merged or >14 days inactive without an open PR; advisory only — detectors report, humans act; graceful WARN on network failure. Per ADR-0068 D1.
    - **REQUIRED-LABELS** — labels declared in `bootstrap.sh` vs live repo; WARN on any missing label (bootstrap.sh drift indicator). Per ADR-0068 D1.
    - **DEAD-ROUTES** — API routes served by `dashboard/server.py` but never fetched by `dashboard/index.html`; honest day-one pre-existing dead routes are the starting value. Per ADR-0068 D1.
    - **SESSION-INJECTION** — one `session_context_injected` event per `session_id` in the last 20-session window; PASS when all sessions have an injection event; WARN when <50% (hook not yet active or pre-hook sessions dominate). Per ADR-0068 D3.
    - **R-SENSITIVE-DETECTOR** — enforcement-path merged PRs (post-bootstrap) without a `human-ack` signal (label or body keyword); always returns WARN (historical tally — blocking is enforced at review time by R-SENSITIVE in the reviewer rubric); activated at PRD #813 closing slice per ADR-0064 D4.
  - **FRONTMATTER-COVERAGE** — % of `.claude/agents/*.md` files with explicit `model:` frontmatter; PASS when 100%; FAIL on any missing. Per ADR-0027 D1 (fleet-economics machinery removed per ADR-0071 D2; FRONTMATTER-COVERAGE retained as the ADR-0027 D1 `model:` invariant).
  - **Liveness + integrity card** — cross-session liveness and proof-integrity rows:
    - **STALE-SERVER** — detects a dashboard server whose process start-time predates the last `root-sync` event (stale worktree server serving stale state); WARN when the running server's PID start-time is older than the most recent git HEAD advance; PASS when fresh or no server detected. Captures the resumed-session stale-server trap (#726/#685).
    - **PROMOTION-LAG** — commits-behind between `develop` HEAD and `main` HEAD, plus age of the last `promotion` event; WARN when lag > 0 and age > 24 h (develop has accumulated un-promoted work); PASS when lag == 0 or last promotion is recent. Surfaces the develop→main promotion backlog.
    - **HOOK-LIVENESS** — verifies at least one `session_context_injected` or `hook_fire` event with `exit=0` was recorded for the current session; WARN when hooks appear dark (worktree session with no `CLAUDE_PROJECT_DIR` and no git-common-dir fallback); PASS when at least one liveness beacon is present. See memory note "hooks go dark on empty CLAUDE_PROJECT_DIR".
    - **PROOF-INTEGRITY** — per merged non-trivial PR in the post-bind-forward window: checks that the `PRODUCTION_VERIFY: PASS` claim in the PR comment trail is backed by a real `PROOF_SOURCE:` session ID that exists in `workflow-events.jsonl` and is not fixture-patterned; WARN when no qualifying PRs yet; FAIL when a PASS claim has a missing or fixture-tagged source. Per ADR-0061 D2.
    - **META-TRIPWIRE** — scans the last promotion batch for guardrail-machinery path touches (`.github/workflows/**`, `.claude/settings.json`, `.claude/hooks/**`, `tools/ci-checks.sh`, `.githooks/**`, `*-critic.md`, or the promotion gate itself); WARN when a batch touching guardrail paths was promoted without a recorded `human-ack` signal; PASS when all guardrail batches carry an ack. Per ADR-0070 D4.

## API reference

| Endpoint | Description |
|---|---|
| `/api/pipeline` | Pipeline topology (nodes + edges) for the Architecture tab |
| `/api/health` | All health check results (TTL-cached); powers the Health tab |
| `/api/runs` | Workflow-event log sessions (events.py); powers the Live tab lane B |
| `/api/live-progress` | Latest open PRD per-slice stage states (collector.py); Lane A |
| `/api/live-poll` | Incremental event poll with opaque cursor; Lane B |
| `/api/file` | Serve repo file contents (path-traversal-protected) |
| `/api/session-live` | Current-session transcript events (slice #899): list of normalised events from the active `.jsonl` transcript; `source` field names the transcript file; `event_count` total events; auto-refreshes every 15s in the Live tab ("Session live" panel). Events are ordered oldest-at-top (stable). |
| `/api/session-firing` | Per-PRD firing tree from transcript (slice #901/#959): `nested_groups` — PRD → slice → dispatch nested trace tree derived from transcript + gh hierarchy; `research_other` — built-in Task types (Explore / Plan / general-purpose / claude-code-guide) segregated from PRD/slice nodes; `groups` — flat PRD-keyed buckets (backward-compat); `dispatch_count`; `completeness_count`. A PRD node carries `partial: true` when its gh sub-issues include slices whose dispatches are absent from the current transcript. The `resolve_dispatch_to_prd()` correlation is disk-cached at `.claude/cache/prd-correlation-cache.json` (permanent, gitignored) so a warm call returns in <3s vs ~37s cold. Auto-refreshes every 30s in the Live tab ("Session firing tree" panel). |
| `/api/runtime-reading` | Current-session runtime reading from transcript (slice #928): event count, session age, last event timestamp + type, `source` field naming the transcript file; `no_session: true` when no transcript found |
| `/api/meta` | Server sha + session handshake (banner freshness gate per slice #773) |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DASH_PORT` | `8765` | Port the server listens on |
| `DASH_NO_BROWSER` | _(unset)_ | Set to any non-empty value to suppress auto-opening the browser on startup (useful in CI, headless, or automated contexts) |
| `DASH_REPO_SLUG` | _(derived)_ | Override the runtime-derived GitHub repo slug (`owner/name`). Normally derived automatically via `gh repo view` → `git remote get-url origin` parse. Set this only when both derivation paths fail (e.g. detached HEAD, no `origin` remote). Must be in `owner/name` form. Single github.com origin assumed (multi-remote / GHE out of scope — see PRD #753 §3). |

Example with custom port:

```bash
DASH_PORT=9876 python dashboard/server.py
```

On Windows Git Bash:

```bash
DASH_PORT=9876 python dashboard/server.py
```

## Cross-platform notes

- Uses Python 3 stdlib only — no `pip install` required.
- Uses `pathlib` throughout; works on Windows Git Bash, Linux, macOS.
- Binds to `localhost` only; not accessible from other machines (per PRD non-goals).
- Path-traversal protection on `/api/file`: rejects any `path` that resolves outside the repo root.

## Intended audience

Solo developer (you). Observation tool; advisory only. Does not replace `tools/cascade-finder.py` — it displays its output. The former `/audit-meta` structure+docs-currency checks now run automatically inside the `codebase-critic` per-PRD pass (PRD #919 slice #920). The former `/audit-subagents` subagent-prompt quality checks now run automatically in CI via CHECK 18 (`python3 dashboard/health.py --check AS-AUDIT`, per PRD #919 slice #921).

## Two-tier delivery model (PRD #836 / ADR-0070 D1)

The project uses a `develop`/`main` two-tier model (wave 5 of workflow v2). Agents merge slices to `develop`; `main` advances only via the deterministic promotion gate (`tools/promote.sh` + `RELEASE-READY`). The Health tab surfaces two new monitoring areas for this model:

**Promotion panel** (Health tab, `RELEASE-READY` + `BRANCH-TOPOLOGY` rows):
- **RELEASE-READY** — evaluates all six conditions from ADR-0070 D2: (a) CI green on `develop` HEAD; (b) full test suite passes; (c) latest production-verify PASS with DOM-attested proof; (d) green-develop streak intact; (e) zero open `needs-human` items; (f) unpromoted batch touches no guardrail-machinery path. A `verdict="true"` means `tools/promote.sh` may advance `main`. Details report the first failing condition when held. Per ADR-0070 D2 / ADR-0072 D1.
- **BRANCH-TOPOLOGY** — confirms slice PRs target `develop` (not `main`) and that `main` advances only via recorded `promotion` events. Dormant until slice #843 wires full branch-protection. Per ADR-0070 D1 / ADR-0072 D3.

**Promotion event log** (`/api/runs`, Live tab lane B): each promotion appends a `{"v":2,"event":"promotion","from":"develop","to":"main","sha":"..."}` event to `.claude/logs/workflow-events.jsonl`; the Green-develop row shows `main`↔`develop` lag (commits-behind + age) and the last promotion sha.

The sole human-blocking role in this model is acking guardrail-machinery promotions (batches touching `.github/workflows/**`, `.claude/settings.json`, `.claude/hooks/**`, `tools/ci-checks.sh`, `.githooks/**`, `*-critic.md`, or the promotion gate itself). The `R-SENSITIVE-DETECTOR` health row tallies these and their ack status. Per ADR-0070 D4.

## Fixtures

`dashboard/fixtures/` contains sample payloads used by `tools/ci-checks.sh` CHECK 8 to mechanically validate the Agent-hook payload schema. CHECK 8 uses a python3 parser (not jq): it loads the fixture via `json.load()` and asserts that `tool_input.subagent_type` resolves to a non-empty value — proving the python3 path handles the canonical `PostToolUse·Agent` payload correctly. Regenerate `dashboard/fixtures/agent-payload-sample.json` from a real `PostToolUse·Agent` payload if Claude Code's hook schema changes.
