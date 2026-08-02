#!/usr/bin/env python3
"""
dashboard/tracestore.py — disposable SQLite derived read-model for the
canonical v3 trace-span log (tools/trace.py).

Slice #1080 (PRD #1075 criteria 2a/2b): folds trace-v3.jsonl into an indexed
SQLite read-model at `.claude/state/trace.db` (gitignored, disposable) and
answers the acid-path causal-chain query from an indexed lookup instead of
tools/trace.py's linear scan. Per ADR-0075 D2, the db is explicitly
REFOLDABLE-FROM-LOG, NEVER a second source of truth: all writes happen via
`fold()` only — no ad hoc INSERT anywhere else in this module or its callers
(SPIDR-R guard, see PRD #1075 §6 rabbit-hole). Any divergence from
tools/trace.py's linear-scan answer is a fold bug, fixed in `fold()`, never
patched by writing to the db directly.

Canonical JSONL log path: reused verbatim from tools/trace.py's
`trace_log_path()` (git-common-dir-parent resolution, TRACE_LOG_OVERRIDE env
seam) — no independent git path-resolution logic lives here (DRY, and it
avoids re-introducing the #1091 MSYS_NO_PATHCONV `git -C <pwd-derived>`
trap: this module never calls `git -C` itself; it delegates entirely to
tools/trace.py's already-safe plain `git rev-parse` resolution, which relies
on the process's own cwd rather than a path argument).

DB path: `<git-common-dir-parent>/.claude/state/trace.db` (sibling of
`.claude/logs/`), gitignored; `TRACE_DB_OVERRIDE` env var is the test seam
(mirrors TRACE_LOG_OVERRIDE).

Refold semantics: `fold()` performs a FULL drop-and-recreate of the `spans`
table from a full re-read of the JSONL (via `trace.read_spans()` — the
IDENTICAL parser tools/trace.py's own linear scan uses, guaranteeing
parity). There is no row-level incremental/delta fold anywhere in this
module. The one optimization implemented is an mtime short-circuit:
`fold(force=False)` (the default used by every query entrypoint below)
SKIPS the rebuild entirely when the JSONL's mtime has not changed since the
mtime recorded in the db's `_meta` table from the last fold. This is a
cheap freshness check, not incremental folding — every actual rebuild is a
full drop-and-recreate of `spans` (disposability requirement: delete db,
refold, identical answer; `force=True` always rebuilds).

Python API (for dashboard reuse):
  db_path(override=None) -> str
  fold(log_path=None, db_path_=None, force=False) -> int  (spans folded)
  acid_path(pr_number, log_path=None, db_path_=None) -> list[dict] | None
  span_tree(trace_id, log_path=None, db_path_=None) -> list[dict]

CLI (parity with `tools/trace.py path --pr <n>` — trace.py's linear scan
remains the fallback/cross-check per the slice's instruction):
  python dashboard/tracestore.py fold
  python dashboard/tracestore.py path --pr <n>

utf-8: the JSONL is always read via trace.read_spans() (utf-8), and SQLite
TEXT columns store native Python str (unicode) without any extra encoding
step.
"""
import argparse
import importlib.util
import json
import os
import sqlite3
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
_TRACE_PY = os.path.join(_REPO_ROOT, "tools", "trace.py")


def _load_trace():
    # Loaded under a distinct module name — never "trace" (stdlib collision,
    # same defensive pattern as tools/pipe/pr-open's _load_trace()).
    spec = importlib.util.spec_from_file_location("trace_v3", _TRACE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def db_path(override=None):
    """Resolve the canonical trace.db path. TRACE_DB_OVERRIDE env var is the
    test seam (mirrors tools/trace.py's TRACE_LOG_OVERRIDE)."""
    if override:
        return override
    env = os.environ.get("TRACE_DB_OVERRIDE")
    if env:
        return env
    trace = _load_trace()
    log_path = trace.trace_log_path()
    # log_path == <root>/.claude/logs/trace-v3.jsonl -> <root>/.claude/state/trace.db
    claude_dir = os.path.dirname(os.path.dirname(log_path))
    return os.path.join(claude_dir, "state", "trace.db")


def _connect(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(conn):
    conn.executescript(
        """
        DROP TABLE IF EXISTS spans;
        CREATE TABLE spans (
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            kind TEXT,
            name TEXT,
            parent_span_id TEXT,
            pr TEXT,
            dur_ms INTEGER,
            attrs_json TEXT NOT NULL
        );
        CREATE INDEX idx_spans_pr ON spans(pr);
        CREATE INDEX idx_spans_trace_id ON spans(trace_id);
        """
    )


def fold(log_path=None, db_path_=None, force=False):
    """(Re)build the trace.db read-model from the canonical JSONL log.

    See module docstring "Refold semantics" for the full contract. Returns
    the number of spans currently represented in the db (either freshly
    folded, or the pre-existing count when a same-mtime fold is skipped).
    """
    trace = _load_trace()
    resolved_log = log_path or trace.trace_log_path()
    resolved_db = db_path_ or db_path()

    log_mtime = (
        os.path.getmtime(resolved_log) if os.path.exists(resolved_log) else None
    )

    conn = _connect(resolved_db)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        if not force:
            row = conn.execute(
                "SELECT value FROM _meta WHERE key = 'log_mtime'"
            ).fetchone()
            if (
                row is not None
                and log_mtime is not None
                and float(row["value"]) == log_mtime
            ):
                try:
                    count_row = conn.execute(
                        "SELECT COUNT(*) AS c FROM spans"
                    ).fetchone()
                    if count_row is not None:
                        return count_row["c"]
                except sqlite3.OperationalError:
                    pass  # spans table missing/corrupt -> fall through, rebuild

        spans = trace.read_spans(resolved_log)
        _create_schema(conn)
        for s in spans:
            attrs = s.get("attrs", {}) or {}
            pr_val = attrs.get("pr")
            conn.execute(
                "INSERT INTO spans (span_id, trace_id, ts, kind, name, "
                "parent_span_id, pr, dur_ms, attrs_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    s.get("span_id"),
                    s.get("trace_id"),
                    s.get("ts"),
                    s.get("kind"),
                    s.get("name"),
                    s.get("parent_span_id"),
                    str(pr_val) if pr_val is not None else None,
                    s.get("dur_ms"),
                    json.dumps(attrs, sort_keys=True),
                ),
            )
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('log_mtime', ?)",
            (str(log_mtime) if log_mtime is not None else "",),
        )
        conn.commit()
        return len(spans)
    finally:
        conn.close()


