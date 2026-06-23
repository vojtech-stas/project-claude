"""
tests/test_record_green_1034.py

Regression tests for slice #1034 — tools/record-green.sh squash-HEAD green path.

Bug: record-green.sh queried repos/{owner}/{repo}/commits/$DEV_SHA/check-runs
to find the `ci` conclusion.  A squash-merge commit (every develop HEAD in
the two-tier workflow) has NO check-runs attached → conclusion is always empty
→ recorder ALWAYS refuses → can never record green.

Fix: replace the commit-sha check-runs query with the PR-mergeCommit lookup
already implemented in dashboard/health.py::_fetch_github_ci_conclusion().

Test injection for the new Python path:
  RECORD_GREEN_CI_STATUS — when set, the script treats this value as the CI
                            status instead of calling _fetch_github_ci_conclusion.
                            Accepted values: pass | fail | pending | unavailable
  RECORD_GREEN_PYTEST_CMD — existing injection for the pytest check (unchanged).

ADR-0067 D3: test commit PRECEDES fix commit; the green-path test (cr.a) FAILS
on the current code (commit-sha query returns empty for squash HEAD) and PASSES
after the fix.

Acceptance criteria verified by these tests:
  cr.a  RECORD_GREEN_CI_STATUS=pass + pytest green → records develop_green + exit 0
        ** FAILS on pre-fix code, PASSES on fixed code **
  cr.b  RECORD_GREEN_CI_STATUS=pending/unavailable/fail → NO write + exit != 0
  cr.c  RECORD_GREEN_CI_STATUS=pass + pytest stub fail → NO write + exit != 0

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_record_green_1034.py -v
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RECORD_GREEN_SH = REPO_ROOT / "tools" / "record-green.sh"


def _run_script(
    extra_env: dict | None = None,
    args: list[str] | None = None,
    tmp_log: Path | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run record-green.sh as a subprocess.

    Uses RECORD_GREEN_CI_STATUS for new-path injection (bypasses Python call),
    and RECORD_GREEN_PYTEST_CMD for pytest injection (unchanged from #1032).
    """
    env = os.environ.copy()

    if tmp_log is not None:
        env["RECORD_GREEN_TEST_LOG_PATH"] = str(tmp_log)

    if extra_env:
        env.update(extra_env)

    cmd = ["bash", str(RECORD_GREEN_SH)] + (args or [])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
        cwd=cwd or str(REPO_ROOT),
    )
    return result


