"""
tests/test_record_green_1032.py

Regression tests for slice #1032 — tools/record-green.sh
verify-then-record develop_green checkpoint.

Core safety property: record develop_green ONLY after verifying develop is
genuinely green (GitHub ci=success on develop HEAD AND pytest green).
NEVER write a false green.

Acceptance criteria:
  cr.1  both stubs green → event appended to temp log + exit 0
  cr.2  ci stub = failure → NO event + exit != 0
  cr.2b pytest stub = fail → NO event + exit != 0
  cr.3  run with cwd in a subdir/worktree → resolves git-common-dir-root log

Script is driven as a subprocess. gh + pytest layers are stubbed via env vars:
  RECORD_GREEN_GH_CMD    — command to call instead of 'gh'; stub echoes "success"
  RECORD_GREEN_PYTEST_CMD — command to call instead of 'python -m pytest'; stub exits 0

Tests at commit #1: tools/record-green.sh does NOT exist yet → all tests fail/error.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_record_green_1032.py -v
"""

import json
import os
import subprocess
import sys
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
    """Run record-green.sh as a subprocess with stubbed gh + pytest commands.

    Stubs are tiny shell scripts written into a temp dir that is prepended to
    PATH so they shadow the real binaries.

    Args:
        extra_env: additional env vars merged on top of the defaults.
        args: extra CLI args for record-green.sh (e.g. ['--dry-run']).
        tmp_log: if provided, use this path as RECORD_GREEN_TEST_LOG_PATH
                 to redirect where the script writes its event (for isolation).
        cwd: working directory for the subprocess (defaults to REPO_ROOT).
    """
    if not RECORD_GREEN_SH.exists():
        raise FileNotFoundError(
            f"tools/record-green.sh not found at {RECORD_GREEN_SH}; "
            "the script must be created by the impl commit"
        )

    env = os.environ.copy()

    # Inject test-log path so the test can inspect it without touching the
    # real canonical log.
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


def _assert_event_appended(log_path: Path, expected_sha: str | None = None) -> dict:
    """Assert exactly one develop_green event was appended; return it."""
    lines = [l.strip() for l in log_path.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    develop_green_lines = [
        l for l in lines
        if '"event"' in l and '"develop_green"' in l
    ]
    assert len(develop_green_lines) >= 1, (
        f"Expected at least one develop_green event in log; got {len(develop_green_lines)}. "
        f"Full log:\n{log_path.read_text()}"
    )
    evt = json.loads(develop_green_lines[-1])
    assert evt.get("event") == "develop_green", f"event field wrong: {evt}"
    assert evt.get("v") == 2, f"v field should be 2: {evt}"
    assert "ts" in evt, f"ts field missing: {evt}"
    assert "sha" in evt, f"sha field missing: {evt}"
    if expected_sha:
        assert evt["sha"] == expected_sha, (
            f"sha mismatch: expected {expected_sha!r}, got {evt['sha']!r}"
        )
    return evt


# ---------------------------------------------------------------------------
# cr.1 — both stubs green → event appended + exit 0
# ---------------------------------------------------------------------------

class TestBothGreen(unittest.TestCase):
    """cr.1: when both gh ci=success and pytest pass, event is appended."""

    def test_both_green_exits_0(self):
        """With both stubs green, script must exit 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Expected exit 0 when both green; got {result.returncode}. "
                f"stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            )

    def test_both_green_appends_event(self):
        """With both stubs green, script must append a develop_green event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
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

    def test_both_green_event_has_sha(self):
        """develop_green event must contain a sha field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(result.returncode, 0,
                             f"exit {result.returncode}: {result.stderr!r}")
            evt = _assert_event_appended(tmp_log)
            self.assertIn("sha", evt, "event must contain sha field")
            self.assertGreater(len(evt["sha"]), 0, "sha must be non-empty")

    def test_both_green_event_src_is_orchestrator(self):
        """develop_green event src must be 'orchestrator'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(result.returncode, 0,
                             f"exit {result.returncode}: {result.stderr!r}")
            evt = _assert_event_appended(tmp_log)
            self.assertEqual(
                evt.get("src"), "orchestrator",
                f"src must be 'orchestrator'; got {evt.get('src')!r}",
            )


# ---------------------------------------------------------------------------
# cr.2 — ci stub = failure → NO event + exit != 0
# ---------------------------------------------------------------------------

class TestCIFail(unittest.TestCase):
    """cr.2: when gh ci stub reports failure, no event is written and exit != 0."""

    def test_ci_fail_exits_nonzero(self):
        """Script must exit non-zero when gh reports ci failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo failure",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"Expected non-zero exit when CI stub=failure; got 0. "
                f"stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            )

    def test_ci_fail_no_event_written(self):
        """No develop_green event must be written when CI fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo failure",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            if tmp_log.exists():
                content = tmp_log.read_text(encoding="utf-8")
                develop_green_lines = [
                    l for l in content.splitlines()
                    if '"develop_green"' in l
                ]
                self.assertEqual(
                    len(develop_green_lines), 0,
                    f"No develop_green event must be written on CI failure; "
                    f"found {len(develop_green_lines)} line(s): {develop_green_lines}",
                )

    def test_ci_fail_prints_reason_to_stderr(self):
        """Script must print a reason to stderr/stdout when CI fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo failure",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            combined = result.stdout + result.stderr
            self.assertGreater(
                len(combined.strip()), 0,
                "Script must print a reason when CI fails; got no output",
            )


# ---------------------------------------------------------------------------
# cr.2b — pytest stub = fail → NO event + exit != 0
# ---------------------------------------------------------------------------

class TestPytestFail(unittest.TestCase):
    """cr.2b: when pytest stub fails, no event is written and exit != 0."""

    def test_pytest_fail_exits_nonzero(self):
        """Script must exit non-zero when pytest stub fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"Expected non-zero exit when pytest stub=fail; got 0. "
                f"stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            )

    def test_pytest_fail_no_event_written(self):
        """No develop_green event must be written when pytest fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "false",
                },
                tmp_log=tmp_log,
            )
            if tmp_log.exists():
                content = tmp_log.read_text(encoding="utf-8")
                develop_green_lines = [
                    l for l in content.splitlines()
                    if '"develop_green"' in l
                ]
                self.assertEqual(
                    len(develop_green_lines), 0,
                    f"No develop_green event must be written on pytest failure; "
                    f"found {len(develop_green_lines)} line(s): {develop_green_lines}",
                )


# ---------------------------------------------------------------------------
# cr.3 — git-common-dir-root log resolution when run from a subdir/worktree
# ---------------------------------------------------------------------------

class TestGitCommonDirResolution(unittest.TestCase):
    """cr.3: writes to git-common-dir-root log when run from a subdir.

    RECORD_GREEN_TEST_LOG_PATH overrides the canonical log path, so we can
    verify the event was written to the tmp log regardless of cwd.
    """

    def test_resolves_from_subdir(self):
        """Script run from a subdir must still resolve and write the event."""
        # Run from the 'tools' subdirectory to simulate subdir/worktree invocation.
        subdir = str(REPO_ROOT / "tools")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
                cwd=subdir,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Script must exit 0 when run from subdir; got {result.returncode}. "
                f"stderr: {result.stderr!r}",
            )
            self.assertTrue(
                tmp_log.exists(),
                f"Event log must be created when run from subdir; path: {tmp_log}",
            )
            evt = _assert_event_appended(tmp_log)
            self.assertEqual(evt["event"], "develop_green")

    def test_log_dir_created_if_absent(self):
        """Script must mkdir -p the log dir if it does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Point to a nested path that doesn't exist yet.
            tmp_log = Path(tmpdir) / "nested" / "subdir" / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
            )
            self.assertEqual(
                result.returncode, 0,
                f"Script must create nested log dirs; got {result.returncode}. "
                f"stderr: {result.stderr!r}",
            )
            self.assertTrue(
                tmp_log.exists(),
                f"Log must exist at nested path {tmp_log}",
            )


