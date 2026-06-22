"""
tests/test_release_ready_timeout_981.py

Regression test for issue #981 — RELEASE-READY ci-checks subprocess timeout
too short (60s) causes condition (a) to false-fail when ci-checks takes ~95s.

Per ADR-0067 D2/D3: this test is committed BEFORE the fix commit and must
FAIL on the pre-fix code (where _RELEASE_READY_CICHECKS_TIMEOUT_S does not
exist or is 60), and PASS after the fix raises the constant to >=180.

Test target: dashboard/health.py module-level constant
  _RELEASE_READY_CICHECKS_TIMEOUT_S

Assertion: the constant must be >= 180 to comfortably accommodate ci-checks'
real ~95s runtime plus adequate headroom for transient gh-API latency.
"""

import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Ensure dashboard/ is importable.
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


class TestCiChecksTimeoutConstant(unittest.TestCase):
    """_RELEASE_READY_CICHECKS_TIMEOUT_S must exist and be >= 180.

    Root cause (issue #981): the RELEASE-READY condition (a) subprocess call to
    tools/ci-checks.sh used a hard-coded 60s timeout. ci-checks.sh now takes
    ~95s due to gh-dependent checks (CHECK 19, etc.). This caused systematic
    false-fail of condition (a), blocking all promote.sh promotions even when
    CI was genuinely green.

    Fix: refactor the timeout to a named module constant set to >=180s so that
    (a) the value is testable, and (b) ci-checks can complete within the allotted
    time even under transient gh-API latency.
    """

    def _load_health(self):
        """Import (or reload) the health module from dashboard/."""
        import health as _h
        importlib.reload(_h)
        return _h

    def test_constant_exists(self):
        """_RELEASE_READY_CICHECKS_TIMEOUT_S must be defined at module level."""
        h = self._load_health()
        self.assertTrue(
            hasattr(h, "_RELEASE_READY_CICHECKS_TIMEOUT_S"),
            "_RELEASE_READY_CICHECKS_TIMEOUT_S must be defined in dashboard/health.py "
            "(issue #981: the 60s hard-coded timeout causes condition (a) to false-fail "
            "since ci-checks.sh now takes ~95s)",
        )

    def test_constant_is_at_least_180(self):
        """_RELEASE_READY_CICHECKS_TIMEOUT_S must be >= 180 seconds.

        ci-checks.sh runs ~95s on develop. The constant must provide at least
        ~2x headroom (180s) to survive transient gh-API latency without timing
        out legitimately-green CI runs.
        """
        h = self._load_health()
        if not hasattr(h, "_RELEASE_READY_CICHECKS_TIMEOUT_S"):
            self.fail(
                "_RELEASE_READY_CICHECKS_TIMEOUT_S not found in health.py — "
                "fix #981 must add this constant (was hard-coded 60s inline)"
            )
        val = h._RELEASE_READY_CICHECKS_TIMEOUT_S
        self.assertGreaterEqual(
            val, 180,
            f"_RELEASE_READY_CICHECKS_TIMEOUT_S must be >= 180 to accommodate "
            f"ci-checks.sh's ~95s runtime plus headroom; got {val!r} "
            f"(issue #981: previous value 60 caused systematic false-fail of "
            f"condition (a) → RELEASE-READY gate held → no promotions possible)",
        )

    def test_constant_is_used_in_ci_subprocess_call(self):
        """health.py source must reference _RELEASE_READY_CICHECKS_TIMEOUT_S in
        the subprocess.run call for ci-checks.sh (not a dead constant).
        """
        health_src = (REPO_ROOT / "dashboard" / "health.py").read_text(encoding="utf-8")
        # The constant name must appear at least twice: definition + use in subprocess.run.
        count = health_src.count("_RELEASE_READY_CICHECKS_TIMEOUT_S")
        self.assertGreaterEqual(
            count, 2,
            f"_RELEASE_READY_CICHECKS_TIMEOUT_S must appear at least twice in "
            f"health.py (once defined, once used in subprocess.run timeout= arg); "
            f"found {count} occurrence(s). A dead constant does not fix #981.",
        )


if __name__ == "__main__":
    unittest.main()
