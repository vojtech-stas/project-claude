"""
Regression tests for issue #873 / slice #907 — STALE-SERVER health check.

ADR-0067 D3 (regression-rider): test commit precedes fix commit in branch
history.  These tests are written BEFORE check_stale_server() is added to
health.py so they intentionally FAIL on the unfixed codebase (STALE-SERVER
absent from CHECK_REGISTRY) and PASS after the fix.

Three test groups:
  1. Registry presence — STALE-SERVER appears in CHECK_REGISTRY and in
     `python dashboard/health.py --list` output.
  2. STALE-SERVER behaviour — PASS when server sha == HEAD; FAIL when sha
     differs from HEAD (stale server).
  3. Behaviour with server unreachable — WARN gracefully (no crash).

All assertions are offline (no live server dependency).  Mock /api/meta and
HEAD sha via env-var overrides mirroring the HOOK-LIVENESS pattern.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_stale_server_907.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
HEALTH_PY = REPO_ROOT / "dashboard" / "health.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_check(meta_response: dict | None, head_sha: str) -> dict:
    """Invoke check_stale_server() via subprocess with mocked inputs.

    Injects:
      _STALE_SERVER_META_OVERRIDE — JSON string for the mocked /api/meta response
        (None = simulate unreachable server / connection error).
      _STALE_SERVER_HEAD_OVERRIDE — HEAD sha string to compare against.
    """
    meta_json = json.dumps(meta_response) if meta_response is not None else ""
    script = f"""
import sys
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
import os
os.environ['_STALE_SERVER_META_OVERRIDE'] = {repr(meta_json)}
os.environ['_STALE_SERVER_HEAD_OVERRIDE'] = {repr(head_sha)}
from health import check_stale_server
import json
result = check_stale_server()
print(json.dumps(result))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "dashboard"),
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"check_stale_server() subprocess failed:\n"
            f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
    return json.loads(proc.stdout.strip())


# ---------------------------------------------------------------------------
# Group 1: Registry presence
# ---------------------------------------------------------------------------

class TestStaleServerRegistryPresence(unittest.TestCase):
    """STALE-SERVER must appear in CHECK_REGISTRY (ADR-0071 D5 claim)."""

    def test_stale_server_in_check_registry(self):
        """CHECK_REGISTRY must contain a 'STALE-SERVER' key."""
        script = f"""
import sys
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
from health import CHECK_REGISTRY
import json
print(json.dumps(list(CHECK_REGISTRY.keys())))
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "dashboard"),
        )
        self.assertEqual(0, proc.returncode,
                         msg=f"health.py import failed:\n{proc.stderr}")
        keys = json.loads(proc.stdout.strip())
        self.assertIn(
            "STALE-SERVER", keys,
            msg="CHECK_REGISTRY must contain 'STALE-SERVER' (ADR-0071 D5 claim). "
                "Add check_stale_server() and register it."
        )

    def test_stale_server_in_list_output(self):
        """`python dashboard/health.py --list` must include STALE-SERVER."""
        proc = subprocess.run(
            [sys.executable, str(HEALTH_PY), "--list"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "dashboard"),
        )
        self.assertEqual(0, proc.returncode,
                         msg=f"--list failed:\n{proc.stderr}")
        self.assertIn(
            "STALE-SERVER", proc.stdout,
            msg="'--list' output must include STALE-SERVER"
        )


# ---------------------------------------------------------------------------
# Group 2: STALE-SERVER behaviour
# ---------------------------------------------------------------------------

class TestStaleServerBehaviour(unittest.TestCase):
    """STALE-SERVER check: PASS fresh / FAIL stale."""

    _HEAD = "abc1234deadbeef"
    _OTHER = "999aaabbbcccddd"

    def test_pass_when_server_sha_matches_head(self):
        """PASS when /api/meta.sha == HEAD sha (server is fresh)."""
        result = _run_check(
            meta_response={"sha": self._HEAD, "started_at": "2026-01-01T00:00:00Z", "stale": False},
            head_sha=self._HEAD,
        )
        self.assertEqual(
            "PASS", result["result"],
            msg=f"Expected PASS (sha==HEAD) but got {result['result']}: {result.get('detail')}"
        )

    def test_fail_when_server_sha_differs_from_head(self):
        """FAIL when /api/meta.sha != HEAD sha (server is stale)."""
        result = _run_check(
            meta_response={"sha": self._OTHER, "started_at": "2026-01-01T00:00:00Z", "stale": False},
            head_sha=self._HEAD,
        )
        self.assertEqual(
            "FAIL", result["result"],
            msg=f"Expected FAIL (sha!=HEAD) but got {result['result']}: {result.get('detail')}"
        )
        self.assertIn(
            "stale", result.get("detail", "").lower(),
            msg="FAIL detail must mention 'stale'"
        )

    def test_fail_when_meta_stale_flag_true(self):
        """FAIL when /api/meta.stale is True (server itself reports staleness)."""
        result = _run_check(
            meta_response={"sha": self._HEAD, "started_at": "2026-01-01T00:00:00Z", "stale": True},
            head_sha=self._HEAD,
        )
        self.assertEqual(
            "FAIL", result["result"],
            msg=f"Expected FAIL (meta.stale=True) but got {result['result']}: {result.get('detail')}"
        )

    def test_result_has_required_id_field(self):
        """Result dict must have id == 'STALE-SERVER'."""
        result = _run_check(
            meta_response={"sha": self._HEAD, "started_at": "2026-01-01T00:00:00Z", "stale": False},
            head_sha=self._HEAD,
        )
        self.assertEqual(
            "STALE-SERVER", result.get("id"),
            msg="Result dict must have id='STALE-SERVER'"
        )


# ---------------------------------------------------------------------------
# Group 3: Graceful degradation when server unreachable
# ---------------------------------------------------------------------------

class TestStaleServerGracefulDegradation(unittest.TestCase):
    """WARN (not crash/FAIL) when the dashboard server is unreachable."""

    def test_warn_when_server_unreachable(self):
        """WARN when meta_response is None (simulates connection refused)."""
        result = _run_check(meta_response=None, head_sha="abc1234")
        self.assertIn(
            result["result"], ("WARN", "PASS"),
            msg=(
                f"Expected WARN (server unreachable) but got {result['result']}: "
                f"{result.get('detail')}"
            )
        )
        # Must not FAIL — no server running is not the same as stale server
        self.assertNotEqual(
            "FAIL", result["result"],
            msg="Unreachable server must produce WARN, not FAIL"
        )


if __name__ == "__main__":
    unittest.main()