# ---------------------------------------------------------------------------
# dry-run flag — prints but does not write
# ---------------------------------------------------------------------------

class TestDryRun(unittest.TestCase):
    """--dry-run: verifications run + event is printed but NOT appended."""

    def test_dry_run_prints_event_on_green(self):
        """--dry-run must print the would-be event to stdout when green."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
                args=["--dry-run"],
            )
            self.assertEqual(
                result.returncode, 0,
                f"--dry-run must exit 0 when green; got {result.returncode}. "
                f"stderr: {result.stderr!r}",
            )
            combined = result.stdout + result.stderr
            self.assertIn(
                "develop_green",
                combined,
                f"--dry-run must print 'develop_green' in output; got: {combined!r}",
            )

    def test_dry_run_does_not_write_event(self):
        """--dry-run must NOT write to the log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo success",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
                args=["--dry-run"],
            )
            self.assertEqual(result.returncode, 0,
                             f"exit {result.returncode}: {result.stderr!r}")
            # Log must NOT have been created or remain empty of develop_green events.
            if tmp_log.exists():
                content = tmp_log.read_text(encoding="utf-8")
                develop_green_lines = [
                    l for l in content.splitlines()
                    if '"develop_green"' in l
                ]
                self.assertEqual(
                    len(develop_green_lines), 0,
                    f"--dry-run must not write develop_green to log; "
                    f"found {len(develop_green_lines)} line(s)",
                )

    def test_dry_run_exits_nonzero_when_ci_fails(self):
        """--dry-run must exit non-zero when CI stub fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = Path(tmpdir) / "workflow-events.jsonl"
            result = _run_script(
                extra_env={
                    "RECORD_GREEN_GH_CMD": "echo failure",
                    "RECORD_GREEN_PYTEST_CMD": "true",
                },
                tmp_log=tmp_log,
                args=["--dry-run"],
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"--dry-run must exit non-zero when CI fails; got 0. "
                f"stdout: {result.stdout!r}",
            )


# ---------------------------------------------------------------------------
# Script existence check — this FAILS at commit #1 (test-first discipline)
# ---------------------------------------------------------------------------

class TestScriptExists(unittest.TestCase):
    """Sanity: tools/record-green.sh must exist. Fails at commit #1 intentionally."""

    def test_script_file_exists(self):
        """tools/record-green.sh must exist on the filesystem."""
        self.assertTrue(
            RECORD_GREEN_SH.exists(),
            f"tools/record-green.sh must exist at {RECORD_GREEN_SH}; "
            "create it in the impl commit (commit #2)",
        )

    def test_script_is_executable_bash(self):
        """tools/record-green.sh must be a bash script (shebang check)."""
        if not RECORD_GREEN_SH.exists():
            self.skipTest("script not yet created (impl commit pending)")
        content = RECORD_GREEN_SH.read_text(encoding="utf-8")
        self.assertTrue(
            content.startswith("#!/bin/bash") or content.startswith("#!/usr/bin/env bash"),
            f"script must start with bash shebang; got: {content[:40]!r}",
        )


if __name__ == "__main__":
    unittest.main()
