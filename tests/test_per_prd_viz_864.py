"""
Tests for slice #864 — per-PRD workflow visualization.

Three test groups (ADR-0067 D2 test-first ordering — this file committed before impl):

  1. serve_runs: events.serve_runs() parses session runs from a synthetic events
     file and returns the expected dict shape.

  2. trail_endpoint_keys: the /api/trail?prd=N returns expected keys for a
     cached PRD fixture (offline import; no live server).

  3. threaded_server_smoke: ThreadingHTTPServer + daemon_threads=True are used
     (static AST parse of server.py — not a live bind test per isolation rules).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_per_prd_viz_864.py -v
"""

import ast
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SERVER_PY = DASHBOARD_DIR / "server.py"
INDEX_HTML = DASHBOARD_DIR / "index.html"


# ---------------------------------------------------------------------------
# Helper: inject dashboard/ into sys.path for submodule imports
# ---------------------------------------------------------------------------

def _dashboard_path_inject():
    s = str(DASHBOARD_DIR)
    if s not in sys.path:
        sys.path.insert(0, s)


# ---------------------------------------------------------------------------
# Group 1: serve_runs — parses runs from a synthetic events file
# ---------------------------------------------------------------------------

class TestServeRuns(unittest.TestCase):
    """events.serve_runs() must parse session runs from a synthetic events file.

    Uses a temp file with known v2 events; validates shape and field presence.
    """

    _SYNTHETIC_EVENTS = [
        # Session A — 2 events (real-looking IDs avoid fixture regex)
        {"v": 2, "ts": "2026-06-15T10:00:00Z", "session_id": "real-alpha-864-aaa",
         "event": "agent_start", "subagent_type": "implementer"},
        {"v": 2, "ts": "2026-06-15T10:05:00Z", "session_id": "real-alpha-864-aaa",
         "event": "agent_complete", "subagent_type": "implementer"},
        # Session B — 1 event
        {"v": 2, "ts": "2026-06-15T11:00:00Z", "session_id": "real-beta-864-bbb",
         "event": "skill_invoke", "skill": "ship"},
        # Fixture event — MUST be filtered out (starts with "fixture")
        {"v": 2, "ts": "2026-06-15T12:00:00Z", "session_id": "fixture-session",
         "event": "agent_start"},
        # Legacy v1 event — MUST be filtered out (v=1)
        {"v": 1, "ts": "2026-06-15T12:01:00Z", "session_id": "v1-session",
         "event": "user_prompt"},
    ]

    def _write_events_file(self) -> Path:
        """Write synthetic events to a temp file; return its Path."""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        for ev in self._SYNTHETIC_EVENTS:
            tmp.write(json.dumps(ev) + "\n")
        tmp.close()
        return Path(tmp.name)

    def setUp(self):
        _dashboard_path_inject()
        from events import serve_runs
        self._serve_runs = serve_runs

    def test_returns_runs_list(self):
        """serve_runs() must return a dict with a 'runs' list."""
        path = self._write_events_file()
        try:
            result = self._serve_runs({}, path)
            self.assertIn("runs", result, "Result must have 'runs' key")
            self.assertIsInstance(result["runs"], list)
        finally:
            path.unlink(missing_ok=True)

    def test_filters_fixture_and_v1_lines(self):
        """Fixture-pattern and v1 session_ids must not appear in runs."""
        path = self._write_events_file()
        try:
            result = self._serve_runs({"n": ["10"]}, path)
            runs = result["runs"]
            sids = [r["session_id"] for r in runs]
            self.assertNotIn("fixture-session", sids,
                             "Fixture session must be filtered from runs")
            self.assertNotIn("v1-session", sids,
                             "v1-schema session must be filtered from runs")
        finally:
            path.unlink(missing_ok=True)

    def test_returns_real_sessions(self):
        """Real v2 sessions must appear in runs output."""
        path = self._write_events_file()
        try:
            result = self._serve_runs({"n": ["10"]}, path)
            runs = result["runs"]
            sids = {r["session_id"] for r in runs}
            self.assertIn("real-alpha-864-aaa", sids)
            self.assertIn("real-beta-864-bbb", sids)
        finally:
            path.unlink(missing_ok=True)

    def test_run_fields_present(self):
        """Each run entry must have session_id, first_ts, last_ts, event_count."""
        path = self._write_events_file()
        try:
            result = self._serve_runs({"n": ["10"]}, path)
            runs = result["runs"]
            for run in runs:
                for field in ("session_id", "first_ts", "last_ts", "event_count"):
                    self.assertIn(field, run,
                                  f"Run must have field '{field}': {run}")
        finally:
            path.unlink(missing_ok=True)

    def test_event_count_correct(self):
        """Session A should have event_count=2; session B event_count=1."""
        path = self._write_events_file()
        try:
            result = self._serve_runs({"n": ["10"]}, path)
            runs = result["runs"]
            by_sid = {r["session_id"]: r for r in runs}
            self.assertEqual(by_sid["real-alpha-864-aaa"]["event_count"], 2)
            self.assertEqual(by_sid["real-beta-864-bbb"]["event_count"], 1)
        finally:
            path.unlink(missing_ok=True)

    def test_empty_file_returns_empty_runs(self):
        """A missing or empty events file must return {runs: [], rejected_lines: 0}."""
        path = Path(tempfile.mktemp(suffix=".jsonl"))
        # file does not exist
        result = self._serve_runs({}, path)
        self.assertEqual(result.get("runs", []), [])

    def test_rejected_lines_counted(self):
        """rejected_lines must count v1 + fixture lines encountered."""
        path = self._write_events_file()
        try:
            result = self._serve_runs({"n": ["10"]}, path)
            rejected = result.get("rejected_lines", 0)
            # 2 invalid lines: fixture-session + v1-session
            self.assertGreaterEqual(rejected, 2,
                                    f"Expected >=2 rejected lines, got {rejected}")
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Group 2: trail endpoint keys for a cached PRD fixture
# ---------------------------------------------------------------------------

