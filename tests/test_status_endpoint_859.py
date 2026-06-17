"""
Tests for slice #859 — /api/status aggregation endpoint + DEAD-ROUTES fix.

Two test groups (ADR-0067 D2 test-first ordering — this file committed before impl):

  1. api_status_keys: assert the handler returns a dict with all expected top-level
     keys and correct value types (offline; no server needed).

  2. dead_routes_improves: assert DEAD-ROUTES count drops to 0 after the impl
     (wires /api/workitems and /api/runs out of the dead set).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_status_endpoint_859.py -v
"""

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SERVER_PY = REPO_ROOT / "dashboard" / "server.py"
INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"
HEALTH_PY = REPO_ROOT / "dashboard" / "health.py"


# ---------------------------------------------------------------------------
# Helper: run a snippet in a subprocess that can import from dashboard/
# ---------------------------------------------------------------------------

def _run_dashboard_script(script: str) -> tuple[int, str, str]:
    """Run a Python snippet with dashboard/ on sys.path; return (rc, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "dashboard"),
        timeout=30,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ---------------------------------------------------------------------------
# Group 1: /api/status handler shape
# ---------------------------------------------------------------------------

class TestApiStatusKeys(unittest.TestCase):
    """The serve_status() handler (or equivalent) must return a dict
    containing all required top-level keys with correctly-typed values.

    Tested offline by importing server.py and calling its status-building
    function directly (no HTTP server needed).
    """

    # Required keys and their expected Python types (None is allowed for
    # nullable fields — we test isinstance OR value is None).
    REQUIRED_KEYS = {
        "head_sha": str,
        "short_sha": str,
        "branch": str,
        "server_sha": str,
        "stale": bool,
        "hooks_live": dict,
        "last_event": dict,
        "main_green": dict,
        "health_summary": dict,
        "open_work": dict,
    }

    HOOKS_LIVE_KEYS = {"alive", "newest_beacon_ts", "age_minutes"}
    LAST_EVENT_KEYS = {"ts", "age_minutes"}
    MAIN_GREEN_KEYS = {"sha", "lag", "age_hours"}
    HEALTH_SUMMARY_KEYS = {"pass", "warn", "fail"}
    OPEN_WORK_KEYS = {"prs", "slices", "captured", "backlog"}

    def _call_build_status(self) -> dict:
        """Call _build_status() from server.py and return the result dict."""
        script = f"""
