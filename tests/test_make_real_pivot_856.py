"""
tests/test_make_real_pivot_856.py

Regression tests for slice #856 — make-real pivot (ADR-0071).

These tests MUST FAIL before the ADR + code changes and PASS after.
Per ADR-0067 D2 (test-first discipline: test commit precedes fix commit).

Tests assert:
1. decisions/0071-make-real-pivot.md exists with required headings
   (Status, Supersedes, Extends, D1–D5 headings, Propagation section)
2. RELEASE-READY check detail string contains "dormant"
3. BRANCH-TOPOLOGY check detail string contains "dormant"

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

    def test_release_ready_detail_contains_dormant(self):
        """RELEASE-READY check detail must contain the word 'dormant'."""
        health = self._load_health()
        result = health.check_release_ready()
        detail = result.get("detail", "")
        self.assertIn(
            "dormant",
            detail.lower(),
            f"RELEASE-READY detail must contain 'dormant' per ADR-0071 D4; "
            f"got: {detail!r}",
        )

    def test_branch_topology_detail_contains_dormant(self):
        """BRANCH-TOPOLOGY check detail must contain the word 'dormant'."""
        health = self._load_health()
        result = health.check_branch_topology()
        detail = result.get("detail", "")
        self.assertIn(
            "dormant",
            detail.lower(),
            f"BRANCH-TOPOLOGY detail must contain 'dormant' per ADR-0071 D4; "
            f"got: {detail!r}",
        )

    def test_release_ready_id_correct(self):
        """RELEASE-READY check must return the correct id field."""
        health = self._load_health()
        result = health.check_release_ready()
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
