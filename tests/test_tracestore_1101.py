"""
tests/test_tracestore_1101.py

Regression tests for issue #1101 — tracestore concurrency prerequisites for
the dashboard repoint (slice #1082, PRD #1075 criterion 9). Reproduces (a)
against the OLD `dashboard/tracestore.py` (pre-#1082) and proves the fix on
the CURRENT module:

  (1) executescript commit-gap: the old `_create_schema()` used
      `conn.executescript()` with DROP+CREATE, which auto-commits BEFORE the
      insert batch runs — a concurrent reader querying `spans` mid-fold saw
      COUNT(*)=0 (spurious "no recorded trace"). Fixed by building the next
      generation into a scratch table and swapping it in atomically under
      one explicit transaction.
  (2) WAL mode + busy_timeout: two concurrent folds must serialize on the
      write lock rather than raising "database is locked".
  (3) INSERT OR IGNORE on span_id: a duplicate span_id must not raise
      IntegrityError or break subsequent queries.
  (4) ORDER BY ts, rowid tie-break: same-timestamp spans must sort in
      insertion order (matching tools/trace.py's stable linear-scan sort).

(5) size+mtime composite freshness is covered by
    tests/test_tracestore_1080.py's
    test_freshness_composite_key_refolds_on_stale_tick_edge.

Test-first discipline: test_concurrent_reader_never_sees_zero_during_fold
FAILS against the tracestore.py shipped in PR #1095 (executescript
commit-gap) and PASSES against this slice's atomic-swap fix. Run via:
  python -m pytest tests/test_tracestore_1101.py -v
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
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


def _load_tracestore():
    return _load_module(TRACESTORE_PY, "tracestore_test_1101")


def _write_fixture_log(path, spans):
    with open(path, "w", encoding="utf-8") as f:
        for s in spans:
            f.write(json.dumps(s) + "\n")


def _make_many_spans(n, trace_prefix="pr-race"):
    """Generate `n` distinct minimal spans so fold()'s insert loop takes
    measurable wall-clock time — widens the race window enough for a
    polling reader thread to reliably observe a commit-gap bug if present."""
    spans = []
    for i in range(n):
        spans.append({
            "v": 3,
            "ts": f"2026-08-02T10:{i % 60:02d}:{i % 60:02d}Z",
            "trace_id": f"{trace_prefix}-{i}",
            "span_id": f"race-{i}",
            "kind": "agent_dispatch",
            "attrs": {"pr": str(9100 + i)},
        })
    return spans


class TestTracestore1101Prerequisites(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.tmpdir.name, "trace-v3.jsonl")
        self.db_path = os.path.join(self.tmpdir.name, "trace.db")
        self.tracestore = _load_tracestore()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_concurrent_reader_never_sees_zero_during_fold(self):
        """(#1101 prereq 1) A warm db (4 spans) is refolded against a MUCH
        larger fixture (500 spans) while a separate connection polls
        COUNT(*) FROM spans in a tight loop. The reader must NEVER observe
        0 (or a missing-table error) — it must see either the full OLD
        generation or the full NEW one, never a transient in-between."""
        warm_spans = _make_many_spans(4, trace_prefix="pr-warm")
        _write_fixture_log(self.log_path, warm_spans)
        warm_count = self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        self.assertEqual(warm_count, 4)

        big_spans = _make_many_spans(500, trace_prefix="pr-big")
        _write_fixture_log(self.log_path, big_spans)

        zero_or_missing_seen = threading.Event()
        stop = threading.Event()

        def reader_loop():
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            try:
                while not stop.is_set():
                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) FROM spans"
                        ).fetchone()
                        if row is not None and row[0] == 0:
                            zero_or_missing_seen.set()
                            break
                    except sqlite3.OperationalError:
                        # "no such table: spans" is ALSO a manifestation of
                        # the commit-gap bug (DROP committed, CREATE not yet
                        # run) — counts as a failure too.
                        zero_or_missing_seen.set()
                        break
                    time.sleep(0.001)
            finally:
                conn.close()

        reader = threading.Thread(target=reader_loop, daemon=True)
        reader.start()
        try:
            self.tracestore.fold(
                log_path=self.log_path, db_path_=self.db_path, force=True
            )
        finally:
            stop.set()
            reader.join(timeout=2)

        self.assertFalse(
            zero_or_missing_seen.is_set(),
            "concurrent reader observed count=0 / missing table mid-fold "
            "(executescript commit-gap regression, #1101 prereq 1)",
        )

    def test_wal_mode_and_busy_timeout_configured(self):
        """(#1101 prereq 2) Every connection enables WAL journal mode and a
        nonzero busy_timeout."""
        _write_fixture_log(self.log_path, _make_many_spans(2))
        self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        conn = self.tracestore._connect(self.db_path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(str(mode).lower(), "wal")
        self.assertGreater(int(busy), 0)

    def test_concurrent_folds_do_not_raise_database_locked(self):
        """(#1101 prereq 2) Multiple threads calling fold(force=True)
        concurrently against the SAME db must serialize on the write lock
        (busy_timeout) rather than raising 'database is locked'."""
        _write_fixture_log(self.log_path, _make_many_spans(50))
        errors = []

        def do_fold():
            try:
                self.tracestore.fold(
                    log_path=self.log_path, db_path_=self.db_path, force=True
                )
            except sqlite3.OperationalError as e:
                errors.append(e)

        threads = [threading.Thread(target=do_fold) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(
            errors, [], f"concurrent folds raised OperationalError: {errors}"
        )

    def test_duplicate_span_id_insert_or_ignore_no_integrity_error(self):
        """(#1101 prereq 3) A duplicate span_id must not raise
        IntegrityError, and queries for OTHER PRs in the same fold must
        still work (not broken by the duplicate)."""
        dup_spans = [
            {"v": 3, "ts": "2026-08-02T10:00:00Z", "trace_id": "pr-9001",
             "span_id": "dup1", "kind": "pr_opened", "attrs": {"pr": "9001"}},
            {"v": 3, "ts": "2026-08-02T10:00:01Z", "trace_id": "pr-9001",
             "span_id": "dup1", "kind": "pr_opened", "attrs": {"pr": "9001"}},
            {"v": 3, "ts": "2026-08-02T10:00:02Z", "trace_id": "pr-9002",
             "span_id": "s2", "kind": "pr_opened", "attrs": {"pr": "9002"}},
        ]
        _write_fixture_log(self.log_path, dup_spans)

        # Must not raise sqlite3.IntegrityError.
        count = self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        self.assertEqual(count, len(dup_spans))  # read_spans sees 3 lines

        # The duplicate is deduplicated (INSERT OR IGNORE keeps the first).
        conn = self.tracestore._connect(self.db_path)
        try:
            stored = conn.execute(
                "SELECT COUNT(*) AS c FROM spans WHERE span_id = 'dup1'"
            ).fetchone()["c"]
        finally:
            conn.close()
        self.assertEqual(stored, 1)

        # Other PR's query is unaffected by the duplicate.
        result = self.tracestore.acid_path(
            9002, log_path=self.log_path, db_path_=self.db_path
        )
        self.assertIsNotNone(result)
        self.assertEqual([s["span_id"] for s in result], ["s2"])

    def test_same_ts_tiebreak_matches_insertion_order(self):
        """(#1101 prereq 4) Spans sharing an identical ts must sort by
        insertion (rowid) order, matching tools/trace.py's stable
        linear-scan sort exactly."""
        same_ts = "2026-08-02T10:00:00Z"
        spans = [
            {"v": 3, "ts": same_ts, "trace_id": "pr-9001", "span_id": "a",
             "kind": "k1", "attrs": {"pr": "9001"}},
            {"v": 3, "ts": same_ts, "trace_id": "pr-9001", "span_id": "b",
             "kind": "k2", "attrs": {"pr": "9001"}},
            {"v": 3, "ts": same_ts, "trace_id": "pr-9001", "span_id": "c",
             "kind": "k3", "attrs": {"pr": "9001"}},
        ]
        _write_fixture_log(self.log_path, spans)

        trace = _load_module(TRACE_PY, "trace_v3_test_1101")
        expected = trace.acid_path(9001, log_path=self.log_path)

        self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        result = self.tracestore.acid_path(
            9001, log_path=self.log_path, db_path_=self.db_path
        )

        self.assertEqual([s["span_id"] for s in expected], ["a", "b", "c"])
        self.assertEqual(
            [s["span_id"] for s in result],
            [s["span_id"] for s in expected],
            "same-ts tie-break must match trace.py's stable insertion-order sort",
        )

    def test_span_tree_same_ts_tiebreak(self):
        """(#1101 prereq 4) span_tree() also applies the rowid tie-break."""
        same_ts = "2026-08-02T11:00:00Z"
        spans = [
            {"v": 3, "ts": same_ts, "trace_id": "t1", "span_id": "x",
             "kind": "k1", "attrs": {}},
            {"v": 3, "ts": same_ts, "trace_id": "t1", "span_id": "y",
             "kind": "k2", "attrs": {}},
        ]
        _write_fixture_log(self.log_path, spans)
        self.tracestore.fold(
            log_path=self.log_path, db_path_=self.db_path, force=True
        )
        tree = self.tracestore.span_tree(
            "t1", log_path=self.log_path, db_path_=self.db_path
        )
        self.assertEqual([s["span_id"] for s in tree], ["x", "y"])


if __name__ == "__main__":
    unittest.main()
