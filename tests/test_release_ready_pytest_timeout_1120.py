"""
tests/test_release_ready_pytest_timeout_1120.py

Regression test for issue #1120 — RELEASE-READY pytest subprocess timeout
too short (120s) causes condition (b) to false-fail now that the full suite
takes ~149s (726 passed in 148.65s at develop head 5429afe — the suite is
green; the budget is the defect).

This is an incomplete-class-revision of #981 (rule #19): #981 raised the
sibling ci-checks.sh sub-call in check_release_ready() condition (a) to a
named module constant (_RELEASE_READY_CICHECKS_TIMEOUT_S) but did not sweep
the sibling pytest sub-call in condition (b), which kept its 120s inline
hard-code and was subsequently outrun by the growing suite (909+ tests).

Per ADR-0067 D2/D3: this test is committed BEFORE the fix commit and must
FAIL on the pre-fix code (where _RELEASE_READY_PYTEST_TIMEOUT_S does not
exist, and the inline hard-code is 120), and PASS after the fix raises the
constant to >=200.

Test target: dashboard/health.py module-level constant
  _RELEASE_READY_PYTEST_TIMEOUT_S

Assertion: the constant must be >= 200 to comfortably accommodate the
suite's real ~149s runtime plus headroom for transient slowness and further
suite growth.
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


class TestPytestTimeoutConstant(unittest.TestCase):
    """_RELEASE_READY_PYTEST_TIMEOUT_S must exist and be >= 200.

    Root cause (issue #1120): the RELEASE-READY condition (b) subprocess call
    to `pytest tests/` used a hard-coded 120s timeout. The suite now takes
    ~149s (726 passed in 148.65s at develop head 5429afe) as it has grown
    past 900+ tests. This caused systematic false-fail of condition (b),
    holding the RELEASE-READY gate — and thus blocking promote.sh — even
    though the suite was genuinely green.

    Fix: refactor the timeout to a named module constant set to >=200s so
    that (a) the value is testable, and (b) the real ~149s pytest run
    completes within the allotted time with headroom for further growth
    and transient slowness.
    """

    def _load_health(self):
        """Import (or reload) the health module from dashboard/."""
        import health as _h
        importlib.reload(_h)
        return _h

    def test_constant_exists(self):
        """_RELEASE_READY_PYTEST_TIMEOUT_S must be defined at module level."""
        h = self._load_health()
        self.assertTrue(
            hasattr(h, "_RELEASE_READY_PYTEST_TIMEOUT_S"),
            "_RELEASE_READY_PYTEST_TIMEOUT_S must be defined in "
            "dashboard/health.py (issue #1120: the 120s hard-coded timeout "
            "causes condition (b) to false-fail since the suite now takes "
            "~149s)",
        )

    def test_constant_is_at_least_200(self):
        """_RELEASE_READY_PYTEST_TIMEOUT_S must be >= 200 seconds.

        The suite runs ~149s on develop. The constant must provide
        meaningful headroom (>=200s) to survive transient slowness and
        further suite growth without timing out a legitimately-green run.
        """
        h = self._load_health()
        if not hasattr(h, "_RELEASE_READY_PYTEST_TIMEOUT_S"):
            self.fail(
                "_RELEASE_READY_PYTEST_TIMEOUT_S not found in health.py — "
                "fix #1120 must add this constant (was hard-coded 120s inline)"
            )
        val = h._RELEASE_READY_PYTEST_TIMEOUT_S
        self.assertGreaterEqual(
            val, 200,
            f"_RELEASE_READY_PYTEST_TIMEOUT_S must be >= 200 to accommodate "
            f"the suite's real ~149s runtime plus headroom; got {val!r} "
            f"(issue #1120: previous value 120 caused systematic false-fail "
            f"of condition (b) → RELEASE-READY gate held → no promotions "
            f"possible even though the suite was genuinely green)",
        )

    def test_constant_is_used_in_pytest_subprocess_call(self):
        """health.py source must reference _RELEASE_READY_PYTEST_TIMEOUT_S in
        the subprocess.run call for the pytest sub-call (not a dead constant).
        """
        health_src = (REPO_ROOT / "dashboard" / "health.py").read_text(encoding="utf-8")
        # The constant name must appear at least twice: definition + use in subprocess.run.
        count = health_src.count("_RELEASE_READY_PYTEST_TIMEOUT_S")
        self.assertGreaterEqual(
            count, 2,
            f"_RELEASE_READY_PYTEST_TIMEOUT_S must appear at least twice in "
            f"health.py (once defined, once used in subprocess.run timeout= "
            f"arg); found {count} occurrence(s). A dead constant does not "
            f"fix #1120.",
        )


if __name__ == "__main__":
    unittest.main()
