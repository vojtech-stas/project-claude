"""
Regression tests for issue #1008 — Health groups show 'No data' on cold
/api/health fetch instead of 'computing…', and no fast retry while cold.

Two defects:
  (a) When /api/health returns empty/cold data the render functions display
      'No data' or 'No <group> data' — misleading because the data is still
      computing, not genuinely absent.
  (b) loadHealth() waits the full 60s auto-refresh interval before retrying
      after a cold/empty response — so the misleading 'No data' persists
      for up to 60s after a dashboard cold start.

These tests FAIL on develop before the fix and PASS after.

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_health_cold_start_1008 -v
  python -m pytest tests/test_health_cold_start_1008.py -v
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"


def _load_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _extract_function_body(content: str, fn_name: str) -> str:
    """Extract the full body of a JS function by brace-matching."""
    pattern = rf'function {re.escape(fn_name)}\s*\('
    m = re.search(pattern, content)
    if not m:
        raise AssertionError(f"function {fn_name}() not found in index.html")
    start = m.start()
    brace_pos = content.index('{', start)
    depth = 0
    i = brace_pos
    while i < len(content):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                return content[brace_pos:i + 1]
        i += 1
    raise AssertionError(f"Could not find closing brace of {fn_name}() in index.html")


def _extract_load_health_body(content: str) -> str:
    """Extract the body of the async loadHealth() function."""
    m = re.search(r'async function loadHealth\(\)', content)
    if not m:
        raise AssertionError("loadHealth() function not found in index.html")
    start = m.start()
    brace_pos = content.index('{', start)
    depth = 0
    i = brace_pos
    while i < len(content):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                return content[brace_pos:i + 1]
        i += 1
    raise AssertionError("Could not find closing brace of loadHealth() in index.html")


# ---------------------------------------------------------------------------
# (a) Render functions: empty/cold branch must use "computing" wording
# ---------------------------------------------------------------------------

class TestComputingWordingInRenderFunctions(unittest.TestCase):
    """Regression (a): each Health render function must display 'computing…'
    (or 'computing') instead of 'No data' / 'No <group> data' when its data
    is absent/empty (cold/loading state).

    Before fix: render functions use 'No data' / 'No purpose-group data' /
    'No verification-integrity data' etc. — misleading on cold start.
    After fix:  those branches show 'computing' (case-insensitive).
    """

    RENDER_FUNCTIONS = [
        "renderPurposeGroups",
        "renderDocsGrid",
        "renderAsGrid",
        "renderSubstrateGrid",
        "renderCriticHealth",
        "renderVerificationIntegrity",
        "renderRegistryIntegrity",
        "renderHygieneIntegrity",
        "renderPromotionIntegrity",
    ]

    def setUp(self):
        self.content = _load_index()

    def _get_empty_branch_text(self, fn_name: str) -> str:
        """Return the substring of the function body that handles the empty/null
        data guard (the early-return branch at the top of each render function)."""
        body = _extract_function_body(self.content, fn_name)
        # The early-return guard is typically within the first ~300 chars of
        # the function body (before the main rendering loop).
        # We look at the portion before any 'for ' or 'let html' to isolate
        # just the guard block.
        guard_end = len(body)
        for marker in ('for (', 'let html', 'const h =', 'let lastGroup'):
            idx = body.find(marker)
            if idx != -1 and idx < guard_end:
                guard_end = idx
        return body[:guard_end]

    def _assert_computing_in_guard(self, fn_name: str):
        guard_text = self._get_empty_branch_text(fn_name)
        has_computing = bool(re.search(r'computing', guard_text, re.IGNORECASE))
        self.assertTrue(
            has_computing,
            msg=(
                f"{fn_name}(): empty/cold guard does NOT contain 'computing' wording.\n"
                f"Guard text (first portion of function body):\n{guard_text!r}\n\n"
                f"Before fix: shows 'No data' / 'No <group> data' on cold start.\n"
                f"After fix:  shows 'computing…' (muted) while data is loading."
            ),
        )

    def test_renderPurposeGroups_computing_wording(self):
        self._assert_computing_in_guard("renderPurposeGroups")

    def test_renderDocsGrid_computing_wording(self):
        self._assert_computing_in_guard("renderDocsGrid")

    def test_renderAsGrid_computing_wording(self):
        self._assert_computing_in_guard("renderAsGrid")

    def test_renderSubstrateGrid_computing_wording(self):
        self._assert_computing_in_guard("renderSubstrateGrid")

    def test_renderCriticHealth_computing_wording(self):
        self._assert_computing_in_guard("renderCriticHealth")

    def test_renderVerificationIntegrity_computing_wording(self):
        self._assert_computing_in_guard("renderVerificationIntegrity")

    def test_renderRegistryIntegrity_computing_wording(self):
        self._assert_computing_in_guard("renderRegistryIntegrity")

    def test_renderHygieneIntegrity_computing_wording(self):
        self._assert_computing_in_guard("renderHygieneIntegrity")

    def test_renderPromotionIntegrity_computing_wording(self):
        self._assert_computing_in_guard("renderPromotionIntegrity")


# ---------------------------------------------------------------------------
# (b) loadHealth(): must schedule a short retry (<=5000ms) when cold/empty
# ---------------------------------------------------------------------------

class TestLoadHealthFastRetry(unittest.TestCase):
    """Regression (b): loadHealth() must schedule a short setTimeout retry
    (<=5000ms, re-invoking loadHealth) when the /api/health response is
    empty/cold/refreshing — instead of waiting the full 60s auto-refresh.

    Before fix: only the 60s setInterval auto-refresh exists; no short retry
    on empty responses — misleading 'No data' persists for up to 60s.
    After fix:  a setTimeout(<= 5000) to loadHealth is set when data is empty.
    """

    def setUp(self):
        self.content = _load_index()
        self.body = _extract_load_health_body(self.content)

    def test_load_health_has_short_settimeout_retry(self):
        """loadHealth() must contain a setTimeout(loadHealth, <=5000) call
        (or equivalent) for the cold/empty retry path.

        Before fix: only the 60s setInterval; no short-retry setTimeout.
        After fix:  a setTimeout with delay <=5000 calling loadHealth is present.
        """
        # Find all setTimeout calls in the loadHealth body.
        # Pattern: setTimeout(loadHealth, <number>) or setTimeout(function(){...loadHealth...}, <number>)
        # We look for setTimeout with a numeric delay argument.
        set_timeout_calls = re.findall(
            r'setTimeout\s*\([^,)]+,\s*(\d+)\s*\)',
            self.body,
        )
        short_retries = [int(d) for d in set_timeout_calls if int(d) <= 5000]

        self.assertTrue(
            len(short_retries) > 0,
            msg=(
                "loadHealth() does not contain a setTimeout with delay <=5000ms.\n"
                f"Found setTimeout delays: {set_timeout_calls}\n\n"
                "Before fix: only the 60s setInterval auto-refresh exists; "
                "cold/empty responses are not retried until the next auto-refresh.\n"
                "After fix: setTimeout(loadHealth, <=5000) is scheduled when "
                "the response data is empty/cold/refreshing."
            ),
        )

    def test_load_health_short_retry_references_loadhealth(self):
        """The short setTimeout in loadHealth() must call loadHealth (recursively).

        This ensures the retry re-invokes the full fetch+render cycle, not
        just a partial update.
        """
        # Look for setTimeout that includes loadHealth in its callback,
        # with a short delay (<= 5000ms).
        # Pattern: setTimeout(loadHealth, N) or setTimeout(fn, N) where fn
        # contains 'loadHealth'.
        pattern = r'setTimeout\s*\(\s*(loadHealth|\bfunction\b[^)]*\)[^{]*\{[^}]*loadHealth[^}]*\})\s*,\s*(\d+)\s*\)'
        matches = re.findall(pattern, self.body, re.DOTALL)
        short_matches = [(cb, int(d)) for cb, d in matches if int(d) <= 5000]

        # Fallback: simpler check — "setTimeout" within 200 chars of "loadHealth"
        # and a short delay somewhere in the vicinity.
        if not short_matches:
            # Try: find short setTimeout calls and check if 'loadHealth' is nearby
            for m in re.finditer(r'setTimeout\s*\([^)]{0,200},\s*(\d+)\s*\)', self.body, re.DOTALL):
                delay = int(m.group(1))
                surrounding = self.body[max(0, m.start() - 10):m.end() + 10]
                if delay <= 5000 and 'loadHealth' in self.body[max(0, m.start() - 200):m.end()]:
                    short_matches.append(('loadHealth (nearby)', delay))
                    break

        self.assertTrue(
            len(short_matches) > 0,
            msg=(
                "loadHealth() has no short setTimeout (<=5000ms) that references "
                "loadHealth in its callback.\n"
                f"loadHealth body snippet (first 800 chars):\n{self.body[:800]}\n\n"
                "After fix: setTimeout(loadHealth, <=5000) or "
                "setTimeout(function(){ loadHealth(); }, <=5000) must be present "
                "to fast-retry on cold/empty response."
            ),
        )

    def test_load_health_still_calls_api_health(self):
        """Sanity: loadHealth() still fetches /api/health (not accidentally removed)."""
        self.assertIn(
            "api/health",
            self.body,
            msg="loadHealth() must still fetch /api/health",
        )


if __name__ == "__main__":
    unittest.main()
