"""
Regression tests for slice #841 — guard layer migrated to origin/develop.

Asserts that tools/worktree-guard.sh and tools/ci-checks.sh reference
origin/develop (not origin/main) as the integration branch, and that
session-start.sh reports divergence vs origin/develop, per ADR-0070 D1.

All assertions are offline (file-system content greps); no network calls;
deterministic on all platforms.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_guard_develop_841.py -v
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GUARD_SH = REPO_ROOT / "tools" / "worktree-guard.sh"
CI_SH = REPO_ROOT / "tools" / "ci-checks.sh"
SESSION_START_SH = REPO_ROOT / ".claude" / "hooks" / "session-start.sh"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class TestWorktreeGuardDevelop(unittest.TestCase):
    """worktree-guard.sh must reference origin/develop, not origin/main,
    for all integration-branch semantics (ADR-0070 D1 + ADR-0058 D3).
    """

    def setUp(self):
        self.content = _read(GUARD_SH)

    def test_no_origin_main_refs(self):
        """worktree-guard.sh must contain zero 'origin/main' references."""
        hits = [
            ln for ln in self.content.splitlines()
            if "origin/main" in ln
        ]
        self.assertEqual(
            [],
            hits,
            msg=(
                "worktree-guard.sh still contains 'origin/main' reference(s) "
                "(should be origin/develop after slice #841 migration):\n"
                + "\n".join(f"  {h}" for h in hits)
            ),
        )

    def test_branch_restore_fetches_develop(self):
        """branch-restore mode must fetch origin develop (not main)."""
        self.assertIn(
            "fetch origin develop",
            self.content,
            msg="branch-restore must fetch 'origin develop', not 'origin main'",
        )

    def test_branch_restore_ff_check_against_develop(self):
        """FF-only check must compare HEAD against origin/develop."""
        self.assertIn(
            "origin/develop",
            self.content,
            msg="FF-only ancestor check must reference origin/develop",
        )
        # Specifically the merge-base --is-ancestor line
        self.assertRegex(
            self.content,
            r"merge-base --is-ancestor HEAD origin/develop",
            msg="merge-base --is-ancestor must use origin/develop",
        )

    def test_branch_restore_checkout_to_develop(self):
        """ff-restore checkout must target origin/develop."""
        self.assertIn(
            "checkout -B",
            self.content,
            msg="branch-restore must use checkout -B",
        )
        self.assertRegex(
            self.content,
            r'checkout -B "\$EXPECTED" origin/develop',
            msg="checkout -B must target origin/develop",
        )

    def test_root_sync_fetches_develop(self):
        """root-sync must fetch origin develop (integration branch)."""
        self.assertIn(
            "fetch origin develop",
            self.content,
            msg="root-sync must fetch 'origin develop'",
        )

    def test_root_sync_checkouts_develop(self):
        """root-sync must checkout develop (not main)."""
        self.assertRegex(
            self.content,
            r'checkout develop',
            msg="root-sync must checkout develop",
        )

    def test_root_sync_ff_merges_develop(self):
        """root-sync merge must target origin/develop."""
        self.assertRegex(
            self.content,
            r"merge --ff-only origin/develop",
            msg="root-sync must merge --ff-only origin/develop",
        )

    def test_prune_zero_ahead_uses_develop(self):
        """is_branch_zero_ahead must count commits ahead of origin/develop."""
        self.assertRegex(
            self.content,
            r'origin/develop\.\.HEAD',
            msg="is_branch_zero_ahead must use 'origin/develop..HEAD' range",
        )


class TestCiChecksDevelop(unittest.TestCase):
    """ci-checks.sh CHECK 3 must scan origin/develop..HEAD, not origin/main..HEAD,
    per ADR-0070 D1 (integration branch is develop).
    """

    def setUp(self):
        self.content = _read(CI_SH)

    def test_no_fetch_origin_main_in_check3(self):
        """CHECK 3 must not fetch origin main (should be origin develop)."""
        # Verify the CHECK 3 fetch line uses develop
        check3_section = re.search(
            r'CHECK 3.*?CHECK 4',
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(check3_section, "CHECK 3 section not found in ci-checks.sh")
        section = check3_section.group(0)
        self.assertNotIn(
            "fetch origin main",
            section,
            msg="CHECK 3 must not fetch origin main; should fetch origin develop",
        )
        self.assertIn(
            "fetch origin develop",
            section,
            msg="CHECK 3 must fetch origin develop",
        )

    def test_commit_range_uses_develop(self):
        """CHECK 3 git log range must be origin/develop..HEAD."""
        self.assertIn(
            "origin/develop..HEAD",
            self.content,
            msg="ci-checks.sh CHECK 3 must scan 'origin/develop..HEAD' range",
        )
        self.assertNotIn(
            "origin/main..HEAD",
            self.content,
            msg="ci-checks.sh must not reference 'origin/main..HEAD' (migrate to develop)",
        )

    def test_adr_comment_updated(self):
        """ci-checks.sh header comment must reference ADR-0070 D1, not ADR-0041 D2,
        for the commit-range base.
        """
        self.assertIn(
            "ADR-0070 D1",
            self.content,
            msg="ci-checks.sh header comment must cite ADR-0070 D1 for develop base",
        )


class TestSessionStartDevelop(unittest.TestCase):
    """session-start.sh must fetch origin develop and report divergence vs
    origin/develop (not origin/main), per ADR-0070 D1.
    """

    def setUp(self):
        self.content = _read(SESSION_START_SH)

    def test_fetch_origin_develop(self):
        """session-start.sh must fetch origin develop."""
        self.assertIn(
            "fetch origin develop",
            self.content,
            msg="session-start.sh must fetch origin develop (not origin main)",
        )
        self.assertNotIn(
            "fetch origin main",
            self.content,
            msg="session-start.sh must not fetch origin main after two-tier migration",
        )

    def test_divergence_count_uses_develop(self):
        """Divergence count must compare HEAD against origin/develop."""
        self.assertIn(
            "HEAD..origin/develop",
            self.content,
            msg="session-start.sh divergence count must use 'HEAD..origin/develop'",
        )
        self.assertNotIn(
            "HEAD..origin/main",
            self.content,
            msg="session-start.sh must not count commits behind origin/main",
        )

    def test_context_string_says_develop(self):
        """Injected context string must say 'behind origin/develop', not 'behind origin/main'."""
        self.assertIn(
            "behind origin/develop",
            self.content,
            msg="Context string must say 'commit(s) behind origin/develop'",
        )
        self.assertNotIn(
            "behind origin/main",
            self.content,
            msg="Context string must not say 'behind origin/main' after migration",
        )

    def test_comment_updated(self):
        """Header comment must reference origin/develop divergence."""
        self.assertIn(
            "origin/develop",
            self.content,
            msg="session-start.sh header comment must mention origin/develop",
        )
        self.assertNotIn(
            "origin/main",
            self.content,
            msg="session-start.sh must have no origin/main references after migration",
        )


if __name__ == "__main__":
    unittest.main()
