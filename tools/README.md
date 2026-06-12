# tools/

Scripts for cascade-aware workflow support and post-dispatch worktree enforcement.
Intended for use by humans and subagents.

**Note:** not all tools in this directory are advisory or read-only. `worktree-guard.sh`
is an enforcement tool that deletes worktrees, removes local branches, and deletes
remote branches — it modifies repository state. `cascade-finder.py` and `ci-checks.sh`
are advisory/read-only.

---

## worktree-guard.sh

Post-dispatch worktree leak-guard and root ff-sync. **Enforcement tool** — modifies
repository state (deletes worktrees, local branches, and remote branches). Invoked by
the `/ship` orchestrator after each isolated `implementer` or `reviewer` dispatch
(per ADR-0058 D3 + [ADR-0041](../decisions/0041-origin-main-source-of-truth.md) D1/D3).

### Subcommands

**`branch-restore <expected-branch>`** — checks whether the current worktree drifted
off `<expected-branch>` and restores it via ff-only checkout of `origin/main`. If the
current HEAD has diverged from `origin/main` (local commits exist), exits **non-zero**
with a divergence message — the old silent force-reset is retired (ADR-0058 D3). A
dirty tree is a no-op (safe exit 0 — orchestrator's own work is left untouched).

**`root-sync`** — ff-syncs the root repo to `origin/main` after a successful merge.
Non-zero on dirty tree or ff failure.

**`prune`** — removes landed dispatch worktrees (`agent-*` prefix only) to prevent
unbounded accumulation. Two reclamation paths:
1. **Landed path:** branch has a merged PR + no open PR.
2. **No-PR reclamation path (ADR-0058 D3):** worktree with no PR at all is reclaimed
   when clean + 0-ahead-of-main + older than 24 hours (avoids racing in-flight
   dispatches).
After removing a worktree, deletes the local branch and the remote branch if present.
Exits **non-zero** if any targeted worktree could not be removed.

### Exit codes

All subcommands exit **non-zero on unrepaired violations** (ADR-0058 D3). The
orchestrator detects guard failures via the exit code. Unknown modes also exit non-zero.
Soft-degrade on transient network/fetch errors: root-sync fetch failure exits 0;
prune with gh absent exits 0 with no work done.

### Safety guarantees

Only removes worktrees whose `basename` starts with `agent-` (the harness
dispatch-tree prefix). Skips the current worktree and the root repo worktree. A
worktree with a live-pid lock is never forcibly removed. These guards make it
impossible to remove the root repo, orchestrator session trees, or non-dispatch trees
regardless of their branch state.

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
