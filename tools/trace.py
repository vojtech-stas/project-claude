#!/usr/bin/env python3
"""
tools/trace.py — stdlib v3 pipeline trace-span emitter + acid-path query CLI.

Slice #1078 (PRD #1075 walking skeleton): appends one v3 JSON span line per
pipeline side-effect transition (pr_opened, pr_merged, ...) to the canonical
trace log, and answers "show one PR's complete causal path" from recorded
spans alone (no gh calls, no regex reconstruction) — the acid test named in
PRD #1075 criteria 1 / 2a / 2b.

Canonical log path: <git-common-dir-parent>/.claude/logs/trace-v3.jsonl
(NEVER cwd-relative — the promote.sh/#1038 log-stranding class this store is
built to avoid from day one). Resolution order:
  1. TRACE_LOG_OVERRIDE env var (absolute path) — test seam, mirrors the
     telemetry_root._telemetry_log_root() override pattern already used
     elsewhere in this repo.
  2. `git rev-parse --path-format=absolute --git-common-dir`, parent dir,
     + .claude/logs/trace-v3.jsonl.

Schema (v3), one JSON object per line, utf-8:
  {
    "v": 3,
    "ts": "<UTC ISO-8601, e.g. 2026-08-02T12:00:00Z>",
    "trace_id": "<caller-supplied grouping id, e.g. 'pr-<n>'>",
    "span_id": "<auto short-uuid if omitted>",
    "parent_span_id": "<optional>",
    "kind": "<pr_opened|pr_merged|...>",
    "name": "<optional human label>",
    "attrs": {...},
    "dur_ms": <optional int>
  }
Optional fields (parent_span_id, name, dur_ms) are OMITTED from the record
entirely when not supplied (never written as null) — keeps this walking-
skeleton schema lean; only the five wrapped transitions + enrichment spans
exist yet (YAGNI — no schema for hypothetical future stages, per PRD #1075
§6 rabbit-hole).

CLI:
  python tools/trace.py emit --kind pr_opened --trace-id prd-1075 \\
      [--span-id ...] [--parent ...] --attr pr=1234 --attr sha=abc \\
      [--name ...] [--dur-ms 250]
  python tools/trace.py path --pr 1234

Python API (for reuse by tools/pipe/pr-open, tools/pipe/pr-merge, and any
future wrapper CLI):
  emit_span(trace_id, kind, name=None, span_id=None, parent_span_id=None,
            attrs=None, dur_ms=None, log_path=None) -> dict
  acid_path(pr_number, log_path=None) -> list[dict] | None
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone


def _git_common_dir_parent():
    """Resolve <git-common-dir-parent> — the canonical, worktree-independent
    root every worktree shares (git-common-dir is ".../<root>/.git")."""
    out = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    common_dir = os.path.abspath(out)
    return os.path.dirname(common_dir)


def trace_log_path():
    """Resolve the canonical trace-v3.jsonl path (TRACE_LOG_OVERRIDE-able)."""
    override = os.environ.get("TRACE_LOG_OVERRIDE")
    if override:
        return override
    root = _git_common_dir_parent()
    return os.path.join(root, ".claude", "logs", "trace-v3.jsonl")


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_span_id():
    return uuid.uuid4().hex[:12]


def emit_span(trace_id, kind, name=None, span_id=None, parent_span_id=None,
              attrs=None, dur_ms=None, log_path=None):
    """Append one v3 span line to the canonical trace log.

    Returns the record dict actually written (span_id/ts filled in).
    Raises OSError if the log path cannot be created/written.
    """
    record = {
        "v": 3,
        "ts": _now_iso(),
        "trace_id": trace_id,
        "span_id": span_id or _new_span_id(),
        "kind": kind,
    }
    if parent_span_id:
        record["parent_span_id"] = parent_span_id
    if name:
        record["name"] = name
    record["attrs"] = attrs or {}
    if dur_ms is not None:
        record["dur_ms"] = dur_ms

    path = log_path or trace_log_path()
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record


def read_spans(log_path=None):
    """Read + parse every line of the trace log. Malformed lines are skipped
    (one bad line must never crash the acid query)."""
    path = log_path or trace_log_path()
    if not os.path.exists(path):
        return []
    spans = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                spans.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return spans


def acid_path(pr_number, log_path=None):
    """Ordered causal chain for one PR: every span whose attrs.pr == pr_number
    (compared as strings), PLUS every other span sharing a trace_id with one
    of those matches (its causal parents/siblings — dispatch/verdict spans
    land here as later slices add them). Returns None if the PR has no
    recorded spans at all (the pre-v3 / untraced case).
    """
    pr_str = str(pr_number)
    spans = read_spans(log_path)
    matched = [s for s in spans if str(s.get("attrs", {}).get("pr")) == pr_str]
    if not matched:
        return None

    trace_ids = {s.get("trace_id") for s in matched}
    chain = [s for s in spans if s.get("trace_id") in trace_ids]

    seen = set()
    deduped = []
    for s in chain:
        sid = s.get("span_id")
        if sid in seen:
            continue
        seen.add(sid)
        deduped.append(s)
    deduped.sort(key=lambda s: s.get("ts", ""))
    return deduped


def _parse_attrs(pairs):
    attrs = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(f"--attr must be key=value, got: {pair!r}")
        k, v = pair.split("=", 1)
        attrs[k] = v
    return attrs


def _cmd_emit(args):
    attrs = _parse_attrs(args.attr)
    record = emit_span(
        trace_id=args.trace_id,
        kind=args.kind,
        name=args.name,
        span_id=args.span_id,
        parent_span_id=args.parent,
        attrs=attrs,
        dur_ms=args.dur_ms,
    )
    print(record["span_id"])
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
    parser = argparse.ArgumentParser(prog="trace.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_emit = sub.add_parser("emit", help="append one v3 span")
    p_emit.add_argument("--kind", required=True)
    p_emit.add_argument("--trace-id", required=True)
    p_emit.add_argument("--span-id", default=None)
    p_emit.add_argument("--parent", default=None)
    p_emit.add_argument("--name", default=None)
    p_emit.add_argument("--attr", action="append", default=[])
    p_emit.add_argument("--dur-ms", type=int, default=None)
    p_emit.set_defaults(func=_cmd_emit)

    p_path = sub.add_parser("path", help="acid-test causal-path query")
    p_path.add_argument("--pr", required=True, type=int)
    p_path.set_defaults(func=_cmd_path)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