import sys
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
import server
import json
result = server._build_status()
print(json.dumps(result))
"""
        rc, stdout, stderr = _run_dashboard_script(script)
        if rc != 0:
            self.fail(
                f"_build_status() subprocess failed (rc={rc}):\n"
                f"STDOUT: {stdout[:500]}\nSTDERR: {stderr[:500]}"
            )
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as e:
            self.fail(f"_build_status() returned non-JSON output: {stdout[:200]}\nError: {e}")

    def test_all_top_level_keys_present(self):
        """All required top-level keys must be present in the response."""
        data = self._call_build_status()
        missing = [k for k in self.REQUIRED_KEYS if k not in data]
        self.assertEqual(
            [],
            missing,
            msg=f"Missing required top-level keys in /api/status: {missing}\nGot keys: {sorted(data.keys())}",
        )

    def test_scalar_types_correct(self):
        """Scalar fields must be string or bool (not None, not wrong type)."""
        data = self._call_build_status()
        # head_sha, short_sha, branch, server_sha may be empty string if git unavailable
        for key in ("head_sha", "short_sha", "branch", "server_sha"):
            self.assertIsInstance(
                data.get(key), str,
                msg=f"'{key}' must be a str (got {type(data.get(key)).__name__})",
            )
        self.assertIsInstance(
            data.get("stale"), bool,
            msg=f"'stale' must be a bool (got {type(data.get('stale')).__name__})",
        )

    def test_nested_dicts_have_required_keys(self):
        """Each nested dict must contain its required subkeys."""
        data = self._call_build_status()

        for subkey in self.HOOKS_LIVE_KEYS:
            self.assertIn(
                subkey, data["hooks_live"],
                msg=f"hooks_live missing key '{subkey}'",
            )
        for subkey in self.LAST_EVENT_KEYS:
            self.assertIn(
                subkey, data["last_event"],
                msg=f"last_event missing key '{subkey}'",
            )
        for subkey in self.MAIN_GREEN_KEYS:
            self.assertIn(
                subkey, data["main_green"],
                msg=f"main_green missing key '{subkey}'",
            )
        for subkey in self.HEALTH_SUMMARY_KEYS:
            self.assertIn(
                subkey, data["health_summary"],
                msg=f"health_summary missing key '{subkey}'",
            )
        for subkey in self.OPEN_WORK_KEYS:
            self.assertIn(
                subkey, data["open_work"],
                msg=f"open_work missing key '{subkey}'",
            )

    def test_health_summary_counts_are_non_negative_ints(self):
        """health_summary pass/warn/fail must be non-negative integers or None.

        None is the honest representation when health is still computing
        (per fix in slice #861 — silent 0/0/0 replaced with null sentinel).
        When non-null, each value must be a non-negative int.
        """
        data = self._call_build_status()
        summary = data.get("health_summary", {})
        for key in ("pass", "warn", "fail"):
            val = summary.get(key)
            # None is valid — means health is still computing (computing sentinel)
            if val is None:
                continue
            self.assertIsInstance(
                val, int,
                msg=f"health_summary.{key} must be int or null (got {type(val).__name__}={val})",
            )
            self.assertGreaterEqual(
                val, 0,
                msg=f"health_summary.{key} must be >= 0 (got {val})",
            )

    def test_open_work_counts_are_non_negative_ints(self):
        """open_work prs/slices/captured/backlog must be non-negative integers."""
        data = self._call_build_status()
        work = data.get("open_work", {})
        for key in ("prs", "slices", "captured", "backlog"):
            val = work.get(key)
            self.assertIsInstance(
                val, int,
                msg=f"open_work.{key} must be int (got {type(val).__name__}={val})",
            )
            self.assertGreaterEqual(
                val, 0,
                msg=f"open_work.{key} must be >= 0 (got {val})",
            )

    def test_hooks_live_alive_is_bool(self):
        """hooks_live.alive must be a bool."""
        data = self._call_build_status()
        alive = data.get("hooks_live", {}).get("alive")
        self.assertIsInstance(
            alive, bool,
            msg=f"hooks_live.alive must be bool (got {type(alive).__name__}={alive})",
        )


# ---------------------------------------------------------------------------
# Group 2: DEAD-ROUTES improves after impl
# ---------------------------------------------------------------------------

class TestDeadRoutesImproves(unittest.TestCase):
    """After the impl, DEAD-ROUTES count must be 0 (all served routes fetched)."""

    def _get_dead_routes_result(self) -> dict:
        """Call check_dead_routes() via subprocess."""
        script = f"""
import sys
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
from health import check_dead_routes
import json
print(json.dumps(check_dead_routes()))
"""
        rc, stdout, stderr = _run_dashboard_script(script)
        if rc != 0:
            self.fail(
                f"check_dead_routes() subprocess failed:\n"
                f"STDOUT: {stdout[:300]}\nSTDERR: {stderr[:300]}"
            )
        return json.loads(stdout)

    def test_dead_routes_count_is_zero(self):
        """After impl, no /api/* routes served but not fetched by index.html."""
        result = self._get_dead_routes_result()
        dead = result.get("dead_routes", [])
        self.assertEqual(
            [],
            dead,
            msg=(
                f"DEAD-ROUTES check still has dead routes after impl: {dead}\n"
                f"Detail: {result.get('detail')}"
            ),
        )

    def test_status_endpoint_fetched_in_index(self):
        """/api/status must appear in at least one fetch() call in index.html."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn(
            "/api/status",
            html,
            msg="/api/status not found in any fetch() call in dashboard/index.html",
        )

    def test_server_py_parses(self):
        """dashboard/server.py must be valid Python (ast.parse succeeds)."""
        import ast
        src = SERVER_PY.read_text(encoding="utf-8")
        try:
            ast.parse(src)
        except SyntaxError as e:
            self.fail(f"dashboard/server.py has a syntax error: {e}")


if __name__ == "__main__":
    unittest.main()
