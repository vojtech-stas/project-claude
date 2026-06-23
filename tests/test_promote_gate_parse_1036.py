"""
tests/test_promote_gate_parse_1036.py

Regression tests for slice #1036 — promote.sh gate-parse reads real PASS line
from health.py CLI, not a JSON verdict field.

Bug: promote.sh parsed JSON `verdict` field from health.py output, but
health.py --check emits human-readable `PASS: RELEASE-READY — ...` lines
(no JSON). The parse always yielded empty verdict → gate always refused.

Fix: promote.sh detects gate-open iff output contains a line matching
`^PASS: RELEASE-READY`. WARN/FAIL → refused.

Per ADR-0067 D3: this test commit precedes the fix commit in branch history.
These tests FAIL before the fix and PASS after.

Injection mechanism:
  PROMOTE_HEALTH_CMD — overrides the health.py invocation; if set, promote.sh
      uses this command instead of `python3 .../health.py --check RELEASE-READY`.
  _PROMOTE_SH_SKIP_PUSH — if set to "1", promote.sh skips the actual git push
      (stub for push isolation in tests).

Isolation note (fix for #1038):
  _run_promote now uses a temporary git repo rather than the real REPO_ROOT as
  cwd.  Previously, running promote.sh with cwd=REPO_ROOT caused promote.sh to
  resolve SENTINEL=$REPO_ROOT/.claude/PROMOTE_OK (the real repo sentinel); the
  "proceed" path deletes that sentinel, wiping any operator-created ack.
  With a temp repo, promote.sh's git-common-dir points at the temp .git →
  SENTINEL is inside the temp dir → real repo is never touched.
  A sentinel is created in the temp repo so gate-parse tests (which exercise
  PASS/WARN parsing logic, not sentinel logic) can reach the gate check.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_promote_gate_parse_1036.py -v
"""

import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PROMOTE_SH = REPO_ROOT / "tools" / "promote.sh"


