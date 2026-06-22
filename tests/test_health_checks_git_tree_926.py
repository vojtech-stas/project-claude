"""
Regression test for issue #926 — health checks enumerate inputs from the committed
git tree, not arbitrary on-disk files.

Root cause: PARITY's skill-declared-ID parser (and STRUCT-*/DOCS-* enumerators) read
from the filesystem via Path.read_text / Path.glob / rglob against _HEALTH_REPO_ROOT.
When a worktree carries untracked or stale on-disk files, spurious IDs / drift are
reported — a false WARN/FAIL that disagrees with CI (which operates on committed state).

This file contains two test classes:
  1. TestParityIgnoresUntrackedCriticsFile: PARITY must not pick up DOCS-* IDs from
     an untracked codebase-critic.md. Before fix: WARN (skill_gaps non-empty).
     After fix: PASS (only reads tracked file; untracked decoy ignored).

  2. TestDocs10IgnoresUntrackedSkillFile: DOCS-10 must not flag an untracked skill
     file containing the backlog-label pattern. Before fix: FAIL (false positive).
     After fix: PASS (only enumerates tracked paths).

Runner: stdlib unittest; NO top-level pytest import.
  python -m pytest tests/test_health_checks_git_tree_926.py -v
  python -m unittest tests.test_health_checks_git_tree_926 -v
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HEALTH_PY = REPO_ROOT / "dashboard" / "health.py"


def _init_temp_git_repo(tmp: Path) -> None:
    """Initialise a minimal git repo with one committed file in tmp/."""
    subprocess.run(["git", "init", str(tmp)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(tmp), "config", "user.email", "test@test.com"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "config", "user.name", "Test"],
        capture_output=True, check=True,
    )
    placeholder = tmp / "placeholder.txt"
    placeholder.write_text("regression-test-anchor\n")
    subprocess.run(
        ["git", "-C", str(tmp), "add", "placeholder.txt"],
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp), "commit", "-m", "init"],
        capture_output=True, check=True,
    )


class TestParityIgnoresUntrackedCriticsFile(unittest.TestCase):
    """PARITY must enumerate skill IDs only from the committed codebase-critic.md.

    When a worktree has an untracked codebase-critic.md on disk (e.g. left by a
    stale checkout or wrong-dir copy), PARITY must NOT read it and must NOT produce
    spurious skill_gaps.

    Bug: before fix, `_CODEBASE_CRITIC_MD.read_text()` picks up ANY file at that
    path regardless of git-tracked status → untracked decoy → fake skill_gaps → WARN.
    Fix: check `git ls-files` for the file before reading; if untracked, treat as
    absent (return empty skill_ids).
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init_temp_git_repo(self.tmp)
        # Create a minimal tools/ci-checks.sh (PARITY reads this for CI-consumed IDs)
        tools_dir = self.tmp / "tools"
        tools_dir.mkdir()
        (tools_dir / "ci-checks.sh").write_text("#!/bin/bash\n# empty\n")
        # Create the agents dir
        agents_dir = self.tmp / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        # Create an UNTRACKED codebase-critic.md with a fake DOCS-ZZDECOY heading
        # (the em-dash — must match the pattern r"###\s+...\s+—")
        decoy = agents_dir / "codebase-critic.md"
        decoy.write_text(
            "### DOCS-ZZDECOY999 — a fake untracked check\n",
            encoding="utf-8",
        )
        # NOTE: decoy is NOT git-added — it remains untracked in self.tmp

    def tearDown(self):
        self._td.cleanup()

    def _run_parity_in_subprocess(self) -> dict:
        """Run check_parity() in a subprocess with _HEALTH_REPO_ROOT and
        _CODEBASE_CRITIC_MD patched to self.tmp, return the result dict."""
        import json
        script = (
            "import sys, json\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, r'{REPO_ROOT / 'dashboard'}')\n"
            "import health as h\n"
            f"tmp = Path(r'{self.tmp}')\n"
            "h._HEALTH_REPO_ROOT = tmp\n"
            "h._CODEBASE_CRITIC_MD = tmp / '.claude' / 'agents' / 'codebase-critic.md'\n"
            "result = h.check_parity()\n"
            "print(json.dumps(result))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "dashboard"),
            timeout=30,
        )
        if proc.returncode != 0:
            self.fail(
                f"check_parity subprocess failed (exit={proc.returncode}):\n"
                f"stderr: {proc.stderr[:500]}"
            )
        return json.loads(proc.stdout.strip())

    def test_parity_ignores_untracked_codebase_critic(self):
        """PARITY must return PASS (no skill_gaps) when codebase-critic.md is untracked.

        The untracked decoy has '### DOCS-ZZDECOY999 — ...' which would produce
        skill_gaps=['DOCS-ZZDECOY999'] -> WARN before the fix.
        After the fix, the untracked file is ignored and no skill_gaps are reported.
        """
        result = self._run_parity_in_subprocess()
        skill_gaps = result.get("skill_gaps", [])
        self.assertNotIn(
            "DOCS-ZZDECOY999",
            skill_gaps,
            msg=(
                "PARITY reported skill_gaps containing 'DOCS-ZZDECOY999' — "
                "a fake ID from an UNTRACKED codebase-critic.md decoy. "
                "The check must enumerate declared IDs only from the committed "
                "git tree (git ls-files), not arbitrary on-disk files. "
                f"Full result: {result}"
            ),
        )
        result_val = result.get("result")
        self.assertNotEqual(
            "WARN",
            result_val,
            msg=(
                f"PARITY returned WARN due to an untracked decoy file. "
                f"Expected PASS or FAIL (not WARN from spurious skill_gaps). "
                f"Full result: {result}"
            ),
        )


