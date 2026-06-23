"""
Regression test for root-cause #880: promote.sh ran without human ack,
pushing main without authorization.

Rule #13 / ADR-0067 D3: this test commit MUST precede the fix commit in
branch history. These tests fail against the un-guarded promote.sh and
pass after the sentinel gate is added.

Test design:
  - Uses a throwaway LOCAL bare repo as origin — no real push to origin/main.
  - Stubs git push by overriding PATH to point at a mock git wrapper.
  - Asserts: (a) absent sentinel → non-zero exit, prints refusal, no push;
             (b) sentinel present → proceeds (push stubbed), removes sentinel.
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

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROMOTE_SH = os.path.join(REPO_ROOT, "tools", "promote.sh")


def _to_bash_path(win_path: str) -> str:
    """Convert a Windows path to a bash-compatible POSIX path for Git Bash.

    On non-Windows systems this is a no-op.
    """
    if platform.system() != "Windows":
        return win_path
    try:
        result = subprocess.run(
            ["cygpath", "-u", win_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback: C:\foo\bar → /c/foo/bar
    p = win_path.replace("\\", "/")
    p = re.sub(r"^([A-Za-z]):/", lambda m: f"/{m.group(1).lower()}/", p)
    return p


def _git(*args, cwd=None, check=True):
    """Run git with args; raises on non-zero if check=True."""
    return subprocess.run(
        ["git"] + list(args),
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _make_bare_repo(tmp_dir):
    """Create a minimal bare git repo usable as a fake origin."""
    bare = os.path.join(tmp_dir, "bare.git")
    os.makedirs(bare)
    _git("init", "--bare", "-b", "main", bare)
    return bare


def _make_working_repo(tmp_dir, bare_url):
    """
    Clone the bare repo, make an initial commit on main, push it,
    then create develop branching from main with one extra commit.
    Returns the path to the working repo.
    """
    work = os.path.join(tmp_dir, "work")
    _git("clone", bare_url, work)

    # configure identity so commits succeed
    _git("-C", work, "config", "user.email", "test@example.com")
    _git("-C", work, "config", "user.name", "Test")
    _git("-C", work, "config", "init.defaultBranch", "main")

    # Ensure we are on 'main' (git may have used 'master')
    current = subprocess.run(
        ["git", "-C", work, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True
    ).stdout.strip()
    if current != "main":
        _git("-C", work, "checkout", "-b", "main")

    # Initial commit on main
    _touch(os.path.join(work, "README.md"), "hello")
    _git("-C", work, "add", "README.md")
    _git("-C", work, "commit", "-m", "init")
    _git("-C", work, "push", "-u", "origin", "HEAD:main")

    # Create develop from main, add one commit
    _git("-C", work, "checkout", "-b", "develop")
    _touch(os.path.join(work, "CHANGES.md"), "dev change")
    _git("-C", work, "add", "CHANGES.md")
    _git("-C", work, "commit", "-m", "dev commit")
    _git("-C", work, "push", "-u", "origin", "develop")

    return work


def _touch(path, content=""):
    with open(path, "w") as f:
        f.write(content)


def _real_git_path():
    """Locate the real git binary (not our shim)."""
    result = subprocess.run(
        ["which", "git"], capture_output=True, text=True
    )
    return result.stdout.strip() or "/usr/bin/git"


def _write_mock_git(bin_dir, push_log_path):
    """
    Write a git shim that intercepts 'push' calls (logging them to
    push_log_path) and delegates everything else to the real git.
    This ensures promote.sh can still call git for read ops but
    a push never reaches origin/main.
    """
    real_git = _real_git_path()
    shim = os.path.join(bin_dir, "git")
    shim_content = textwrap.dedent(f"""\
        #!/bin/bash
        # Mock git: intercept push, log it, succeed without pushing.
        if [ "$1" = "push" ]; then
            echo "MOCK_PUSH: $*" >> "{push_log_path}"
            exit 0
        fi
        exec "{real_git}" "$@"
    """)
    with open(shim, "w") as f:
        f.write(shim_content)
    os.chmod(shim, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
             stat.S_IROTH | stat.S_IXOTH)
    return shim


class TestPromoteAckGate(unittest.TestCase):
    """Regression suite for #880: promote.sh must require human-ack sentinel."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="promote_test_")
        bare = _make_bare_repo(self.tmp)
        self.work = _make_working_repo(self.tmp, bare)

        # Directory for mock git shim
        self.bin_dir = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin_dir)

        # Log file for intercepted pushes
        self.push_log = os.path.join(self.tmp, "push.log")

        _write_mock_git(self.bin_dir, self.push_log)

        # Patch PATH so mock git wins
        self.patched_env = os.environ.copy()
        self.patched_env["PATH"] = self.bin_dir + os.pathsep + os.environ["PATH"]

        # Sentinel path inside the work repo
        self.sentinel = os.path.join(self.work, ".claude", "PROMOTE_OK")

        # Stub PROMOTE_HEALTH_CMD so promote.sh passes the RELEASE-READY gate
        # in both test scenarios.  Updated by slice #1036: the real CLI emits
        # `PASS: RELEASE-READY — <detail>` (not JSON), so the stub now matches
        # the real format.  The old JSON stub caused promote.sh to refuse even
        # when the gate was open — the test-reality gap that hid bug #1036.
        health_stub_sh = os.path.join(self.tmp, "health_stub.sh")
        with open(health_stub_sh, "w", newline="\n") as f:
            f.write(textwrap.dedent("""\
                #!/bin/bash
                # Stub: emit real PASS: RELEASE-READY format (slice #1036 fix)
                echo "PASS: RELEASE-READY - gate open: stub for test_promote_ack_880"
                exit 0
            """))
        os.chmod(health_stub_sh,
                 stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        # Use POSIX path so bash can find the script on Windows Git Bash.
        self.patched_env["PROMOTE_HEALTH_CMD"] = f"bash {_to_bash_path(health_stub_sh)}"
        self.patched_env["MSYS_NO_PATHCONV"] = "1"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_promote(self):
        """Run promote.sh in the work repo; return CompletedProcess."""
        return subprocess.run(
            ["bash", PROMOTE_SH],
            cwd=self.work,
            env=self.patched_env,
            capture_output=True,
            text=True,
        )

    def _push_occurred(self):
        """Return True if mock git intercepted at least one push call."""
        if not os.path.exists(self.push_log):
            return False
        with open(self.push_log) as f:
            content = f.read().strip()
        return bool(content)

    # ------------------------------------------------------------------
    # Test (a): absent sentinel → non-zero exit, prints refusal, no push
    # ------------------------------------------------------------------
    def test_refuses_without_sentinel(self):
        """promote.sh MUST exit non-zero and NOT push when PROMOTE_OK absent."""
        # Ensure sentinel is absent
        if os.path.exists(self.sentinel):
            os.remove(self.sentinel)

        result = self._run_promote()

        # Must exit non-zero (gate blocked)
        self.assertNotEqual(
            result.returncode, 0,
            msg=(
                "promote.sh should exit non-zero when .claude/PROMOTE_OK is "
                "absent, but it exited 0.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )

        # Must print the refusal message
        combined = result.stdout + result.stderr
        self.assertIn(
            "PROMOTION REFUSED",
            combined,
            msg=(
                "promote.sh should print 'PROMOTION REFUSED' when sentinel is "
                f"absent.\nstdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )
        self.assertIn(
            "PROMOTE_OK",
            combined,
            msg=(
                "Refusal message should mention 'PROMOTE_OK'.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )

        # Must NOT have pushed
        self.assertFalse(
            self._push_occurred(),
            msg=(
                "promote.sh performed a git push even though "
                ".claude/PROMOTE_OK was absent — this is the #880 regression."
            ),
        )

    # ------------------------------------------------------------------
    # Test (b): sentinel present → proceeds (push stubbed), removes sentinel
    # ------------------------------------------------------------------
    def test_proceeds_and_removes_sentinel_when_present(self):
        """promote.sh should proceed and remove PROMOTE_OK when sentinel exists."""
        # Create the sentinel
        os.makedirs(os.path.dirname(self.sentinel), exist_ok=True)
        _touch(self.sentinel, "")

        result = self._run_promote()

        # Must exit 0 (promotion allowed)
        self.assertEqual(
            result.returncode, 0,
            msg=(
                "promote.sh should exit 0 when .claude/PROMOTE_OK is present, "
                f"but it exited {result.returncode}.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )

        # Sentinel must be removed (one-shot gate)
        self.assertFalse(
            os.path.exists(self.sentinel),
            msg=(
                "promote.sh should remove .claude/PROMOTE_OK after a successful "
                "promotion (one-shot sentinel), but the file still exists."
            ),
        )


if __name__ == "__main__":
    unittest.main()
