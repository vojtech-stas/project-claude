"""
tests/test_tracestore_1080.py

Regression / new-feature tests for slice #1080 (PRD #1075 criteria 2a/2b) —
the disposable SQLite derived read-model (`dashboard/tracestore.py`) that
folds the canonical v3 trace-span log (`tools/trace.py`) into an indexed
store and answers the acid-path causal-chain query without a linear scan.

Test-first discipline: this commit lands BEFORE `dashboard/tracestore.py`
exists. FAILS before impl: every test below errors (FileNotFoundError raised
by `_load_tracestore()` in setUp) because the module under test does not
exist yet. PASSES after impl: `dashboard/tracestore.py` lands in the next
commit and satisfies every assertion here.

Covers:
  (a) fold-then-query parity: the indexed query returns the SAME ordered
      path as tools/trace.py's linear-scan acid_path, for a fixture JSONL
      log spanning multiple PRs and a same-trace_id sibling span lacking
      attrs.pr (the dispatch-span case the acid-path chain-gather logic
      must include on both sides identically).
  (b) disposability: delete the db file, re-query (which re-folds), get the
      IDENTICAL answer — the store is refoldable-from-log, never a second
      source of truth (ADR-0075 D2).
  (c) mtime-based freshness semantics: fold(force=False) SKIPS the rebuild
      when the JSONL's mtime is unchanged since the last fold, and performs
      a FULL refold (never row-level incremental) once the mtime changes —
      documents+proves the module's stated full-refold-or-skip semantics.
  (d) unknown PR -> loud fail: both the Python API (returns None, matching
      tools/trace.py's None) and the CLI (`path --pr <n>` exits non-zero
      with an explicit "no recorded trace" stderr message) preserve the
      pre-v3 loud-fail contract — no fabricated partial answer.
  (e) span_tree API: ordered spans for one trace_id (the dashboard-facing
      span-tree function the slice requires alongside acid_path).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_tracestore_1080.py -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
DASHBOARD_DIR = REPO_ROOT / "dashboard"
TRACE_PY = TOOLS_DIR / "trace.py"
TRACESTORE_PY = DASHBOARD_DIR / "tracestore.py"


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_trace():
    """Import tools/trace.py under a distinct module name (never "trace" —
    that shadows/collides with the stdlib `trace` coverage module)."""
    if not TRACE_PY.exists():
        raise FileNotFoundError(f"tools/trace.py not found at {TRACE_PY}")
    return _load_module(TRACE_PY, "trace_v3_tracestore_test")


def _load_tracestore():
    if not TRACESTORE_PY.exists():
        raise FileNotFoundError(
            f"dashboard/tracestore.py not found at {TRACESTORE_PY}"
        )
    return _load_module(TRACESTORE_PY, "tracestore_test")


# One trace-id with a sibling dispatch span (no attrs.pr) + pr_opened +
# pr_merged, plus one unrelated PR's span — mirrors real pr-open/pr-merge
# wrapper output shape.
_FIXTURE_SPANS = [
    {
        "v": 3, "ts": "2026-08-02T10:00:00Z", "trace_id": "pr-9001",
        "span_id": "s0", "kind": "agent_dispatch",
        "attrs": {"actor": "implementer"},
    },
    {
        "v": 3, "ts": "2026-08-02T10:00:05Z", "trace_id": "pr-9001",
        "span_id": "s1", "kind": "pr_opened",
        "attrs": {"pr": "9001", "branch": "feat/x"},
    },
    {
        "v": 3, "ts": "2026-08-02T10:05:00Z", "trace_id": "pr-9001",
        "span_id": "s2", "kind": "pr_merged", "parent_span_id": "s1",
        "dur_ms": 125, "attrs": {"pr": "9001", "sha": "abc123"},
    },
    {
        "v": 3, "ts": "2026-08-02T11:00:00Z", "trace_id": "pr-9002",
        "span_id": "s3", "kind": "pr_opened",
        "attrs": {"pr": "9002", "branch": "feat/y"},
    },
]


def _write_fixture_log(path, spans=None):
    spans = spans if spans is not None else _FIXTURE_SPANS
    with open(path, "w", encoding="utf-8") as f:
        for s in spans:
            f.write(json.dumps(s) + "\n")


class TestTracestoreFoldQueryParity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.tmpdir.name, "trace-v3.jsonl")
        self.db_path = os.path.join(self.tmpdir.name, "trace.db")
        _write_fixture_log(self.log_path)
        self.trace = _load_trace()
        self.tracestore = _load_tracestore()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_fold_then_query_matches_linear_scan(self):
        folded = self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        self.assertEqual(folded, len(_FIXTURE_SPANS))

        expected = self.trace.acid_path(9001, log_path=self.log_path)
        actual = self.tracestore.acid_path(
            9001, log_path=self.log_path, db_path_=self.db_path
        )

        self.assertIsNotNone(expected)
        self.assertIsNotNone(actual)
        self.assertEqual(
            [s["span_id"] for s in expected], ["s0", "s1", "s2"]
        )
        self.assertEqual(
            [s["span_id"] for s in expected],
            [s["span_id"] for s in actual],
        )
        for exp_s, act_s in zip(expected, actual):
            self.assertEqual(exp_s, act_s, "indexed query must match linear-scan span exactly")

    def test_disposability_delete_db_refold_identical(self):
        self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        before = self.tracestore.acid_path(
            9001, log_path=self.log_path, db_path_=self.db_path
        )

        os.remove(self.db_path)
        self.assertFalse(os.path.exists(self.db_path))

        after = self.tracestore.acid_path(
            9001, log_path=self.log_path, db_path_=self.db_path
        )
        self.assertEqual(before, after)

    def test_mtime_freshness_skip_then_full_refold_on_change(self):
        first_count = self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        self.assertEqual(first_count, len(_FIXTURE_SPANS))

        # Overwrite the fixture with MORE spans but preserve the exact
        # mtime -> fold(force=False) must SKIP the rebuild (freshness check,
        # not incremental) and report the OLD count.
        extra_spans = _FIXTURE_SPANS + [
            {
                "v": 3, "ts": "2026-08-02T12:00:00Z", "trace_id": "pr-9003",
                "span_id": "s4", "kind": "pr_opened", "attrs": {"pr": "9003"},
            },
        ]
        stat_before = os.stat(self.log_path)
        _write_fixture_log(self.log_path, extra_spans)
        os.utime(self.log_path, (stat_before.st_atime, stat_before.st_mtime))

        skipped_count = self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=False
        )
        self.assertEqual(
            skipped_count, first_count,
            "same-mtime fold(force=False) must SKIP the rebuild, not refold",
        )

        # Now bump the mtime -> fold(force=False) must detect staleness and
        # perform a FULL refold (never row-level incremental), reflecting
        # every span present in the file at that point.
        newer = stat_before.st_mtime + 5
        os.utime(self.log_path, (newer, newer))
        refolded_count = self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=False
        )
        self.assertEqual(refolded_count, len(extra_spans))

    def test_unknown_pr_returns_none_matching_trace_py(self):
        expected = self.trace.acid_path(424242, log_path=self.log_path)
        self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        actual = self.tracestore.acid_path(
            424242, log_path=self.log_path, db_path_=self.db_path
        )
        self.assertIsNone(expected)
        self.assertIsNone(actual)

    def test_unknown_pr_cli_loud_fail_nonzero(self):
        env = dict(os.environ)
        env["TRACE_LOG_OVERRIDE"] = self.log_path
        env["TRACE_DB_OVERRIDE"] = self.db_path
        result = subprocess.run(
            [sys.executable, str(TRACESTORE_PY), "path", "--pr", "424242"],
            capture_output=True, text=True, env=env,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no recorded trace", result.stderr.lower())

    def test_span_tree_api_returns_ordered_spans_for_trace_id(self):
        self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        tree = self.tracestore.span_tree(
            "pr-9001", log_path=self.log_path, db_path_=self.db_path
        )
        self.assertEqual([s["span_id"] for s in tree], ["s0", "s1", "s2"])

    def test_cli_path_parity_with_trace_py_cli(self):
        """CLI parity: `dashboard/tracestore.py path --pr N` output matches
        `tools/trace.py path --pr N` output (same span ordering/fields)."""
        env = dict(os.environ)
        env["TRACE_LOG_OVERRIDE"] = self.log_path
        env["TRACE_DB_OVERRIDE"] = self.db_path

        trace_result = subprocess.run(
            [sys.executable, str(TRACE_PY), "path", "--pr", "9001"],
            capture_output=True, text=True, env=env,
        )
        tracestore_result = subprocess.run(
            [sys.executable, str(TRACESTORE_PY), "path", "--pr", "9001"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(trace_result.returncode, 0)
        self.assertEqual(tracestore_result.returncode, 0)
        self.assertEqual(trace_result.stdout, tracestore_result.stdout)


if __name__ == "__main__":
    unittest.main()
