# project-claude workflow dashboard

Local web visualizer for the project's autonomous pipeline.

## Backend modules

The backend is split into flat sibling modules under `dashboard/`; `server.py` is a thin HTTP facade that re-exports everything:

| Module | Responsibility |
|---|---|
| `server.py` | HTTP request handler, named re-exports for all `/api/*` routes, module-level globals (caches, locks, `KNOWN_CRITICS`) |
| `live.py` | Live-progress cache + background refresh, `/api/live-progress` + `/api/live-poll` polling, capture-pill state |
| `discovery.py` | Skill/agent/hook/ADR filesystem discovery for `/api/pipeline` and the component graph |
| `health.py` | `check_docs1`–`check_docs10` audit-meta checks + AS-* audit-subagents checks, TTL-cached `/api/health` |
| `events.py` | Workflow-event log reading (`/api/runs`), byte-cursor incremental poll, session grouping |
| `workitems.py` | GitHub Issues fetch + `/api/workitems` response |
| `readme_gen.py` | README regeneration logic (`--generate-readme` CLI flag) |
| `pipeline_spec.py` | Pipeline topology spec (SPEC v2 nodes + edges) for `/api/pipeline` |
| `collector.py` | PRD-run artifact collection from GitHub API; `--compare` golden-run mode |
| `comparison.py` | Run-vs-spec edge comparison, `run_pass` verdict, downloadable JSON report |

## Usage

Run from the **project root**:

```bash
python dashboard/server.py
```

Then open `http://localhost:8765` in any modern browser.

## Tabs

- **Architecture** — pipeline mermaid diagram with evidence-tier styling (github/runtime/unmeasurable edges) + auto-discovered component graph (skills, agents, hooks, ADRs). Includes a per-run Trail comparison panel: run picker, per-edge states (confirmed/missing/not-reached/not-exercised/unexpected), violation detectors (unreviewed-merge, no-closes-slice, slice-no-pr), and repo rollup (PASS/FAIL per run PASS definition in ADR-0053 D3). Each comparison view shows a prominent **declared == measured: PASS/FAIL banner** (derived from `run_pass` in the comparison report) plus a **Download report** link serving the full JSON report as an attachment. Click any node to view its file.
- **Live** — two-lane real-time view of agent work in flight (PRD #680):
  - **Lane A — run progress (artifact-fed, hook-independent):** polls `/api/live-progress` (backed by `dashboard/collector.py`) to show the most recent open PRD's per-slice stage states (PRD posted, slices open/closed, PR open/merged, reviewer verdict rounds, production-verify) with timestamps. Works even when Claude Code hooks are dead (e.g. resumed sessions never register hooks — a known Claude Code behavior).
  - **Lane B — session chat transcript (hook-fed, incremental):** polls `/api/live-poll?cursor=N` with a byte-cursor against `.claude/logs/workflow-events.jsonl`. Reads only appended bytes (O(delta)), resets cursor on truncation. Groups events by `session_id`; default selection is the most recent session with ≥1 event. Renders as a chat transcript: `user_prompt` events appear as user bubbles (blue left-border, prompt excerpt); `session_stop` events with `assistant_tail` appear as assistant bubbles (green left-border, labeled "turn end"); tool beats (`skill_invoke`, `agent_start`, `agent_complete`, `bash_complete`, `grill_qa`) render as indented compact rows between bubbles. `agent_complete` rows show an APPROVE/BLOCK badge when their `tail` field contains a fenced `VERDICT:` line (live enrichment only — authoritative verdicts remain GitHub comments per ADR-0053 D1). Chronological order (oldest at top); auto-scrolls to newest only when already at the bottom (never yanks a scrolled-up reader). Every row expands on click to show the full captured payload inline (no re-fetch). Filter chips — **All / Chat / Tools** — hide tool beats or bubbles client-side.
  - **Status pills:** capture pill (`LIVE — last event Ns ago` when fresh; `INACTIVE — this session never registered hooks` when dead) and collector pill (last successful `gh` fetch age / auth-dead warning / `OFFLINE — showing cached trails`). Honest degradation: Lane A runs independently when Lane B is inactive.
- **Health** — DOCS-1..DOCS-10 audit-meta grid, AS-* audit-subagents grid, cascade-finder status. Click any FAIL row to expand details.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DASH_PORT` | `8765` | Port the server listens on |
| `DASH_NO_BROWSER` | _(unset)_ | Set to any non-empty value to suppress auto-opening the browser on startup (useful in CI, headless, or automated contexts) |

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

Solo developer (you). Observation tool; advisory only. Does not replace `/audit-meta`, `/audit-subagents`, or `tools/cascade-finder.py` — it displays their output.

## Fixtures

`dashboard/fixtures/` contains sample payloads used by `tools/ci-checks.sh` CHECK 8 to mechanically validate the Agent-hook payload schema. CHECK 8 uses a python3 parser (not jq): it loads the fixture via `json.load()` and asserts that `tool_input.subagent_type` resolves to a non-empty value — proving the python3 path handles the canonical `PostToolUse·Agent` payload correctly. Regenerate `dashboard/fixtures/agent-payload-sample.json` from a real `PostToolUse·Agent` payload if Claude Code's hook schema changes.
