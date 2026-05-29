# project-claude workflow dashboard

Local web visualizer for the project's autonomous pipeline. Slice 1 of [PRD #345](https://github.com/vojtech-stas/project-claude/issues/345).

## Usage

Run from the **project root**:

```bash
python dashboard/server.py
```

Then open `http://localhost:8765` in any modern browser.

## Tabs

- **Architecture** — pipeline mermaid diagram + auto-discovered component graph (skills, agents, hooks, ADRs). Click any node to view its file.
- **Live** — placeholder; real-time event stream ships in slice 2 of PRD #345.
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

## Roadmap

- **Slice 2 of PRD #345** — Live event stream (SSE from `.claude/logs/workflow-events.jsonl`) + SessionStart auto-start hook + ADR-0033.