def _to_bash_path(win_path: str) -> str:
    """Convert a Windows path to a bash-compatible path on Windows Git Bash.

    On POSIX systems this is a no-op.  On Windows, replaces backslashes and
    drive letter so bash can invoke the script.
    """
    if platform.system() != "Windows":
        return win_path
    # Try cygpath first (available in Git Bash / MSYS2)
    try:
        result = subprocess.run(
            ["cygpath", "-u", win_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback: manual conversion C:\foo\bar → /c/foo/bar
    p = win_path.replace("\\", "/")
    p = re.sub(r"^([A-Za-z]):/", lambda m: f"/{m.group(1).lower()}/", p)
    return p


def _git(*args, cwd=None, check=True):
    """Run git with args."""
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _make_isolated_repo(parent_tmp: str) -> str:
    """Create a minimal self-contained git repo in parent_tmp.

    Returns the path to the working repo.  This repo has a local bare origin
    and both main + develop branches so promote.sh can resolve them.

    The .git of this repo is NOT a worktree link — git-common-dir == .git →
    LOGROOT == this repo.  SENTINEL = this_repo/.claude/PROMOTE_OK.
    No real repo files are touched.
    """
    bare = os.path.join(parent_tmp, "bare.git")
    os.makedirs(bare)
    _git("init", "--bare", "-b", "main", bare)

    work = os.path.join(parent_tmp, "work")
    _git("clone", bare, work)
    _git("-C", work, "config", "user.email", "test@example.com")
    _git("-C", work, "config", "user.name", "Test")

    current = subprocess.run(
        ["git", "-C", work, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    if current != "main":
        _git("-C", work, "checkout", "-b", "main")

    readme = os.path.join(work, "README.md")
    with open(readme, "w") as f:
        f.write("hello")
    _git("-C", work, "add", "README.md")
    _git("-C", work, "commit", "-m", "init")
    _git("-C", work, "push", "-u", "origin", "HEAD:main")

    _git("-C", work, "checkout", "-b", "develop")
    changes = os.path.join(work, "CHANGES.md")
    with open(changes, "w") as f:
        f.write("dev change")
    _git("-C", work, "add", "CHANGES.md")
    _git("-C", work, "commit", "-m", "dev commit")
    _git("-C", work, "push", "-u", "origin", "develop")

    return work


def _make_stub_health(tmpdir: str, output_line: str) -> str:
    """Create a stub script that prints `output_line` and exits 0.

    Returns the POSIX path to the stub script (bash-compatible).
    The stub emulates the real `health.py --check RELEASE-READY` CLI output
    format: one line starting with PASS:, WARN:, or FAIL:.
    """
    stub_path = os.path.join(tmpdir, "stub_health.sh")
    # Escape any double-quotes in the output line for safety
    safe_line = output_line.replace('"', '\\"')
    with open(stub_path, "w", newline="\n") as f:
        f.write("#!/bin/bash\n")
        f.write(f'printf "%s\\n" "{safe_line}"\n')
        f.write("exit 0\n")
    current_mode = os.stat(stub_path).st_mode
    os.chmod(stub_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return _to_bash_path(stub_path)


def _run_promote(stub_output: str, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run promote.sh with a stubbed health command and push skipped.

    Uses a temporary isolated git repo as cwd so promote.sh never resolves
    its SENTINEL or EVENTS_LOG to the real repo (fix for #1038 isolation bug).
    A sentinel is pre-created in the temp repo so tests that exercise gate-
    parse logic (not sentinel logic) can reach the gate check.

    Returns the CompletedProcess with stdout+stderr captured.
    """
    if not PROMOTE_SH.exists():
        raise FileNotFoundError(f"promote.sh not found at {PROMOTE_SH}")

    with tempfile.TemporaryDirectory(prefix="promote_1036_") as tmpdir:
        # Build isolated repo so promote.sh's git-common-dir stays in tmpdir
        work = _make_isolated_repo(tmpdir)

        # Create sentinel in the temp repo's canonical root
        # (LOGROOT = work, since work/.git is not a worktree link)
        sentinel_dir = os.path.join(work, ".claude")
        os.makedirs(sentinel_dir, exist_ok=True)
        sentinel = os.path.join(sentinel_dir, "PROMOTE_OK")
        with open(sentinel, "w") as f:
            f.write("")

        stub_posix_path = _make_stub_health(tmpdir, stub_output)
        env = os.environ.copy()
        # Point promote.sh at our stub instead of real health.py.
        # Use POSIX path so bash can find the script on Windows Git Bash.
        env["PROMOTE_HEALTH_CMD"] = f"bash {stub_posix_path}"
        env["MSYS_NO_PATHCONV"] = "1"
        # Skip actual git push (test isolation — no real push to main)
        env["_PROMOTE_SH_SKIP_PUSH"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", str(PROMOTE_SH)],
            capture_output=True,
            text=True,
            env=env,
            cwd=work,
            timeout=30,
        )


# ---------------------------------------------------------------------------
# Group 1: KEY regression — PASS line accepted (current code rejects it)
# ---------------------------------------------------------------------------

class TestGateParsePassLine(unittest.TestCase):
    """CORE REGRESSION: promote.sh must accept a PASS: RELEASE-READY line.

    Before the fix: promote.sh parses JSON `verdict` field → always empty →
    always refused even when PASS line is present.
    After the fix: promote.sh greps for `^PASS: RELEASE-READY` → accepts it.
    """

    def test_pass_line_accepted(self):
        """promote.sh must proceed past gate on a PASS: RELEASE-READY line.

        KEY assertion: before the fix this test FAILS because promote.sh refuses
        despite seeing the PASS line (JSON parse yields empty verdict → refused).
        After the fix this test PASSES because the grep finds the PASS line.
        """
        result = _run_promote(
            "PASS: RELEASE-READY - gate open: (a) CI green, (b) tests pass"
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "gate not open",
            combined.lower(),
            f"promote.sh must NOT refuse gate when output is a PASS: RELEASE-READY line.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}\n"
            f"(Before fix: promote.sh rejects PASS line because it parses JSON verdict)",
        )
        self.assertNotIn(
            "could not parse",
            combined.lower(),
            f"promote.sh must not say 'could not parse' when PASS line present.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )

    def test_pass_line_with_detail_accepted(self):
        """PASS line with full detail string is also accepted."""
        result = _run_promote(
            "PASS: RELEASE-READY - gate open: all six conditions pass [injected]"
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "gate not open",
            combined.lower(),
            f"promote.sh must accept PASS: RELEASE-READY with detail.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )


# ---------------------------------------------------------------------------
# Group 2: WARN line → gate refused
# ---------------------------------------------------------------------------

class TestGateParseWarnLine(unittest.TestCase):
    """WARN: RELEASE-READY output must cause promote.sh to refuse (exit 1)."""

    def test_warn_line_refused(self):
        """promote.sh must exit non-zero when health.py outputs WARN: RELEASE-READY."""
        result = _run_promote(
            "WARN: RELEASE-READY - gate held: condition (a) CI not green"
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must exit non-zero on WARN: RELEASE-READY line.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "gate not open",
            combined.lower(),
            f"promote.sh refusal message must mention 'gate not open'.\n"
            f"combined={combined!r}",
        )

    def test_force_fail_path_still_refuses(self):
        """_RELEASE_READY_FORCE_FAIL=1 path still refuses after the fix.

        The real health.py with _RELEASE_READY_FORCE_FAIL=1 emits:
          WARN: RELEASE-READY - gate held: forced fail via _RELEASE_READY_FORCE_FAIL

        We simulate this via stub. The grep for ^PASS: must fail → refuse.
        """
        result = _run_promote(
            "WARN: RELEASE-READY - gate held: forced fail via _RELEASE_READY_FORCE_FAIL (test injection)"
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must refuse when force-fail WARN line present.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )


# ---------------------------------------------------------------------------
# Group 3: FAIL line → gate refused
# ---------------------------------------------------------------------------

class TestGateParseFAILLine(unittest.TestCase):
    """FAIL: RELEASE-READY output must also refuse."""

    def test_fail_line_refused(self):
        """promote.sh must exit non-zero when health.py outputs FAIL: RELEASE-READY."""
        result = _run_promote(
            "FAIL: RELEASE-READY - gate failed: critical error"
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must exit non-zero on FAIL: RELEASE-READY line.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )


# ---------------------------------------------------------------------------
# Group 4: empty / garbage output → gate refused
# ---------------------------------------------------------------------------

class TestGateParseGarbageOutput(unittest.TestCase):
    """If health.py emits no PASS: RELEASE-READY line, gate must be refused."""

    def test_empty_output_refused(self):
        """promote.sh must refuse when health.py emits no output."""
        result = _run_promote("")
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must refuse when health.py emits no output.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )

    def test_json_verdict_output_refused(self):
        """promote.sh must refuse when health.py emits JSON (old expected format).

        Root-cause documentation: old code expected JSON `verdict` field but the
        real CLI never emitted it. After fix, JSON is treated as 'no PASS line'
        → refused. This test documents the test-reality gap that hid the bug.
        """
        result = _run_promote(
            '{"id": "RELEASE-READY", "result": "PASS", "verdict": "true"}'
        )
        self.assertNotEqual(
            result.returncode, 0,
            f"promote.sh must refuse JSON output (not a PASS: line) after fix.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )


# ---------------------------------------------------------------------------
# Group 5: helpful error message includes actual health.py output on refusal
# ---------------------------------------------------------------------------

class TestGateRefusalHelpfulMessage(unittest.TestCase):
    """On refusal, promote.sh must echo the actual health.py output."""

    def test_refusal_echoes_health_output(self):
        """On WARN refusal, stderr must include health.py output text."""
        warn_text = "WARN: RELEASE-READY - gate held: needs-human count=2"
        result = _run_promote(warn_text)
        self.assertNotEqual(result.returncode, 0)
        combined = result.stdout + result.stderr
        # The actual health.py output (or key part) must appear so operator
        # knows WHY it was refused.
        self.assertTrue(
            "WARN" in combined or "needs-human" in combined or "gate held" in combined,
            f"Refusal message must include health.py output text for diagnostics.\n"
            f"combined={combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
