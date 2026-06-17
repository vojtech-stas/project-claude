"""
tests/test_make_real_pivot_856.py

Regression tests for slice #856 — make-real pivot (ADR-0071).

These tests MUST FAIL before the ADR + code changes and PASS after.
Per ADR-0067 D2 (test-first discipline: test commit precedes fix commit).

Tests assert:
1. decisions/0071-make-real-pivot.md exists with required headings
   (Status, Supersedes, Extends, D1–D5 headings, Propagation section)
2. RELEASE-READY check detail string does NOT contain "dormant" (wired by slice #838)
3. BRANCH-TOPOLOGY check detail string does NOT contain "dormant" (wired by slice #843)

All assertions are offline / headless (no network required).
Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_make_real_pivot_856.py -v
"""

import importlib
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DASHBOARD_DIR = _REPO_ROOT / "dashboard"

# Ensure dashboard/ is importable
if str(_DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_DIR))

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

ADR_0071 = _REPO_ROOT / "decisions" / "0071-make-real-pivot.md"


def _adr_text() -> str:
    return ADR_0071.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ADR-0071 file structure tests
# ---------------------------------------------------------------------------


class TestADR0071Exists(unittest.TestCase):
    """ADR-0071 must exist and contain the required top-level structure."""

    def test_file_exists(self):
        """decisions/0071-make-real-pivot.md must exist."""
        self.assertTrue(
            ADR_0071.exists(),
            "decisions/0071-make-real-pivot.md must be created (slice #856 deliverable 1).",
        )

    def test_status_accepted(self):
        """ADR-0071 must have Status: Accepted."""
        text = _adr_text()
        self.assertIn(
            "Status:",
            text,
            "ADR-0071 must have a Status: line.",
        )
        self.assertIn(
            "Accepted",
            text,
            "ADR-0071 Status must be Accepted.",
        )

    def test_supersedes_header(self):
        """ADR-0071 must have a Supersedes header."""
        text = _adr_text()
        self.assertIn(
            "Supersedes",
            text,
            "ADR-0071 must carry a Supersedes header.",
        )

    def test_extends_header(self):
        """ADR-0071 must have an Extends header."""
        text = _adr_text()
        self.assertIn(
            "Extends",
            text,
            "ADR-0071 must carry an Extends header.",
        )

    def test_d1_heading(self):
        """ADR-0071 must have a ### D1 heading."""
        text = _adr_text()
        self.assertIn(
            "### D1",
            text,
            "ADR-0071 must contain a '### D1' decision heading.",
        )

    def test_d2_heading(self):
        """ADR-0071 must have a ### D2 heading."""
        text = _adr_text()
        self.assertIn(
            "### D2",
            text,
            "ADR-0071 must contain a '### D2' decision heading.",
        )

    def test_d3_heading(self):
        """ADR-0071 must have a ### D3 heading."""
        text = _adr_text()
        self.assertIn(
            "### D3",
            text,
            "ADR-0071 must contain a '### D3' decision heading.",
        )

    def test_d4_heading(self):
        """ADR-0071 must have a ### D4 heading."""
        text = _adr_text()
        self.assertIn(
            "### D4",
            text,
            "ADR-0071 must contain a '### D4' decision heading.",
        )

    def test_d5_heading(self):
        """ADR-0071 must have a ### D5 heading."""
        text = _adr_text()
        self.assertIn(
            "### D5",
            text,
            "ADR-0071 must contain a '### D5' decision heading.",
        )

    def test_propagation_section(self):
        """ADR-0071 must have a ## Propagation section."""
        text = _adr_text()
        self.assertIn(
            "## Propagation",
            text,
            "ADR-0071 must contain a '## Propagation' section "
            "(required by ADR-0064 D1 / AC-PROPAGATION).",
        )

    def test_consequences_section(self):
        """ADR-0071 must have a ## Consequences section."""
        text = _adr_text()
        self.assertIn(
            "## Consequences",
            text,
            "ADR-0071 must contain a '## Consequences' section.",
        )

    def test_alternatives_section(self):
        """ADR-0071 must have an ## Alternatives considered section."""
        text = _adr_text()
        self.assertIn(
            "## Alternatives considered",
            text,
            "ADR-0071 must contain an '## Alternatives considered' section.",
        )


