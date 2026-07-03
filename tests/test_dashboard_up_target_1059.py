"""
tests/test_dashboard_up_target_1059.py

Regression test for #1059 — dashboard-up.ps1 misclassifies a real git
WORKTREE (e.g. the live-dashboard worktree) as "repo root" when the script
is invoked with its own directory located inside that worktree, because the
old classification compared $TARGET against a hardcoded
".claude/worktrees/live-dashboard" path rather than asking git the truth.

Root cause (per issue #1059 body): the classification never asked git
whether TARGET is a worktree at all — it only special-cased one hardcoded
subpath. When dashboard-up.ps1 is copied into / run from a DIFFERENT
worktree's tools/ dir (as happens for any worktree that isn't literally
named "live-dashboard", or when $RepoRoot resolves to the worktree itself),
the hardcoded-path check fails, $TARGET falls back to $RepoRoot (the
worktree), and $IsLiveDashboardTarget becomes $false -> "target is repo
root - skipping reset" even though $TARGET IS a worktree.

The correct classification (per the fix) is git truth:
    git -C <target> rev-parse --git-dir
    git -C <target> rev-parse --git-common-dir
  A target is a WORKTREE iff --git-dir != --git-common-dir (a real repo
  root has --git-dir == --git-common-dir == ".git").

This test creates a REAL git worktree via `git worktree add` (never
touching the real live-dashboard worktree or any shared session tree),
copies dashboard-up.ps1 into <worktree>/tools/, runs it there with
-CheckOnly (side-effect-free), and asserts the decision output correctly
names the target as a worktree (would-reset-eligible). It ALSO creates a
separate scratch plain `git init` repo (NOT a worktree of anything) and
asserts that invocation names the target as root (skip-reset) -- note
this canNOT reuse THIS repo's own REPO_ROOT for that assertion, because
under harness worktree-isolation (ADR-0036) REPO_ROOT itself may already
BE a linked worktree of the shared .git, which would make the "root"
assertion meaningless (it would correctly say "worktree" too).

Per ADR-0067 D3: this test file is committed BEFORE the fix. It FAILS
before the fix (classification says "repo root" for the worktree target)
and PASSES after (classification says "worktree").

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_dashboard_up_target_1059.py -v
"""