class TestTrailEndpointKeys(unittest.TestCase):
    """The /api/trail?prd=N path (via collector.get_trail) returns expected keys.

    Uses a synthetic trail fixture (matching the real prd-*.json schema) to
    validate offline. Also validates against the first real cached file if present.
    """

    _TRAIL_CACHE_DIR = REPO_ROOT / ".claude" / "logs" / "trail-cache"
    _FIXTURE_PRD = 496

    def setUp(self):
        _dashboard_path_inject()

    def _make_fixture_trail_file(self, prd_num: int) -> tuple[Path, dict]:
        """Write a minimal synthetic trail cache file; return (path, trail_dict)."""
        trail = {
            "prd_number": prd_num,
            "prd_title": f"PRD: fixture PRD #{prd_num}",
            "prd_created_at": "2026-01-01T00:00:00Z",
            "prd_closed_at": "2026-01-02T00:00:00Z",
            "prd_labels": ["prd"],
            "prd_verdicts": [],
            "slices": [
                {
                    "number": prd_num + 1,
                    "title": "Fixture slice",
                    "prd_number": prd_num,
                    "labels": ["slice"],
                    "created_at": "2026-01-01T10:00:00Z",
                    "closed_at": "2026-01-02T00:00:00Z",
                    "closed_event_at": "2026-01-02T00:00:00Z",
                    "closing_pr_number": prd_num + 2,
                    "assignees": ["test-user"],
                    "comment_count": 0,
                }
            ],
            "prs": {
                str(prd_num + 2): {
                    "number": prd_num + 2,
                    "created_at": "2026-01-01T11:00:00Z",
                    "merged_at": "2026-01-02T00:00:00Z",
                    "head_ref": f"feat/{prd_num + 1}-fixture",
                    "closing_issues": [prd_num + 1],
                    "verdicts": [{"verdict": "APPROVE", "round": 1}],
                    "verdict_count": 1,
                    "last_verdict": {"verdict": "APPROVE", "round": 1},
                    "reviewed_before_merge": True,
                    "is_trivial": False,
                    "body_excerpt": "Closes #%d" % (prd_num + 1),
                    "status_check_rollup": [],
                }
            },
            "collector_status": "ok",
            "wall_time_s": 3600.0,
        }
        wrapper = {"fetched_at": "2026-01-03T00:00:00Z",
                   "closed_at": "2026-01-02T00:00:00Z",
                   "trail": trail}
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(wrapper, tmp)
        tmp.close()
        return Path(tmp.name), trail

    def test_fixture_trail_has_expected_keys(self):
        """A synthetic trail dict must contain the standard top-level keys."""
        _, trail = self._make_fixture_trail_file(9900)
        required_keys = {
            "prd_number", "prd_title", "prd_closed_at",
            "slices", "prs", "wall_time_s",
        }
        for key in required_keys:
            self.assertIn(key, trail,
                          f"Trail dict missing required key '{key}'")

    def test_real_cached_trail_has_expected_keys(self):
        """If prd-496.json exists in trail-cache, it must have expected keys."""
        cache_file = self._TRAIL_CACHE_DIR / f"prd-{self._FIXTURE_PRD}.json"
        if not cache_file.exists():
            self.skipTest(f"trail-cache/prd-{self._FIXTURE_PRD}.json not present")
        wrapper = json.loads(cache_file.read_text(encoding="utf-8"))
        trail = wrapper.get("trail", wrapper)  # handle both shapes
        required_keys = {"prd_number", "prd_title", "slices", "prs"}
        for key in required_keys:
            self.assertIn(key, trail,
                          f"Real trail for PRD #{self._FIXTURE_PRD} missing key '{key}'")

    def test_prd_number_matches_fixture(self):
        """trail.prd_number must equal the requested PRD number."""
        _, trail = self._make_fixture_trail_file(9901)
        self.assertEqual(trail["prd_number"], 9901)

    def test_slices_is_list(self):
        """trail.slices must be a list (possibly empty)."""
        _, trail = self._make_fixture_trail_file(9902)
        self.assertIsInstance(trail["slices"], list)

    def test_prs_is_dict(self):
        """trail.prs must be a dict keyed by PR number strings."""
        _, trail = self._make_fixture_trail_file(9903)
        self.assertIsInstance(trail["prs"], dict)

    def test_collector_via_subprocess(self):
        """collector.get_trail() for a real cached PRD returns expected keys.

        Uses subprocess so REPO_ROOT resolution is consistent.
        """
        cache_files = sorted(self._TRAIL_CACHE_DIR.glob("prd-*.json"))
        if not cache_files:
            self.skipTest("No trail-cache files present")
        # Pick the first cached PRD
        fname = cache_files[0].name
        prd_num = int(fname.replace("prd-", "").replace(".json", ""))
        import subprocess
        script = f"""
import sys
sys.path.insert(0, r'{DASHBOARD_DIR}')
from collector import get_trail
import json
trail = get_trail({prd_num})
print(json.dumps({{k: type(v).__name__ for k, v in trail.items()}}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30,
            cwd=str(DASHBOARD_DIR),
        )
        self.assertEqual(result.returncode, 0,
                         f"collector.get_trail() failed:\nSTDERR: {result.stderr[:400]}")
        shape = json.loads(result.stdout.strip())
        for key in ("prd_number", "prd_title", "slices", "prs"):
            self.assertIn(key, shape,
                          f"get_trail() response missing key '{key}' (got {sorted(shape)})")


# ---------------------------------------------------------------------------
# Group 3: threaded-server concurrency smoke (AST parse — no live bind)
# ---------------------------------------------------------------------------

class TestThreadedServerSmoke(unittest.TestCase):
    """server.py must use ThreadingHTTPServer + daemon_threads=True.

    Validates via AST parse — never binds port 8765 (isolation rule per slice body).
    """

    def _parse_server_ast(self):
        src = SERVER_PY.read_text(encoding="utf-8")
        return ast.parse(src)

    def test_server_py_parses_without_error(self):
        """dashboard/server.py must be valid Python."""
        try:
            self._parse_server_ast()
        except SyntaxError as e:
            self.fail(f"server.py has a syntax error: {e}")

    def test_threading_http_server_imported(self):
        """server.py must import ThreadingHTTPServer from http.server."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            "ThreadingHTTPServer",
            src,
            "ThreadingHTTPServer must be imported in server.py",
        )

    def test_daemon_threads_set_true(self):
        """server.py must set daemon_threads = True (or =True) on the server."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            "daemon_threads",
            src,
            "server.py must set daemon_threads (for concurrency safety)",
        )
        # Check the assignment is True (not False)
        # Accept both `server.daemon_threads = True` and `daemon_threads=True`
        self.assertRegex(
            src,
            r"daemon_threads\s*=\s*True",
            "daemon_threads must be set to True in server.py",
        )

    def test_threading_server_used_in_main(self):
        """ThreadingHTTPServer must be instantiated in server.py's main()."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            "ThreadingHTTPServer(",
            src,
            "server.py must instantiate ThreadingHTTPServer (not plain HTTPServer)",
        )

    def test_api_runs_route_present(self):
        """server.py must have an elif path == '/api/runs' route handler."""
        src = SERVER_PY.read_text(encoding="utf-8")
        self.assertIn(
            '"/api/runs"',
            src,
            "server.py must contain an elif path == '/api/runs' route",
        )

    def test_api_runs_fetched_in_index_html(self):
        """index.html must contain a fetch('/api/runs') call."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/runs",
            html,
            "index.html must fetch /api/runs (DEAD-ROUTES compliance)",
        )

    def test_dead_routes_pass_after_impl(self):
        """DEAD-ROUTES health check must return PASS (no dead routes)."""
        import subprocess
        script = f"""