def _row_to_span(row):
    """Reconstruct the exact v3 span shape emit_span() writes: optional
    fields (parent_span_id, name, dur_ms) are OMITTED when falsy/absent,
    never written as null — mirrors tools/trace.py's emit_span()."""
    span = {
        "v": 3,
        "ts": row["ts"],
        "trace_id": row["trace_id"],
        "span_id": row["span_id"],
        "kind": row["kind"],
        "attrs": json.loads(row["attrs_json"]) if row["attrs_json"] else {},
    }
    if row["parent_span_id"]:
        span["parent_span_id"] = row["parent_span_id"]
    if row["name"]:
        span["name"] = row["name"]
    if row["dur_ms"] is not None:
        span["dur_ms"] = row["dur_ms"]
    return span


def acid_path(pr_number, log_path=None, db_path_=None):
    """Indexed acid-path causal-chain query — same semantics as
    tools/trace.py's acid_path (the linear-scan cross-check): every span
    whose attrs.pr == pr_number, PLUS every span sharing a trace_id with one
    of those matches, ts-ordered. Returns None when the PR has no recorded
    spans at all (pre-v3 / untraced — the loud-fail contract preserved)."""
    resolved_db = db_path_ or db_path()
    fold(log_path=log_path, db_path_=resolved_db, force=False)
    conn = _connect(resolved_db)
    try:
        pr_str = str(pr_number)
        matched = conn.execute(
            "SELECT DISTINCT trace_id FROM spans WHERE pr = ?", (pr_str,)
        ).fetchall()
        if not matched:
            return None
        trace_ids = [r["trace_id"] for r in matched]
        placeholders = ",".join("?" for _ in trace_ids)
        rows = conn.execute(
            f"SELECT * FROM spans WHERE trace_id IN ({placeholders}) ORDER BY ts",
            trace_ids,
        ).fetchall()
        return [_row_to_span(r) for r in rows]
    finally:
        conn.close()


def span_tree(trace_id, log_path=None, db_path_=None):
    """Span-tree API: every span for one trace_id, ts-ordered. Returns []
    when the trace_id is unknown (a caller probing existence gets an empty
    list — distinct from acid_path's loud-fail None for an untraced PR)."""
    resolved_db = db_path_ or db_path()
    fold(log_path=log_path, db_path_=resolved_db, force=False)
    conn = _connect(resolved_db)
    try:
        rows = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY ts", (trace_id,)
        ).fetchall()
        return [_row_to_span(r) for r in rows]
    finally:
        conn.close()


def _cmd_fold(args):
    count = fold(force=True)
    print(f"folded {count} spans into {db_path()}")
    return 0


def _cmd_path(args):
    chain = acid_path(args.pr)
    if chain is None:
        print(f"no recorded trace for PR #{args.pr}", file=sys.stderr)
        return 1
    for s in chain:
        dur = s.get("dur_ms")
        dur_str = f" dur_ms={dur}" if dur is not None else ""
        parent = s.get("parent_span_id")
        parent_str = f" parent={parent}" if parent else ""
        print(
            f"{s.get('ts')} kind={s.get('kind')} span={s.get('span_id')}"
            f"{parent_str} attrs={json.dumps(s.get('attrs', {}), sort_keys=True)}"
            f"{dur_str}"
        )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tracestore.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fold = sub.add_parser("fold", help="force-refold the sqlite read-model")
    p_fold.set_defaults(func=_cmd_fold)

    p_path = sub.add_parser("path", help="indexed acid-test causal-path query")
    p_path.add_argument("--pr", required=True, type=int)
    p_path.set_defaults(func=_cmd_path)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
