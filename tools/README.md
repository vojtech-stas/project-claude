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
| `grep-slug` | 3 | ADR slug literal (e.g. `ADR-0032`) — only for `decisions/` targets |
| `grep-filename` | 2 | The file's basename appears in the referencing file |
| `grep-concept` | 1 | The file's YAML `title:` field appears in the referencing file |

Note: the `edge` pass (typed `**EdgeType:** [[path]]` links in KB atomic notes)
was removed per ADR-0032 D6 — the separate KB layer is retired. The three
grep passes operate on the canonical substrate: `.claude/{agents,skills,hooks}` +
`decisions/` + `CLAUDE.md` + `README.md` + `tools/`.

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
| 3 | Slicer + reviewer integration — `R-CASCADE-CLEAN` gate | Future PRD (new ADR) |

Note: Phases 3 and 4 from the original roadmap (kb-maintainer T8, KB simplification)
were superseded by ADR-0032 (KB layer retired). The edge pass was removed from
Phase 1; Phases 2-3 continue as viable future PRDs.

---

## Context

This tool discovers files that reference a given target, helping identify cascade-doc
obligations before editing a key file. Per [ADR-0032](../decisions/0032-workflow-only-architecture.md)
D6, the discovery substrate is the canonical operational surfaces:
`.claude/{agents,skills,hooks}` + `decisions/` + `CLAUDE.md` + `README.md` + `tools/`.

The `edge` pass (typed-edge graph in KB atomic notes) was removed when the KB layer was
retired per ADR-0032. The three grep passes (`grep-slug`, `grep-filename`, `grep-concept`)
remain and operate on the updated substrate.
