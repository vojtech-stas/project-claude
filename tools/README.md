# tools/

Advisory scripts for cascade-aware workflow support. Intended for use by humans and
(in future phases) subagents. All tools in this directory are advisory — they emit
informational output only; they do not modify any files.

---

## cascade-finder.py

Discovers files that reference or depend on a given target file. Useful before
editing a file: know what else is likely to need updating.

### Usage

```
python tools/cascade-finder.py <target_file> [--json]
```

**Arguments:**

- `target_file` — repo-relative or absolute path to the file whose dependents you
  want to discover.
- `--json` — emit output as a JSON array instead of a Markdown table.

**Output columns (Markdown table, default):**

| Column | Meaning |
|---|---|
| File | Repo-relative path to the file that references the target |
| Line | Line number of the reference |
| Reference type | How the file references the target (see below) |
| Context | Excerpt of the matching line (max 80 chars) |

**Reference types (ranked highest to lowest):**

| Type | Weight | Description |
|---|---|---|
| `edge` | 4 | A typed `**EdgeType:** [[path]]` link in a `docs/current/**/*.md` file |
| `grep-slug` | 3 | ADR slug literal (e.g. `ADR-0031`) — only for `decisions/` targets |
| `grep-filename` | 2 | The file's basename appears in the referencing file |
| `grep-concept` | 1 | The concept's YAML `title:` field appears — only for `docs/current/concepts/` |

Results are deduplicated by `(file, line)` and ranked by weight descending, then by
file path, then by line number.

### Examples

```
# Who depends on ADR-0031?
python tools/cascade-finder.py decisions/0031-knowledge-architecture-v2.md

# Who depends on the audit-meta skill?
python tools/cascade-finder.py .claude/skills/audit-meta/SKILL.md

# Emit JSON for programmatic downstream use
python tools/cascade-finder.py CLAUDE.md --json
```

### Requirements

- Python 3.9+ (stdlib only — no `pip install` required)
- Cross-platform: Windows, macOS, Linux
- `git` in PATH is preferred (uses `git ls-files` for scope); falls back to
  `os.walk` if not in a git repo

### Exit code

Always 0. Advisory output only — never modifies any file.

---

## Intended audience

- **Humans** — run before editing a key file to know what cascade-updates are likely.
- **Future Phase 2 `cascade-updater`** — programmatic caller via `--json` output;
  feeds the mechanical-update script per PRD §5 Phase 2 plan.
- **Future Phase 3 `kb-maintainer`** — LLM propagator (`T8` from
  [ADR-0031](../decisions/0031-knowledge-architecture-v2.md) D10); ingests JSON to
  scope which files to read and propose synthesis updates for.
- **Future Phase 4 slicer/reviewer integration** — the slicer could query this tool
  at slice-creation time to surface cascade-doc obligations; the reviewer could gate
  on `R-CASCADE-CLEAN` per a future ADR.

---

## Phase roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 1 (this PR) | `cascade-finder.py` — advisory discovery | Done |
| 2 | `cascade-updater.py` — mechanical dependency update | Future PRD |
| 3 | `kb-maintainer` generator subagent — LLM-synthesised propagation | Future PRD (ADR-0031 T8) |
| 4 | Slicer + reviewer integration — `R-CASCADE-CLEAN` gate | Future PRD (new ADR) |
| 5 | KB simplification — delete duplicate surfaces, collapse redundancy | Future PRD |

---

## Context

This tool is the Phase 1 foundation for the cascade-aware workflow refactor described
in [ADR-0031](../decisions/0031-knowledge-architecture-v2.md) D7 (`impact-analyst`
deferred) and D8 (`kb-maintainer` deferred). The typed-edge graph in atomic notes
(D3) exists but nothing queries it — this tool is the active piece that was missing.

Per [ADR-0031](../decisions/0031-knowledge-architecture-v2.md) D10, the T7/T8
migration tasks are scheduled as future PRDs; this tool enables that migration by
making the dependency graph legible at human invocation time today.
