"""
tests/test_trace_runs_route_1082.py

Structural wiring regressions for slice #1082 (PRD #1075 criterion 9 — the
Firing tab's dashboard repoint). Mirrors the existing test_prd_firing_871.py
"server_route_present" AST/import-only pattern (no live server bind, per
isolation rules): asserts server.py wires the /api/trace-runs route and
index.html renders BOTH the recorded (primary) panel and the demoted
reconstructed (cross-check) panel with a DOM-greppable marker + the honest
pre-v3 empty-state text.

Test-first discipline: this commit lands BEFORE the server.py route /
index.html rendering exist. FAILS before impl (grep assertions on absent
strings); PASSES once the next commit wires both.

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


class TestIndexHtmlRendersBothPanels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_src = INDEX_HTML.read_text(encoding="utf-8", errors="replace")

    def test_fetches_trace_runs_endpoint(self):
        self.assertIn(
            "/api/trace-runs", self.html_src,
            "index.html must fetch /api/trace-runs for the recorded (primary) panel",
        )

    def test_cross_check_label_dom_marker_present(self):
        """DOM-greppable marker for the demoted reconstructed layer — never
        delete the gh-derived rendering, only relabel it."""
        self.assertIn(
            'id="firing-cross-check-label"', self.html_src,
            "index.html must carry a DOM-greppable cross-check label marker",
        )
        self.assertIn(
            "reconstructed (cross-check)", self.html_src,
            "the demoted gh-derived panel must be relabeled "
            '"reconstructed (cross-check)" — demote, never delete',
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

    def test_reconstructed_panel_still_present_not_deleted(self):
        """The existing gh-derived rendering must remain — demoted, never
        deleted (per the slice's explicit instruction)."""
        self.assertIn("renderFiring", self.html_src)
        self.assertIn("fetchFiring", self.html_src)
        self.assertIn('id="firing-content"', self.html_src)

    def test_cross_check_annotation_gated_on_recorded_load(self):
        """Live QA (headless Playwright against real PRs 1095-1105) caught a
        race: the recorded and reconstructed panels fetch independently, and
        when gh_cache is already warm, the reconstructed panel can paint
        BEFORE the recorded fetch resolves — a PR that IS recorded would
        then show a false "no recorded trace" annotation. The annotation
        must be gated on a loaded-flag so it never renders on an in-flight
        (not-yet-resolved) recorded fetch."""
        self.assertIn("_recordedRunsLoaded", self.html_src)


if __name__ == "__main__":
    unittest.main()