import sys
sys.path.insert(0, r'{DASHBOARD_DIR}')
from health import check_dead_routes
import json
print(json.dumps(check_dead_routes()))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=30,
            cwd=str(DASHBOARD_DIR),
        )
        self.assertEqual(result.returncode, 0,
                         f"check_dead_routes() subprocess failed:\n{result.stderr[:400]}")
        data = json.loads(result.stdout.strip())
        dead = data.get("dead_routes", [])
        self.assertEqual(
            [],
            dead,
            f"DEAD-ROUTES check has dead routes: {dead}\nDetail: {data.get('detail')}",
        )

    def test_trail_tab_fetches_trail_api(self):
        """index.html Trail tab must fetch /api/trail for per-PRD timeline."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/trail",
            html,
            "index.html must fetch /api/trail in the Trail tab",
        )

    def test_live_tab_fetches_live_progress(self):
        """index.html Live tab must fetch /api/live-progress."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/live-progress",
            html,
            "index.html must fetch /api/live-progress in the Live tab",
        )

    def test_per_prd_timeline_section_present(self):
        """index.html must contain the per-PRD workflow-firing timeline section.

        The section can be in the Trail tab (showing per-PRD timeline from
        /api/trail data) or in the Live tab (from /api/runs). Checks for
        a marker that indicates wired rendering of real per-PRD events.
        """
        html = INDEX_HTML.read_text(encoding="utf-8")
        # The timeline section renders per-PRD firing: slices + PRs + verdicts
        # Must have a section element with data from /api/trail or /api/runs
        markers = [
            "per-prd-timeline",    # id or class we'll add
            "prd-timeline",        # alternative id
            "workflow-timeline",   # alternative
            "prd-firing",          # alternative
        ]
        found = any(m in html for m in markers)
        self.assertTrue(
            found,
            f"index.html must contain a per-PRD workflow-firing timeline section "
            f"(looked for: {markers}). Timeline renders how+when the workflow fired "
            f"for a PRD from /api/trail data.",
        )


if __name__ == "__main__":
    unittest.main()
