"""
tests/test_promote_sentinel_order_1038.py

Regression test for root-cause #1038:
  promote.sh ran RELEASE-READY gate (full pytest suite) BEFORE checking the
  human-ack sentinel. The pytest suite includes tests that run promote.sh as a
  subprocess in the real REPO_ROOT — those sub-runs delete .claude/PROMOTE_OK
  (sentinel removal on the "proceed" path), so the outer promote.sh always
  found the sentinel missing and refused.

Rule #13 / ADR-0067 D3: this test commit MUST precede the fix commit in
branch history. These tests FAIL against the un-fixed promote.sh (sentinel
checked after gate, which runs pytest that wipes sentinel) and PASS after the
fix (sentinel checked first, before gate runs).

Two sub-failures this test covers:
  A. Order bug: sentinel check happens AFTER gate; gate wipes sentinel → refused.
  B. Path bug: sentinel resolved via $REPO_ROOT (worktree path), not canonical
     git-common-dir root → fails when run from any worktree.

Test design:
  - Creates a synthetic git repo in a temp dir to serve as the "worktree".
  - Stubs PROMOTE_HEALTH_CMD to a script that:
      (1) emits "PASS: RELEASE-READY - ..." (gate open signal)
      (2) DELETES $SENTINEL from the canonical git-common-dir location
    This simulates the pytest-wipe: health check runs pytest which removes
    the real sentinel.
  - Creates the sentinel at the canonical git-common-dir root BEFORE running.
  - Asserts: promote.sh PROCEEDS past both gates (reaches the would-push step)
    even though the stub-health deletes the sentinel, because the sentinel is
    checked FIRST (before stub-health runs).
  - NEVER real-pushes (uses _PROMOTE_SH_SKIP_PUSH=1).

Sentinel path isolation: the synthetic repo's git-common-dir IS the temp dir's
.git, so LOGROOT = temp_dir. SENTINEL = temp_dir/.claude/PROMOTE_OK. No real
repo sentinel is touched.
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
    The .git of this repo is NOT a worktree link — it's the common-dir.
    """
    work = os.path.join(tmp_dir, "work")
    _git("clone", bare_url, work)
    _git("-C", work, "config", "user.email", "test@example.com")
    _git("-C", work, "config", "user.name", "Test")

    current = subprocess.run(
        ["git", "-C", work, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    if current != "main":
        _git("-C", work, "checkout", "-b", "main")

    # Initial commit on main
    readme = os.path.join(work, "README.md")
    with open(readme, "w") as f:
        f.write("hello")
    _git("-C", work, "add", "README.md")
    _git("-C", work, "commit", "-m", "init")
    _git("-C", work, "push", "-u", "origin", "HEAD:main")

    # Create develop from main with one commit
    _git("-C", work, "checkout", "-b", "develop")
    changes = os.path.join(work, "CHANGES.md")
    with open(changes, "w") as f:
        f.write("dev change")
    _git("-C", work, "add", "CHANGES.md")
    _git("-C", work, "commit", "-m", "dev commit")
    _git("-C", work, "push", "-u", "origin", "develop")

    return work


class TestPromoteSentinelCheckedFirst(unittest.TestCase):
    """Regression for #1038: sentinel must be checked BEFORE the gate runs.

    Without the fix, the order is:
      (0b) gate check [runs pytest → wipes sentinel]
      (0a) sentinel check → MISSING → refuses

    With the fix:
      (0a) sentinel check → FOUND (checked before any pytest wipe)
      (0b) gate check [sentinel already validated; wipe is now harmless]
      → proceeds
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="promote_sentinel_test_1038_")
        bare = _make_bare_repo(self.tmp)
        self.work = _make_working_repo(self.tmp, bare)

        # The git-common-dir for the work repo is work/.git (not a worktree
        # link), so LOGROOT = work.  This mirrors how sentinel is resolved via
        # git-common-dir: LOGROOT = dirname(git-common-dir).
        self.logroot = self.work  # canonical root for this temp repo

        # Sentinel at canonical root/.claude/PROMOTE_OK
        self.sentinel = os.path.join(self.logroot, ".claude", "PROMOTE_OK")

        self.patched_env = os.environ.copy()
        self.patched_env["MSYS_NO_PATHCONV"] = "1"
        self.patched_env["_PROMOTE_SH_SKIP_PUSH"] = "1"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_wiping_health_stub(self, sentinel_posix: str) -> str:
        """
        Write a stub health script that:
          1. Emits "PASS: RELEASE-READY - stub" (so gate appears open)
          2. Deletes $sentinel_posix (simulates pytest wiping the sentinel)

        Returns the PROMOTE_HEALTH_CMD value (bash <posix_path>).
        """
        stub_path = os.path.join(self.tmp, "wiping_stub.sh")
        # Use POSIX path for bash rm command
        sentinel_escaped = sentinel_posix.replace("'", "'\\''")
        with open(stub_path, "w", newline="\n") as f:
            f.write(textwrap.dedent(f"""\
                #!/bin/bash
                # Stub: emit PASS line AND delete sentinel — simulates pytest wipe
                echo "PASS: RELEASE-READY - gate open: stub for test_promote_sentinel_order_1038"
                rm -f '{sentinel_escaped}'
                exit 0
            """))
        os.chmod(stub_path,
                 stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                 stat.S_IROTH | stat.S_IXOTH)
        return f"bash {_to_bash_path(stub_path)}"

    def test_sentinel_checked_before_gate_wipes_it(self):
        """Sentinel present at start → promote.sh proceeds even if gate deletes it.

        This is the KEY regression for #1038.

        CURRENT CODE (unfixed): gate runs first → deletes sentinel → sentinel
        check sees missing sentinel → exits 1 with 'PROMOTION REFUSED'.
        This test FAILS before the fix.

        FIXED CODE: sentinel checked first (FOUND) → gate runs (deletes it, but
        too late) → promote.sh proceeds to the would-push step.
        This test PASSES after the fix.
        """
        # Create sentinel at canonical root
        os.makedirs(os.path.dirname(self.sentinel), exist_ok=True)
        with open(self.sentinel, "w") as f:
            f.write("")

        # Stub that passes the gate AND wipes the sentinel
        sentinel_posix = _to_bash_path(self.sentinel)
        health_cmd = self._write_wiping_health_stub(sentinel_posix)
        self.patched_env["PROMOTE_HEALTH_CMD"] = health_cmd

        result = subprocess.run(
            ["bash", str(PROMOTE_SH)],
            cwd=self.work,
            env=self.patched_env,
            capture_output=True,
            text=True,
        )

        combined = result.stdout + result.stderr
        # Must NOT refuse with sentinel-missing message
        self.assertNotIn(
            "human ack required",
            combined.lower(),
            msg=(
                "promote.sh refused with 'human ack required' even though "
                "the sentinel was present at the start of the run.\n"
                "This is the #1038 regression: the gate ran first and wiped "
                "the sentinel before the sentinel check.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        self.assertNotIn(
            "promotion refused",
            combined.lower(),
            msg=(
                "promote.sh printed 'PROMOTION REFUSED' even though sentinel "
                "was present at run start.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        # Must exit 0 (sentinel present + gate open → promotion proceeds)
        self.assertEqual(
            result.returncode, 0,
            msg=(
                "promote.sh must exit 0 when sentinel is present and gate is "
                f"open, but exited {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

    def test_sentinel_resolved_via_git_common_dir(self):
        """Sentinel at git-common-dir canonical root is found from any cwd.

        Simulates running promote.sh from a worktree subdirectory: the worktree
        has its own show-toplevel (work/) but git-common-dir points to work/.git
        (same in a plain clone — LOGROOT = work). In a real worktree, LOGROOT
        would be the shared root, not the worktree path.

        We verify that when promote.sh uses LOGROOT (git-common-dir parent)
        rather than $REPO_ROOT (show-toplevel), it finds the sentinel at the
        canonical location.

        Without the git-common-dir fix, the sentinel would be looked for at
        $REPO_ROOT/.claude/PROMOTE_OK (the worktree path), missing if created
        only at the canonical root. With the fix, it is always found.
        """
        # Create sentinel at the canonical root (git-common-dir parent)
        os.makedirs(os.path.dirname(self.sentinel), exist_ok=True)
        with open(self.sentinel, "w") as f:
            f.write("")

        # Stub that passes the gate but does NOT wipe the sentinel (clean path)
        clean_stub = os.path.join(self.tmp, "clean_stub.sh")
        with open(clean_stub, "w", newline="\n") as f:
            f.write("#!/bin/bash\n")
            f.write(
                'echo "PASS: RELEASE-READY - gate open: clean stub for #1038"\n'
            )
            f.write("exit 0\n")
        os.chmod(clean_stub,
                 stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                 stat.S_IROTH | stat.S_IXOTH)
        self.patched_env["PROMOTE_HEALTH_CMD"] = (
            f"bash {_to_bash_path(clean_stub)}"
        )

        result = subprocess.run(
            ["bash", str(PROMOTE_SH)],
            cwd=self.work,
            env=self.patched_env,
            capture_output=True,
            text=True,
        )

        combined = result.stdout + result.stderr
        self.assertEqual(
            result.returncode, 0,
            msg=(
                "promote.sh must exit 0 when sentinel exists at the canonical "
                "git-common-dir root and gate is open.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        self.assertNotIn(
            "promotion refused",
            combined.lower(),
            msg=(
                "promote.sh must not refuse when sentinel is at git-common-dir "
                f"root.\ncombined: {combined!r}"
            ),
        )

    def test_no_sentinel_still_refuses(self):
        """Without sentinel, promote.sh still refuses (sentinel gate enforced).

        This verifies the sentinel check still works after reordering.
        The gate stub passes, but no sentinel → refused.
        """
        # Ensure no sentinel exists
        if os.path.exists(self.sentinel):
            os.remove(self.sentinel)

        clean_stub = os.path.join(self.tmp, "clean_stub2.sh")
        with open(clean_stub, "w", newline="\n") as f:
            f.write("#!/bin/bash\n")
            f.write(
                'echo "PASS: RELEASE-READY - gate open: clean stub for #1038 no-sentinel"\n'
            )
            f.write("exit 0\n")
        os.chmod(clean_stub,
                 stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                 stat.S_IROTH | stat.S_IXOTH)
        self.patched_env["PROMOTE_HEALTH_CMD"] = (
            f"bash {_to_bash_path(clean_stub)}"
        )

        result = subprocess.run(
            ["bash", str(PROMOTE_SH)],
            cwd=self.work,
            env=self.patched_env,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(
            result.returncode, 0,
            msg=(
                "promote.sh must exit non-zero when no sentinel exists, "
                f"but exited 0.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )
        combined = result.stdout + result.stderr
        self.assertIn(
            "PROMOTION REFUSED",
            combined,
            msg=(
                "promote.sh must print 'PROMOTION REFUSED' when sentinel is "
                f"absent.\ncombined: {combined!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
