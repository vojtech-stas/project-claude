#!/usr/bin/env python3
"""cascade-finder.py — advisory tool that finds files referencing a given target file.

Given a target file path, enumerates the files in the repository that depend on or
reference that file. Cross-platform, stdlib only. Advisory output only (exit 0 always).

Usage:
    python tools/cascade-finder.py <target_file> [--json]

Part of the cascade-aware workflow foundation. See tools/README.md and
decisions/0032-workflow-only-architecture.md D6 for context.

Discovery substrate (per ADR-0032 D6): .claude/{agents,skills,hooks} + decisions/ +
CLAUDE.md + README.md + tools/. The typed-edge discovery was removed when the KB layer
was retired per ADR-0032 D1; three grep passes remain.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Ensure stdout can handle UTF-8 on Windows (where cp1252 is the default)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


CONTEXT_MAX = 80
REF_WEIGHT = {"grep-slug": 3, "grep-filename": 2, "grep-concept": 1}

EXCLUDE_DIRS = {".git", ".claude/worktrees", "tool-results", "transcripts"}

# Discovery substrate per ADR-0032 D6: canonical operational surfaces only.
# KB layer retired per ADR-0032 D1; substrate is these prefix/path patterns.
SUBSTRATE_PREFIXES = (
    ".claude/agents/",
    ".claude/skills/",
    ".claude/hooks/",
    "decisions/",
    "tools/",
)
SUBSTRATE_EXACT = {"CLAUDE.md", "README.md"}


def find_repo_root(start: Path) -> Path:
    """Walk up from start to find the git repo root (contains .git/)."""
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return start.resolve()


def is_excluded(rel_path: str) -> bool:
    """Return True if the path should be excluded from search scope."""
    posix = Path(rel_path).as_posix()
    for excl in EXCLUDE_DIRS:
        if posix.startswith(excl + "/") or posix == excl:
            return True
    return False


def enumerate_scope(repo_root: Path, target_rel: str) -> list[str]:
    """Return list of repo-relative paths to search (tracked files or os.walk)."""
    use_git = False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        use_git = result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        use_git = False

    files = []
    if use_git:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            files = result.stdout.strip().splitlines()

    if not files:
        # Fallback: os.walk
        for dirpath, dirnames, filenames in os.walk(repo_root):
            rel_dir = Path(dirpath).relative_to(repo_root).as_posix()
            # Prune excluded dirs in-place
            dirnames[:] = [
                d
                for d in dirnames
                if not is_excluded(
                    (rel_dir + "/" + d).lstrip("./") if rel_dir != "." else d
                )
            ]
            for fname in filenames:
                if rel_dir == ".":
                    rel = fname
                else:
                    rel = rel_dir + "/" + fname
                files.append(rel)

    # Filter: only searchable text formats; exclude target itself and excluded dirs;
    # restrict to the ADR-0032 D6 substrate (canonical operational surfaces).
    target_posix = Path(target_rel).as_posix()
    EXTENSIONS = {".md", ".py", ".sh", ".json", ".txt", ".yaml", ".yml"}
    scoped = []
    for f in files:
        p = Path(f).as_posix()
        if is_excluded(p):
            continue
        if p == target_posix:
            continue
        if Path(f).suffix.lower() not in EXTENSIONS:
            continue
        # Restrict to substrate: prefix match OR exact name match
        in_substrate = (
            any(p.startswith(pfx) for pfx in SUBSTRATE_PREFIXES)
            or p in SUBSTRATE_EXACT
        )
        if not in_substrate:
            continue
        scoped.append(f)

    return scoped


def compute_anchors(repo_root: Path, target_rel: str) -> dict:
    """Compute the 3 search anchors from the target path.

    Per ADR-0032 D6, the typed-edge discovery and its concept_title anchor are retired
    along with the KB layer. Three passes remain: grep-slug, grep-filename, grep-concept
    (concept_title retained for files that happen to have a title: YAML field; harmless
    no-op when not present).
    """
    p = Path(target_rel)
    anchors = {
        "path": p.as_posix(),  # repo-relative path
        "filename": p.name,  # basename
        "slug": None,  # ADR-NNNN (if decisions/)
        "concept_title": None,  # title from YAML frontmatter (grep-concept pass)
    }

    # Slug anchor: extract ADR-NNNN from decisions/NNNN-*.md
    posix = p.as_posix()
    if posix.startswith("decisions/"):
        m = re.match(r"decisions/(\d{4})-", posix)
        if m:
            anchors["slug"] = "ADR-" + m.group(1)

    # Concept title anchor: parse ^title: from first 20 lines of YAML frontmatter
    # (still useful for any substrate file that carries a title: field)
    full_path = repo_root / p
    try:
        with open(full_path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= 20:
                    break
                m = re.match(r"^title:\s*(.+)", line)
                if m:
                    anchors["concept_title"] = m.group(1).strip()
                    break
    except OSError:
        pass

    return anchors


def truncate_context(line: str) -> str:
    """Strip whitespace and truncate to CONTEXT_MAX chars."""
    stripped = line.strip().replace("\n", " ").replace("\r", "")
    if len(stripped) > CONTEXT_MAX:
        return stripped[:CONTEXT_MAX - 1] + "…"
    return stripped


def discover_grep_slug(repo_root: Path, scoped: list[str], anchors: dict) -> list[tuple]:
    """Pass 2: grep for ADR-NNNN slug (only if target is a decisions/ file)."""
    slug = anchors.get("slug")
    if not slug:
        return []
    results = []
    for rel in scoped:
        full = repo_root / rel
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if slug in line:
                        results.append(
                            (rel, lineno, "grep-slug", truncate_context(line))
                        )
        except OSError:
            pass
    return results


def discover_grep_filename(repo_root: Path, scoped: list[str], anchors: dict) -> list[tuple]:
    """Pass 3: grep for filename (basename) in each scoped file."""
    filename = anchors.get("filename", "")
    if not filename:
        return []
    results = []
    for rel in scoped:
        full = repo_root / rel
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if filename in line:
                        results.append(
                            (rel, lineno, "grep-filename", truncate_context(line))
                        )
        except OSError:
            pass
    return results


def discover_grep_concept(repo_root: Path, scoped: list[str], anchors: dict) -> list[tuple]:
    """Pass 4: grep for concept title (case-sensitive) in each scoped file."""
    title = anchors.get("concept_title")
    if not title:
        return []
    results = []
    for rel in scoped:
        full = repo_root / rel
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if title in line:
                        results.append(
                            (rel, lineno, "grep-concept", truncate_context(line))
                        )
        except OSError:
            pass
    return results


def aggregate_and_rank(all_hits: list[tuple]) -> list[dict]:
    """Deduplicate by (file, line), keep highest-weight ref_type, then rank."""
    best: dict[tuple, dict] = {}
    for file, line, ref_type, context in all_hits:
        key = (file, line)
        weight = REF_WEIGHT.get(ref_type, 0)
        if key not in best or weight > REF_WEIGHT.get(best[key]["ref_type"], 0):
            best[key] = {
                "file": file,
                "line": line,
                "ref_type": ref_type,
                "context": context,
            }
    ranked = sorted(
        best.values(),
        key=lambda r: (
            -REF_WEIGHT.get(r["ref_type"], 0),
            r["file"],
            r["line"],
        ),
    )
    return ranked


def emit_markdown(results: list[dict]) -> None:
    """Emit a Markdown table to stdout."""
    if not results:
        print("_No dependents found._")
        return
    print("| File | Line | Reference type | Context |")
    print("|---|---|---|---|")
    for r in results:
        file_cell = r["file"].replace("|", "\\|")
        ctx_cell = r["context"].replace("|", "\\|")
        print(f"| {file_cell} | {r['line']} | {r['ref_type']} | {ctx_cell} |")


def emit_json(results: list[dict]) -> None:
    """Emit a JSON array to stdout."""
    print(json.dumps(results, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "cascade-finder: find files that reference or depend on a given file. "
            "Advisory output only — always exits 0."
        )
    )
    parser.add_argument(
        "target_file",
        help="Path to the file whose dependents you want to discover.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit output as JSON array instead of Markdown table.",
    )
    args = parser.parse_args()

    # Resolve repo root and target path
    repo_root = find_repo_root(Path(args.target_file).parent)
    target_path = Path(args.target_file)

    if not target_path.exists():
        # Try resolving relative to cwd
        target_path = Path.cwd() / args.target_file
    if not target_path.exists():
        print(
            f"Error: target file not found: {args.target_file}",
            file=sys.stderr,
        )
        sys.exit(0)  # advisory: exit 0 always

    target_path = target_path.resolve()
    repo_root = find_repo_root(target_path.parent)

    try:
        target_rel = target_path.relative_to(repo_root).as_posix()
    except ValueError:
        # Not inside the repo root somehow; use the raw path
        target_rel = Path(args.target_file).as_posix()

    anchors = compute_anchors(repo_root, target_rel)
    scoped = enumerate_scope(repo_root, target_rel)

    all_hits = []
    # typed-edge discovery removed per ADR-0032 D6 (KB layer retired)
    all_hits.extend(discover_grep_slug(repo_root, scoped, anchors))
    all_hits.extend(discover_grep_filename(repo_root, scoped, anchors))
    all_hits.extend(discover_grep_concept(repo_root, scoped, anchors))

    results = aggregate_and_rank(all_hits)

    if args.json:
        emit_json(results)
    else:
        emit_markdown(results)

    sys.exit(0)


if __name__ == "__main__":
    main()