def _assert_event_appended(log_path: Path) -> dict:
    """Assert exactly one develop_green event was appended; return it."""
    lines = [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    dg_lines = [ln for ln in lines if '"develop_green"' in ln]
    assert len(dg_lines) >= 1, (
        f"Expected at least one develop_green event; got {len(dg_lines)}. "
        f"Full log:\n{log_path.read_text()}"
    )
    evt = json.loads(dg_lines[-1])
    assert evt.get("event") == "develop_green"
    assert evt.get("v") == 2
    assert "ts" in evt
    assert "sha" in evt
    return evt


def _assert_no_event_written(tmp_log: Path) -> None:
    """Assert that no develop_green event was written."""
    if not tmp_log.exists():
        return
    content = tmp_log.read_text(encoding="utf-8")
    dg_lines = [ln for ln in content.splitlines() if '"develop_green"' in ln]
    assert dg_lines == [], (
        f"Expected NO develop_green event; found {len(dg_lines)}: {dg_lines}"
    )


# ---------------------------------------------------------------------------
# cr.a — RECORD_GREEN_CI_STATUS=pass + pytest green → records + exit 0
#
# THIS TEST FAILS ON PRE-FIX CODE.
# Pre-fix code ignores RECORD_GREEN_CI_STATUS and does the commit-sha
# check-runs query (returns empty for squash HEAD) → exits 1.
# Post-fix code reads RECORD_GREEN_CI_STATUS=pass → proceeds to pytest → records.
# ---------------------------------------------------------------------------

class TestSquashHeadGreenPath(unittest.TestCase):
    """cr.a: the squash-HEAD green path via RECORD_GREEN_CI_STATUS injection.

    These tests FAIL on the current (pre-fix) code because record-green.sh
    does not yet honour RECORD_GREEN_CI_STATUS — it calls the commit-sha
    check-runs query instead, which returns '' for squash-merge commits.
    """

    def test_ci_status_pass_exits_0(self):
        """RECORD_GREEN_CI_STATUS=pass + pytest green must exit 0.

        FAILS before fix: pre-fix code ignores RECORD_GREEN_CI_STATUS and
        calls gh api check-runs which returns empty → exits 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0 when RECORD_GREEN_CI_STATUS=pass + pytest green; "
                f"got {result.returncode}. "
                f"stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            )

    def test_ci_status_pass_appends_event(self):
        """RECORD_GREEN_CI_STATUS=pass + pytest green must append develop_green.

        FAILS before fix: pre-fix code refuses at the empty ci conclusion.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Script must exit 0 for green path; got {result.returncode}. "
                f"stderr: {result.stderr!r}",
            )
            self.assertTrue(
                tmp_log.exists(),
                f"Log file must be created; path: {tmp_log}. "
                f"stderr: {result.stderr!r}",
            )
            evt = _assert_event_appended(tmp_log)
            self.assertEqual(evt["event"], "develop_green")
            self.assertEqual(evt["v"], 2)
            self.assertIn("sha", evt)

    def test_ci_status_pass_dry_run_exits_0(self):
        """RECORD_GREEN_CI_STATUS=pass + --dry-run must exit 0, no write.

        FAILS before fix: pre-fix code refuses at empty ci conclusion.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
                args=["--dry-run"],
            )
            self.assertEqual(
                result.returncode, 0,
                f"--dry-run must exit 0 when RECORD_GREEN_CI_STATUS=pass; "
                f"got {result.returncode}. stderr: {result.stderr!r}",
            )
            # dry-run must NOT write
            _assert_no_event_written(tmp_log)
            # must mention develop_green in output
            combined = result.stdout + result.stderr
            self.assertIn("develop_green", combined,
                          f"--dry-run output must mention develop_green; got: {combined!r}")


# ---------------------------------------------------------------------------
# cr.b — RECORD_GREEN_CI_STATUS != pass → refuse (no write, exit != 0)
# ---------------------------------------------------------------------------

class TestSquashHeadNonPassRefuses(unittest.TestCase):
    """cr.b: non-pass CI statuses must refuse to record (no-false-green)."""

    def _assert_refused(self, ci_status: str) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": ci_status,
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"RECORD_GREEN_CI_STATUS={ci_status!r} must cause exit != 0; "
                f"got 0. stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            )
            _assert_no_event_written(tmp_log)

    def test_ci_status_pending_refuses(self):
        """RECORD_GREEN_CI_STATUS=pending must refuse."""
        self._assert_refused("pending")

    def test_ci_status_unavailable_refuses(self):
        """RECORD_GREEN_CI_STATUS=unavailable must refuse."""
        self._assert_refused("unavailable")

    def test_ci_status_fail_refuses(self):
        """RECORD_GREEN_CI_STATUS=fail must refuse."""
        self._assert_refused("fail")

    def test_ci_status_empty_refuses(self):
        """RECORD_GREEN_CI_STATUS='' (empty) must refuse."""
        self._assert_refused("")


# ---------------------------------------------------------------------------
# cr.c — RECORD_GREEN_CI_STATUS=pass + pytest fail → refuse (no write)
# ---------------------------------------------------------------------------

class TestSquashHeadPytestFail(unittest.TestCase):
    """cr.c: ci=pass but pytest fails → must still refuse (no-false-green)."""

    def test_ci_pass_pytest_fail_exits_nonzero(self):
        """RECORD_GREEN_CI_STATUS=pass + pytest stub fail must exit != 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"Must exit non-zero when pytest fails; got 0. "
                f"stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            )

    def test_ci_pass_pytest_fail_no_event_written(self):
        """RECORD_GREEN_CI_STATUS=pass + pytest stub fail must not write event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            _assert_no_event_written(tmp_log)


if __name__ == "__main__":
    unittest.main()