# ---------------------------------------------------------------------------
# health.py check detail-string tests
# ---------------------------------------------------------------------------


class TestDormantDetailStrings(unittest.TestCase):
    """RELEASE-READY and BRANCH-TOPOLOGY detail strings must say 'dormant'."""

    def _load_health(self):
        """Reload health module to pick up current code state."""
        import health
        importlib.reload(health)
        return health

    def test_release_ready_detail_not_dormant(self):
        """RELEASE-READY check detail must NOT contain 'dormant' — slice #838 wired
        the six-condition gate (ADR-0070 D2), superseding the dormant period.

        ADR-0071 D4 marked RELEASE-READY dormant while develop was absent.
        Develop now exists and the gate is operational per slice #838.

        Uses env-var injection to avoid real CI/pytest/gh calls (fast test).
        """
        import os
        # Fast-path injection: bypass real CI/test/gh subprocesses.
        env_patch = {
            "_RELEASE_READY_CI_RESULT": "PASS",
            "_RELEASE_READY_TESTS_RESULT": "PASS",
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
            "_RELEASE_READY_STREAK_RESULT": "PASS",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        }
        old_vals = {}
        for k, v in env_patch.items():
            old_vals[k] = os.environ.get(k)
            os.environ[k] = v
        try:
            health = self._load_health()
            result = health.check_release_ready()
        finally:
            for k, old_v in old_vals.items():
                if old_v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = old_v
        detail = result.get("detail", "")
        self.assertNotIn(
            "dormant",
            detail.lower(),
            f"RELEASE-READY detail must not say 'dormant' — slice #838 wired the gate; "
            f"got: {detail!r}",
        )

    def test_branch_topology_detail_not_dormant(self):
        """BRANCH-TOPOLOGY check detail must NOT contain 'dormant' — slice #843 wired real check.

        Slice #843 replaced the ADR-0071 D4 stub with a real implementation that
        reports the actual develop/main relationship.  The detail must mention real
        topology data (develop sha, main sha, ahead/behind counts) rather than 'dormant'.
        """
        health = self._load_health()
        result = health.check_branch_topology()
        detail = result.get("detail", "")
        self.assertNotIn(
            "dormant",
            detail.lower(),
            f"BRANCH-TOPOLOGY detail must not say 'dormant' — slice #843 wired the real check; "
            f"got: {detail!r}",
        )
        # Must report real topology: id correct, result is a known verdict
        self.assertIn(
            result.get("result"),
            ("PASS", "WARN", "FAIL"),
            f"BRANCH-TOPOLOGY result must be PASS/WARN/FAIL; got: {result.get('result')!r}",
        )

    def test_release_ready_id_correct(self):
        """RELEASE-READY check must return the correct id field."""
        import os
        # Fast-path injection to avoid real subprocesses.
        env_patch = {
            "_RELEASE_READY_CI_RESULT": "PASS",
            "_RELEASE_READY_TESTS_RESULT": "PASS",
            "_RELEASE_READY_PROOF_INTEGRITY_RESULT": "PASS",
            "_RELEASE_READY_STREAK_RESULT": "PASS",
            "_RELEASE_READY_NEEDS_HUMAN_COUNT": "0",
        }
        old_vals = {}
        for k, v in env_patch.items():
            old_vals[k] = os.environ.get(k)
            os.environ[k] = v
        try:
            health = self._load_health()
            result = health.check_release_ready()
        finally:
            for k, old_v in old_vals.items():
                if old_v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = old_v
        self.assertEqual(
            result.get("id"),
            "RELEASE-READY",
            "check_release_ready() must return id='RELEASE-READY'.",
        )

    def test_branch_topology_id_correct(self):
        """BRANCH-TOPOLOGY check must return the correct id field."""
        health = self._load_health()
        result = health.check_branch_topology()
        self.assertEqual(
            result.get("id"),
            "BRANCH-TOPOLOGY",
            "check_branch_topology() must return id='BRANCH-TOPOLOGY'.",
        )


if __name__ == "__main__":
    unittest.main()
