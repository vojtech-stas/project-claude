"""
tests/test_record_green_ci_trust_1161.py

Regression tests for issue #1161 — tools/record-green.sh must TRUST a
recorded GitHub `ci` conclusion for the EXACT develop-HEAD sha instead of
unconditionally re-running the full pytest suite locally (kills the #1122
budget-bump class at the root; ~25-35 min/slice measured duplication).

Per ADR-0067 D2/D3: this test commit PRECEDES the fix commit. These tests
are WRITTEN TO FAIL on pre-fix tools/record-green.sh (which always runs the
pytest sub-call regardless of the CI status) and PASS after the fix.

Fix shape (tools/record-green.sh only):
  RECORD_GREEN_CI_STATUS (or the real _fetch_github_ci_conclusion path)
    == "pass"        -> SKIP the local pytest sub-call entirely; record
                        green trusting the recorded ci run alone.
    == "unavailable" -> no recorded ci run for this sha (fresh clone /
                        un-pushed sha) -> local pytest fallback STILL runs
                        (fresh-clone honesty preserved).
    == "fail" | "pending" | "" -> refuse immediately (unchanged; a pytest
                        fallback never rescues an explicit fail/incomplete
                        recorded run).

Spy technique (per the #1119 lesson: NO PATH stubs — reuse the existing
RECORD_GREEN_PYTEST_CMD env seam only): RECORD_GREEN_PYTEST_CMD is set to a
shell command that both touches a marker file AND exits 0/1, so we can
distinguish "invoked and passed" from "never invoked at all" (both of which
look identical from the exit code alone).

Acceptance criteria verified by these tests:
  (a) ci=pass for the exact sha -> record-green does NOT invoke pytest
      (spy marker absent) and STILL records the green event
      ** FAILS on pre-fix code (spy marker WOULD be created) **
  (b) NO recorded ci run for the sha (unavailable) -> the local pytest
      fallback DOES run (spy marker present)
  (c) ci=fail -> no green is recorded (unchanged; spy marker absent too —
      pytest was never invoked pre- or post-fix on an explicit fail)
  stdout must name the recorded-ci evidence source (not just a bare exit
  code) so an operator can see WHICH evidence proved the suite green.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_record_green_ci_trust_1161.py -v
"""

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
) -> subprocess.CompletedProcess:
    """Run record-green.sh as a subprocess with the documented env seams."""
    env = os.environ.copy()
    if tmp_log is not None:
        env["RECORD_GREEN_TEST_LOG_PATH"] = str(tmp_log)
    if extra_env:
        env.update(extra_env)
    cmd = ["bash", str(RECORD_GREEN_SH)] + (args or [])
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, env=env, cwd=str(REPO_ROOT),
    )


def _assert_event_appended(log_path: Path) -> None:
    assert log_path.exists(), f"Log file must exist at {log_path}"
    content = log_path.read_text(encoding="utf-8")
    dg_lines = [ln for ln in content.splitlines() if '"develop_green"' in ln]
    assert len(dg_lines) >= 1, f"Expected a develop_green event; got none. Log:\n{content}"


def _assert_no_event_written(log_path: Path) -> None:
    if not log_path.exists():
        return
    content = log_path.read_text(encoding="utf-8")
    dg_lines = [ln for ln in content.splitlines() if '"develop_green"' in ln]
    assert dg_lines == [], f"Expected NO develop_green event; found: {dg_lines}"


# ---------------------------------------------------------------------------
# (a) ci=pass -> pytest sub-call is SKIPPED, green is still recorded
# ---------------------------------------------------------------------------