class TestDocs10IgnoresUntrackedSkillFile(unittest.TestCase):
    """DOCS-10 must not flag an untracked skill file containing the backlog-label pattern.

    Bug: before fix, check_docs10_backlog_surfacing() calls rglob('*.md') on
    .claude/skills/ which picks up untracked files → spurious FAIL.
    Fix: enumerate only tracked files via git ls-files.
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init_temp_git_repo(self.tmp)
        # Create an UNTRACKED skills/zzdecoy/SKILL.md with the backlog-label pattern
        skills_dir = self.tmp / ".claude" / "skills" / "zzdecoy-926"
        skills_dir.mkdir(parents=True)
        decoy = skills_dir / "SKILL.md"
        decoy.write_text(
            "# Decoy Skill (untracked)\n"
            "This is NOT a real skill. It contains `backlog`-labeled pattern "
            "to test that DOCS-10 ignores untracked files.\n",
            encoding="utf-8",
        )
        # Create agents dir (DOCS-10 scans both agents and skills)
        (self.tmp / ".claude" / "agents").mkdir(parents=True)
        # NOTE: nothing is git-added; both dirs are untracked

    def tearDown(self):
        self._td.cleanup()

    def _run_docs10_in_subprocess(self) -> dict:
        """Run check_docs10_backlog_surfacing() with _HEALTH_REPO_ROOT patched."""
        import json
        script = (
            "import sys, json\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, r'{REPO_ROOT / 'dashboard'}')\n"
            "import health as h\n"
            f"tmp = Path(r'{self.tmp}')\n"
            "h._HEALTH_REPO_ROOT = tmp\n"
            "result = h.check_docs10_backlog_surfacing()\n"
            "print(json.dumps(result))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "dashboard"),
            timeout=30,
        )
        if proc.returncode != 0:
            self.fail(
                f"check_docs10 subprocess failed (exit={proc.returncode}):\n"
                f"stderr: {proc.stderr[:500]}"
            )
        return json.loads(proc.stdout.strip())

    def test_docs10_ignores_untracked_skill_file(self):
        """DOCS-10 must not flag a backlog-label pattern in an untracked skill file.

        The decoy has the exact ``backlog``-labeled pattern. Before fix, DOCS-10
        returns FAIL (false positive). After fix, DOCS-10 returns PASS because it
        only enumerates git-tracked paths.
        """
        result = self._run_docs10_in_subprocess()
        detail = result.get("detail", "")
        self.assertNotIn(
            "zzdecoy-926",
            detail,
            msg=(
                "DOCS-10 flagged '.claude/skills/zzdecoy-926/SKILL.md' which is "
                "an UNTRACKED file. The check must enumerate skill files only from "
                "the committed git tree (git ls-files), not arbitrary on-disk files. "
                f"Full result: {result}"
            ),
        )
        result_val = result.get("result")
        self.assertNotEqual(
            "FAIL",
            result_val,
            msg=(
                f"DOCS-10 returned FAIL due to an untracked decoy file. "
                f"Expected PASS (no tracked files contain the pattern). "
                f"Full result: {result}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
