"""
tests/test_dead_routes_removed_729.py

Regression tests for issue #729: dead /api/dora + /api/workitems cleanup.

Per ADR-0067 D2 + D3 (regression rider): this test file is committed BEFORE
the fix commit so it fails on the pre-fix codebase.  After the fix it passes.

Asserts:
  (a) dashboard/server.py no longer advertises /api/dora (no route handler,
      no stale docstring mention).
  (b) dashboard/server.py no longer advertises /api/workitems (no route handler,
      no stale docstring mention).
  (c) /api/runs route handler IS present in server.py (must be kept).
  (d) fetch_workitems can be imported from workitems.py (function kept,
      only the route is dead).
  (e) dashboard/README.md does not list /api/workitems in its API table.

Tests (a-b) FAIL before the fix; tests (c-d-e) verify invariants that
must hold both before AND after the fix.
"""

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DASHBOARD_DIR = _REPO_ROOT / "dashboard"
if str(_DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_DIR))


class TestDeadRoutesRemoved(unittest.TestCase):
    """Dead /api/dora + /api/workitems surface must be fully removed."""

    @classmethod
    def setUpClass(cls):
        cls.server_src = (_REPO_ROOT / "dashboard" / "server.py").read_text(
            encoding="utf-8", errors="replace"
        )
        cls.readme_src = (_REPO_ROOT / "dashboard" / "README.md").read_text(
            encoding="utf-8", errors="replace"
        )

    # ------------------------------------------------------------------
    # (a) /api/dora — fully absent
    # ------------------------------------------------------------------

    def test_dora_no_route_handler(self):
        """server.py must not contain a path == "/api/dora" route handler."""
        self.assertNotIn(
            '"/api/dora"',
            self.server_src,
            "server.py must not contain a /api/dora route handler (issue #729)",
        )

    def test_dora_no_stale_docstring(self):
        """server.py module docstring must not reference /api/dora at all."""
        self.assertNotIn(
            "api/dora",
            self.server_src,
            "server.py must not mention api/dora (dead route, stale docstring to remove — issue #729)",
        )

    # ------------------------------------------------------------------
    # (b) /api/workitems — route surface removed
    # ------------------------------------------------------------------

    def test_workitems_no_route_handler(self):
        """server.py must not contain a path == "/api/workitems" route handler."""
        self.assertNotIn(
            '"/api/workitems"',
            self.server_src,
            "server.py must not contain a /api/workitems route handler (issue #729)",
        )

    def test_workitems_no_stale_docstring(self):
        """server.py module docstring must not advertise GET /api/workitems."""
        # The docstring line starts with whitespace + "GET /api/workitems"
        self.assertNotIn(
            "GET /api/workitems",
            self.server_src,
            "server.py docstring must not advertise GET /api/workitems (dead route — issue #729)",
        )

    def test_workitems_not_in_readme_api_table(self):
        """dashboard/README.md API table must not list /api/workitems."""
        self.assertNotIn(
            "/api/workitems",
            self.readme_src,
            "dashboard/README.md must not list /api/workitems in API reference (issue #729)",
        )

    # ------------------------------------------------------------------
    # (c) /api/runs — must remain
    # ------------------------------------------------------------------

    def test_runs_route_handler_present(self):
        """server.py must still contain the /api/runs route handler."""
        self.assertIn(
            '"/api/runs"',
            self.server_src,
            "server.py must keep the /api/runs route handler (used by Recent sessions panel)",
        )

    # ------------------------------------------------------------------
    # (d) fetch_workitems() — function must be importable (server-side use)
    # ------------------------------------------------------------------

    def test_fetch_workitems_importable(self):
        """workitems.fetch_workitems() must still be importable (used by /api/status)."""
        try:
            import importlib
            wm = importlib.import_module("workitems")
            self.assertTrue(
                callable(getattr(wm, "fetch_workitems", None)),
                "fetch_workitems must be a callable in workitems.py",
            )
        except ImportError as exc:
            self.fail(f"workitems module must be importable: {exc}")


if __name__ == "__main__":
    unittest.main()
