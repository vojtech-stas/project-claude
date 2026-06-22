"""
Regression test for issue #950 — branch-restore must hard-align local main
to origin/main when local main is ahead of (or diverged from) origin/main.

BUG: branch-restore "main" with local main 1 commit AHEAD of origin/main
returned exit 0 and left local main on the wrong (un-merged feature) commit
because the ff-only path exited early when CURRENT == EXPECTED without
verifying that local main actually equals origin/main.

FIX: when target branch is "main", hard-align via
  git fetch origin main && git checkout main && git reset --hard origin/main
regardless of whether local main is ahead/behind/diverged.

Test strategy: create a temp git repo with a local "main" advanced 1 commit
AHEAD of origin/main, run tools/worktree-guard.sh branch-restore main
(with cwd = the temp repo), and assert local main is reset to origin/main's SHA.

Runner: stdlib unittest only — NO top-level pytest import.
  python -m unittest tests/test_branch_restore_hard_align_950.py -v
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# Resolve the repo root (tests/ is one level below repo root).
REPO_ROOT = Path(__file__).parent.parent
GUARD_SH = REPO_ROOT / "tools" / "worktree-guard.sh"


def _git_list(args, cwd, check=True):
    """Run git command as a list (avoids shell quoting issues on Windows)."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def _git(cmd_str, cwd, check=True):
    """Run a simple git command string (no special chars) in cwd."""
    return subprocess.run(
        cmd_str,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        shell=True,
    )


class TestBranchRestoreHardAlignMain(unittest.TestCase):
    """branch-restore 'main' must hard-align local main to origin/main
    even when local main is ahead of origin/main (issue #950).
    """

    def setUp(self):
        """Set up a temporary two-repo environment:
          - origin/: bare repo acting as the remote
          - local/: clone of origin, with local main advanced 1 commit ahead
        """
        # Skip on platforms where bash is not available.
        result = subprocess.run(
            ["bash", "--version"], capture_output=True, text=True
        )
        if result.returncode != 0:
            self.skipTest("bash not available — skipping behavioral test")

        if not GUARD_SH.exists():
            self.fail(f"Guard script not found at {GUARD_SH}")

        self._tmpdir = tempfile.mkdtemp(prefix="guard-test-950-")
        origin_path = os.path.join(self._tmpdir, "origin")
        local_path = os.path.join(self._tmpdir, "local")

        # 1. Create a seed repo with an initial commit on main.
        seed_path = os.path.join(self._tmpdir, "seed")
        os.makedirs(seed_path)
        _git_list(["init", "."], seed_path)
        _git_list(["config", "user.email", "test@example.com"], seed_path)
        _git_list(["config", "user.name", "Test"], seed_path)
        _git_list(["checkout", "-b", "main"], seed_path)

        # Create the initial file and commit.
        readme = os.path.join(seed_path, "README.txt")
        with open(readme, "w") as f:
            f.write("initial\n")
        _git_list(["add", "README.txt"], seed_path)
        _git_list(["commit", "-m", "initial commit"], seed_path)

        # 2. Clone the seed as a bare "origin".
        os.makedirs(origin_path)
        _git_list(["clone", "--bare", seed_path, origin_path], self._tmpdir)

        # 3. Clone the bare origin into "local".
        _git_list(["clone", origin_path, local_path], self._tmpdir)
        _git_list(["config", "user.email", "test@example.com"], local_path)
        _git_list(["config", "user.name", "Test"], local_path)

        # Ensure we're on local "main" that tracks origin/main.
        _git_list(["checkout", "main"], local_path)

        # 4. Add a commit on local main that does NOT exist on origin/main.
        #    This simulates the fix-on-PR-branch dispatch pattern (#950).
        extra = os.path.join(local_path, "EXTRA.txt")
        with open(extra, "w") as f:
            f.write("un-merged feature commit\n")
        _git_list(["add", "EXTRA.txt"], local_path)
        _git_list(
            ["commit", "-m", "un-merged feature commit local main ahead of origin"],
            local_path,
        )

        self._local_path = local_path
        self._origin_path = origin_path

        # Capture origin/main SHA (what local main SHOULD equal after the fix).
        self._origin_main_sha = _git_list(
            ["rev-parse", "origin/main"], local_path
        ).stdout.strip()

        # Capture the current local main SHA (which is 1 ahead of origin/main).
        self._local_ahead_sha = _git_list(
            ["rev-parse", "main"], local_path
        ).stdout.strip()

        # Sanity: the two SHAs must differ (local is ahead).
        self.assertNotEqual(
            self._local_ahead_sha,
            self._origin_main_sha,
            "Test setup error: local main should be ahead of origin/main",
        )

    def tearDown(self):
        """Remove the temporary repos."""
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_branch_restore_hard_aligns_main_when_ahead(self):
        """branch-restore main must reset local main to origin/main when ahead.

        Before fix: exits 0 but leaves local main at the feature commit (1 ahead).
        After fix: resets local main to origin/main's SHA.
        """
        guard_sh_abs = str(GUARD_SH.resolve()).replace("\\", "/")

        # Run branch-restore main with cwd = the local repo.
        # The script uses `git` without -C so it operates on cwd.
        result = subprocess.run(
            ["bash", str(GUARD_SH.resolve()), "branch-restore", "main"],
            cwd=self._local_path,
            capture_output=True,
            text=True,
        )

        # Assert exit code 0 (the restore should succeed, not error out).
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"branch-restore main exited {result.returncode} (expected 0).\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )

        # Assert local main is NOW at origin/main's SHA (hard-aligned).
        local_main_after = _git_list(
            ["rev-parse", "main"], self._local_path
        ).stdout.strip()

        self.assertEqual(
            local_main_after,
            self._origin_main_sha,
            msg=(
                f"After branch-restore main, local main is still at {local_main_after} "
                f"(the ahead commit), NOT at origin/main {self._origin_main_sha}.\n"
                f"This is the #950 bug: branch-restore must hard-align main to "
                f"origin/main, not leave it ahead."
            ),
        )

    def test_branch_restore_main_is_idempotent_when_already_aligned(self):
        """branch-restore main is a no-op when local main already equals origin/main."""
        # First align manually.
        _git_list(["reset", "--hard", "origin/main"], self._local_path)
        aligned_sha = _git_list(
            ["rev-parse", "main"], self._local_path
        ).stdout.strip()
        self.assertEqual(aligned_sha, self._origin_main_sha)

        # Run branch-restore main again.
        result = subprocess.run(
            ["bash", str(GUARD_SH.resolve()), "branch-restore", "main"],
            cwd=self._local_path,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"branch-restore main (already aligned) exited {result.returncode}.\n"
                f"stderr: {result.stderr}"
            ),
        )

        # Local main must still be at origin/main.
        local_main_after = _git_list(
            ["rev-parse", "main"], self._local_path
        ).stdout.strip()
        self.assertEqual(
            local_main_after,
            self._origin_main_sha,
            msg="Idempotency failure: branch-restore main moved local main away from origin/main",
        )


if __name__ == "__main__":
    unittest.main()