class TestCiPassSkipsLocalPytest(unittest.TestCase):
    """(a): RECORD_GREEN_CI_STATUS=pass must record green WITHOUT invoking
    the local pytest sub-call at all. FAILS on pre-fix code (which always
    invokes RECORD_GREEN_PYTEST_CMD regardless of CI status)."""

    def test_marker_not_created_when_ci_pass(self):
        """A pytest-stub marker file must NOT be created on the ci=pass path
        -- proof the sub-call never fired (not just that it happened to
        pass)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            marker = Path(tmpdir) / "pytest_invoked.marker"
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": f"echo ran > '{marker}'",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0 when ci=pass; got {result.returncode}. "
                f"stdout: {result.stdout!r} stderr: {result.stderr!r}",
            )
            self.assertFalse(
                marker.exists(),
                f"RECORD_GREEN_PYTEST_CMD must NOT be invoked when "
                f"RECORD_GREEN_CI_STATUS=pass (#1161 ci-trust fast path); "
                f"marker file was created at {marker}, proving it ran. "
                f"stdout: {result.stdout!r}",
            )
            _assert_event_appended(tmp_log)

    def test_records_green_even_if_pytest_cmd_would_fail(self):
        """RECORD_GREEN_PYTEST_CMD='false' (would refuse if ever run) must
        have ZERO effect on the ci=pass path -- proves the sub-call is
        skipped, not merely coincidentally green. Supersedes the pre-#1161
        cr.c contract in tests/test_record_green_1034.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"ci=pass must record green regardless of what "
                f"RECORD_GREEN_PYTEST_CMD would have done (it must never be "
                f"invoked); got exit {result.returncode}. "
                f"stdout: {result.stdout!r} stderr: {result.stderr!r}",
            )
            _assert_event_appended(tmp_log)

    def test_stdout_names_recorded_ci_evidence(self):
        """stdout must state the suite was proven by the recorded CI run,
        not a local run -- an operator-legible evidence trail (#1161)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "pass",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            combined = result.stdout + result.stderr
            self.assertIn(
                "no local pytest re-run", combined,
                f"stdout must explicitly name the ci-trust evidence source; "
                f"got: {combined!r}",
            )
            self.assertIn("#1161", combined, f"got: {combined!r}")


# ---------------------------------------------------------------------------
# (b) no recorded ci run for the sha -> local pytest fallback DOES run
# ---------------------------------------------------------------------------

class TestNoRecordedRunFallsBackToLocalPytest(unittest.TestCase):
    """(b): RECORD_GREEN_CI_STATUS=unavailable (no recorded ci run for this
    sha) must still invoke the local pytest fallback -- fresh-clone honesty
    preserved."""

    def test_marker_created_when_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            marker = Path(tmpdir) / "pytest_invoked.marker"
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "unavailable",
                    "RECORD_GREEN_PYTEST_CMD": f"echo ran > '{marker}'",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0 when unavailable + pytest stub green; "
                f"got {result.returncode}. stdout: {result.stdout!r} "
                f"stderr: {result.stderr!r}",
            )
            self.assertTrue(
                marker.exists(),
                f"RECORD_GREEN_PYTEST_CMD MUST be invoked as the local "
                f"fallback when no recorded ci run exists for this sha "
                f"(RECORD_GREEN_CI_STATUS=unavailable); marker not found. "
                f"stdout: {result.stdout!r}",
            )
            _assert_event_appended(tmp_log)

    def test_unavailable_plus_pytest_fail_refuses(self):
        """Fallback pytest failing must still refuse (no-false-green)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "unavailable",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"Expected non-zero exit when local pytest fallback fails; "
                f"got 0. stdout: {result.stdout!r}",
            )
            _assert_no_event_written(tmp_log)


# ---------------------------------------------------------------------------
# (c) ci=fail -> no green is recorded; pytest never invoked either way
# ---------------------------------------------------------------------------

class TestCiFailNeverRescuedByPytest(unittest.TestCase):
    """(c): RECORD_GREEN_CI_STATUS=fail must refuse immediately; the pytest
    sub-call must never fire (true both pre- and post-#1161, asserted here
    for full #1161 traceability)."""

    def test_marker_not_created_and_refuses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            marker = Path(tmpdir) / "pytest_invoked.marker"
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_CI_STATUS": "fail",
                    "RECORD_GREEN_PYTEST_CMD": f"echo ran > '{marker}'",
                },
                tmp_log=tmp_log,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"Expected non-zero exit when ci=fail; got 0. "
                f"stdout: {result.stdout!r}",
            )
            self.assertFalse(
                marker.exists(),
                "pytest sub-call must never fire when ci=fail (no rescue)",
            )
            _assert_no_event_written(tmp_log)


if __name__ == "__main__":
    unittest.main()
