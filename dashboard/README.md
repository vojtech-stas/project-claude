# project-claude workflow dashboard

Local web visualizer for the project's autonomous pipeline.

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
  - **Lane B — session feed (hook-fed, incremental):** polls `/api/runs?since=<cursor>` with a byte-cursor against `.claude/logs/workflow-events.jsonl`. Reads only appended bytes (O(delta)), resets cursor on truncation. Groups events by `session_id`; default selection is the most recent session with ≥1 event. `agent_complete` events whose `tail` field contains a fenced `VERDICT: APPROVE|BLOCK` line render an APPROVE/BLOCK badge (live enrichment only — authoritative verdicts remain GitHub comments per ADR-0053 D1).
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

`dashboard/fixtures/` contains sample payloads used by `tools/ci-checks.sh` CHECK 8 to mechanically validate Agent-hook jq paths. Regenerate from a real `PostToolUse·Agent` payload if Claude Code's hook schema changes.