import shutil
import socket
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = REPO_ROOT / "tools" / "dashboard-up.ps1"

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _free_port() -> int:
    """Find a free TCP port on 127.0.0.1 (test doesn't fight real listeners)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_checkonly(script_path: Path, port: int) -> subprocess.CompletedProcess:
    """Invoke <script_path> -CheckOnly with DASH_PORT=<port>."""
    import os

    env = dict(os.environ)
    env["DASH_PORT"] = str(port)
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-File", str(script_path), "-CheckOnly"],
        capture_output=True, text=True, env=env, timeout=30,
    )


@unittest.skipUnless(POWERSHELL, "powershell/pwsh not available on this system")
class TestDashboardUpTargetClassification(unittest.TestCase):
    """#1059: classification must use git truth (--git-dir vs
    --git-common-dir), not a hardcoded path comparison."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp(prefix="dashboard-up-1059-")
        cls._worktree_dir = str(Path(cls._tmpdir) / f"zzztest-worktree-{uuid.uuid4().hex[:8]}")

        # Create a REAL, disposable git worktree off a throwaway branch tip
        # of THIS repo's current HEAD. Never touches the real live-dashboard
        # worktree or any shared/session worktree (isolated under a fresh
        # tempdir, unique branch name).
        cls._branch_name = f"zzztest-1059-{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "worktree", "add", "-b", cls._branch_name,
             cls._worktree_dir, "HEAD"],
            capture_output=True, text=True, check=True,
        )

        # Copy dashboard-up.ps1 into <worktree>/tools/ so $RepoRoot (parent
        # of $ScriptDir) resolves to the worktree itself -- reproducing the
        # real-world shape where the script lives inside the live-dashboard
        # worktree's own tools/ dir.
        worktree_tools = Path(cls._worktree_dir) / "tools"
        worktree_tools.mkdir(parents=True, exist_ok=True)
        cls._worktree_script = worktree_tools / "dashboard-up.ps1"
        shutil.copyfile(SCRIPT_PATH, cls._worktree_script)

        # Separate scratch PLAIN repo root (a fresh `git init`, NOT a
        # worktree of anything) -- used for the "root" classification
        # assertion. This canNOT reuse THIS repo's own REPO_ROOT: under
        # harness worktree-isolation (ADR-0036) REPO_ROOT may itself
        # already be a linked worktree of a shared .git, in which case it
        # legitimately classifies as "worktree" too, making the "root"
        # assertion meaningless.
        cls._root_dir = str(Path(cls._tmpdir) / f"zzztest-root-{uuid.uuid4().hex[:8]}")
        Path(cls._root_dir).mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "-C", cls._root_dir, "init", "-q"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", cls._root_dir, "config", "user.email", "test@example.com"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "-C", cls._root_dir, "config", "user.name", "test"],
            capture_output=True, text=True, check=True,
        )
        root_tools = Path(cls._root_dir) / "tools"
        root_tools.mkdir(parents=True, exist_ok=True)
        cls._root_script = root_tools / "dashboard-up.ps1"
        shutil.copyfile(SCRIPT_PATH, cls._root_script)
        # dashboard-up.ps1 shells out to `git rev-parse origin/develop` for
        # developSha (unrelated to classification) -- a bare `git init` with
        # no commits/remote will just print developSha=(null), which is
        # fine; the classification lines are independent of that value.

    @classmethod
    def tearDownClass(cls):
        # Always remove the scratch worktree + branch + root repo, even on
        # failure.
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force",
             cls._worktree_dir],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "branch", "-D", cls._branch_name],
            capture_output=True, text=True,
        )
        shutil.rmtree(cls._tmpdir, ignore_errors=True)

    def test_git_truth_confirms_worktree_shape(self):
        """Sanity: the scratch worktree dir IS a worktree by git's own
        definition (--git-dir != --git-common-dir), and the scratch plain
        repo root is NOT (--git-dir == --git-common-dir)."""
        git_dir = subprocess.run(
            ["git", "-C", self._worktree_dir, "rev-parse", "--git-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        common_dir = subprocess.run(
            ["git", "-C", self._worktree_dir, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertNotEqual(
            Path(git_dir).resolve(), Path(common_dir).resolve(),
            "scratch dir must be a real worktree (--git-dir != --git-common-dir)",
        )

        root_git_dir = subprocess.run(
            ["git", "-C", self._root_dir, "rev-parse", "--git-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        root_common_dir = subprocess.run(
            ["git", "-C", self._root_dir, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(
            Path(self._root_dir, root_git_dir).resolve(),
            Path(self._root_dir, root_common_dir).resolve(),
            "scratch plain repo root must NOT be a worktree (--git-dir == --git-common-dir)",
        )

    def test_checkonly_real_worktree_target_classified_as_worktree(self):
        """Running dashboard-up.ps1 -CheckOnly FROM a real worktree's tools/
        dir must print an explicit classification line naming TARGET as a
        worktree (reset-eligible), not root.

        FAILS before the fix: the old -CheckOnly output prints no
        classification line at all (the worktree/root check + its message
        only existed in the non-CheckOnly action path), so there is no
        'classification: worktree' anywhere in stdout. PASSES after the fix
        (git-truth classification emits an explicit classification line
        naming it 'worktree' even under -CheckOnly, per the #1059
        acceptance criterion: 'update -CheckOnly output to name the
        classification for auditability')."""
        port = _free_port()
        result = _run_checkonly(self._worktree_script, port)
        self.assertEqual(
            result.returncode, 0,
            f"exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        stdout_lower = result.stdout.lower()
        self.assertIn(
            "classification: worktree", stdout_lower,
            f"expected an explicit '-CheckOnly' classification line naming "
            f"the target as a worktree (would allow reset): {result.stdout!r}",
        )
        self.assertNotIn(
            "classification: root", stdout_lower,
            f"target was misclassified as repo root (the #1059 bug): {result.stdout!r}",
        )

    def test_checkonly_plain_repo_root_classified_as_root(self):
        """Running dashboard-up.ps1 -CheckOnly from a scratch PLAIN repo
        root (a fresh `git init`, not a worktree of anything) must print an
        explicit classification line naming TARGET as root (skip-reset
        guard preserved for the real repo root).

        FAILS before the fix (no classification line exists yet in
        -CheckOnly output). PASSES after the fix."""
        port = _free_port()
        result = _run_checkonly(self._root_script, port)
        self.assertEqual(
            result.returncode, 0,
            f"exit={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        stdout_lower = result.stdout.lower()
        self.assertIn(
            "classification: root", stdout_lower,
            f"expected an explicit '-CheckOnly' classification line naming "
            f"the target as root (skip reset): {result.stdout!r}",
        )
        self.assertNotIn(
            "classification: worktree", stdout_lower,
            f"a plain repo root was misclassified as a worktree: {result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
