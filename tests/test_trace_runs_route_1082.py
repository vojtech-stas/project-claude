"""
tests/test_trace_runs_route_1082.py

Structural wiring regressions for slice #1082 (PRD #1075 criterion 9 — the
Firing tab's dashboard repoint) + ADR-0080 D1 (the recorded panel's
relocation into the Run-board and the reconstructed cross-check panel's
deletion). Mirrors the existing test_prd_firing_871.py "server_route_present"
AST/import-only pattern (no live server bind, per isolation rules): asserts
server.py wires the /api/trace-runs route and index.html renders the
recorded panel (relocated into tab-runboard, the dashboard's only tab) with
the honest pre-v3 empty-state text — and that the gh-derived reconstructed
panel, superseded by ADR-0080 D1, is actually gone (not merely demoted).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_trace_runs_route_1082.py -v
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
SERVER_PY = DASHBOARD_DIR / "server.py"
INDEX_HTML = DASHBOARD_DIR / "index.html"


class TestServerRoutePresent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_src = SERVER_PY.read_text(encoding="utf-8", errors="replace")

    def test_trace_runs_route_handler_present(self):
        self.assertIn(
            '"/api/trace-runs"', self.server_src,
            "server.py must wire a /api/trace-runs route handler (slice #1082)",
        )

    def test_tracestore_module_imported(self):
        self.assertIn(
            "import tracestore", self.server_src,
            "server.py must import tracestore for the /api/trace-runs route",
        )

    def test_route_calls_serve_trace_runs(self):
        self.assertIn(
            "serve_trace_runs", self.server_src,
            "server.py's /api/trace-runs route must call tracestore.serve_trace_runs()"
            " (non-blocking, mirrors /api/prd-firing's house pattern)",
        )

    def test_docstring_mentions_route(self):
        self.assertIn(
            "/api/trace-runs", self.server_src,
            "server.py's module docstring should advertise /api/trace-runs",
        )


class TestIndexHtmlRendersRecordedPanel(unittest.TestCase):
    """The recorded (primary) panel, relocated into the Run-board tab.

    ADR-0080 D1 supersedes ADR-0075 D6's "never delete the gh-reconstructed
    layer" clause: the reconstructed cross-check panel (formerly tested here
    as TestIndexHtmlRendersBothPanels) IS deleted — the RECORD-VS-GH
    reconciler + a new HOSTED-CI-REAL CI check are its mechanized
    replacement (CLAUDE.md rule #19: revise the whole flagged class, not
    just the instance — this file's cross-check-panel-presence assertions
    are inverted below, not merely deleted, to actively guard against
    resurrection).
    """

    @classmethod
    def setUpClass(cls):
        cls.html_src = INDEX_HTML.read_text(encoding="utf-8", errors="replace")

    def test_fetches_trace_runs_endpoint(self):
        self.assertIn(
            "/api/trace-runs", self.html_src,
            "index.html must fetch /api/trace-runs for the recorded panel",
        )

    def test_honest_empty_state_for_pre_v3_prs(self):
        self.assertIn(
            "no recorded trace",
            self.html_src,
            "index.html must render an honest empty-state for pre-v3 PRs "
            '("no recorded trace — pre-v3")',
        )
        self.assertIn("pre-v3", self.html_src)

    def test_recorded_panel_render_function_present(self):
        self.assertIn("renderTraceRuns", self.html_src)
        self.assertIn("fetchTraceRuns", self.html_src)

    def test_recorded_panel_lives_in_runboard_tab(self):
        """The relocated panel's content div sits inside tab-runboard, the
        dashboard's only tab (ADR-0080 D1), before the <script> block."""
        rb_idx = self.html_src.find('id="tab-runboard"')
        trace_idx = self.html_src.find('id="trace-runs-content"')
        script_idx = self.html_src.find('<script>')
        self.assertGreater(rb_idx, -1, "tab-runboard div not found")
        self.assertGreater(trace_idx, rb_idx,
                            "trace-runs-content must appear after tab-runboard opens")
        self.assertLess(trace_idx, script_idx,
                         "trace-runs-content must be markup, not inside <script>")

    def test_reconstructed_panel_deleted(self):
        """The gh-derived cross-check panel is DELETED, not merely demoted
        (ADR-0080 D1 supersedes ADR-0075 D6's never-delete clause)."""
        self.assertNotIn("renderFiring", self.html_src)
        self.assertNotIn("fetchFiring", self.html_src)
        self.assertNotIn('id="firing-content"', self.html_src)
        self.assertNotIn('id="firing-cross-check-label"', self.html_src)
        self.assertNotIn("reconstructed (cross-check)", self.html_src)

    def test_race_fix_bookkeeping_removed_with_reconstructed_panel(self):
        """The #1082 review-round-1 race-fix bookkeeping (_recordedRunsLoaded,
        _recordedRunsCapped, the shared #firing-limit-input picker) existed
        solely to support the now-deleted reconstructed panel's cross-check
        annotation — it is dead code alongside its only consumer. (The DOM
        element itself is gone; a historical explanatory code comment may
        still name it in prose — that's not the DOM element.)"""
        self.assertNotIn("_recordedRunsLoaded", self.html_src)
        self.assertNotIn("_recordedRunsCapped", self.html_src)
        self.assertNotIn("_firingSharedLimit", self.html_src)
        self.assertNotIn('id="firing-limit-input"', self.html_src)

    def test_fetch_uses_fixed_limit(self):
        """fetchTraceRuns() now uses a fixed limit constant — the shared
        picker input it used to read died with the reconstructed panel."""
        self.assertIn("_TRACE_RUNS_LIMIT", self.html_src)


if __name__ == "__main__":
    unittest.main()
