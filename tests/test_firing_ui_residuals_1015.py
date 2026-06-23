"""
Regression tests for issue #1015 — two firing-UI residuals:

(a) Firing tab cold-state: fetchFiring()/renderFiring() shows 'No PR data
    available' when /api/prd-firing returns {status:'computing'} on cold
    cache start, instead of showing 'computing…' and scheduling a retry.

(b) Session-firing tree prd_number: the Live-tab session-firing tree labels
    every group header as 'PRD #N' regardless of whether #N is an actual PRD.
    The render must reference prd_n (the resolved PRD number stored in each
    nested_groups node) to decide labelling — non-PRD dispatches without a
    resolved PRD should go into a non-PRD maintenance bucket.

These tests FAIL on develop before the fix and PASS after.

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_firing_ui_residuals_1015 -v
  python -m pytest tests/test_firing_ui_residuals_1015.py -v
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"


def _load_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _extract_function_body(content: str, fn_name: str) -> str:
    """Extract the full body of a named JS function by brace-matching."""
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


def _extract_async_function_body(content: str, fn_name: str) -> str:
    """Extract the full body of a named async JS function by brace-matching."""
    pattern = rf'async function {re.escape(fn_name)}\s*\('
    m = re.search(pattern, content)
    if not m:
        # Fall back to non-async
        return _extract_function_body(content, fn_name)
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
    raise AssertionError(
        f"Could not find closing brace of async {fn_name}() in index.html"
    )


# ---------------------------------------------------------------------------
# (a) Firing tab: renderFiring() must handle status='computing'
# ---------------------------------------------------------------------------

class TestRenderFiringComputingState(unittest.TestCase):
    """Regression (a): renderFiring() must detect data.status === 'computing'
    and show 'computing…' + schedule a retry, NOT show 'No PR data available'.

    Before fix: renderFiring() checks prs.length === 0 and immediately shows
      'No PR data available (gh may be unavailable or no PRs found)' —
      misleading when /api/prd-firing returns {status:'computing'} on cold start.
    After fix:  renderFiring() (or fetchFiring()) checks for status==='computing'
      first; shows 'computing…' and schedules a short retry (like the #1008
      Health fix).  'No PR data available' is only shown for a genuine empty list
      (warm cache + 0 PRs, no computing status).
    """

    def setUp(self):
        self.content = _load_index()

    def test_renderFiring_checks_computing_status(self):
        """renderFiring() must reference 'computing' when data.status indicates it.

        Before fix: only checks prs.length === 0, shows 'No PR data available'.
        After fix:  checks data.status (or result.status) for 'computing' and
          branches to show 'computing…' wording instead.
        """
        body = _extract_function_body(self.content, "renderFiring")

        # Must contain a reference to 'computing' status check
        has_computing_check = bool(
            re.search(r"computing", body, re.IGNORECASE)
        )
        self.assertTrue(
            has_computing_check,
            msg=(
                "renderFiring(): no 'computing' status check found.\n\n"
                "Before fix: only checks prs.length === 0 → shows "
                "'No PR data available' even when status='computing'.\n"
                "After fix:  detects status==='computing' (or absent prs + "
                "computing marker) and shows 'computing…' wording.\n\n"
                f"Function body (first 600 chars):\n{body[:600]}"
            ),
        )

    def test_renderFiring_computing_not_solely_no_pr_data(self):
        """The empty-prs branch must NOT unconditionally show 'No PR data available'.

        Before fix: prs.length === 0 → always 'No PR data available'.
        After fix:  prs.length === 0 with status='computing' → 'computing…';
          prs.length === 0 without computing → 'No PR data available' (genuine empty).
        """
        body = _extract_function_body(self.content, "renderFiring")

        # Locate the 'No PR data available' string
        no_pr_idx = body.find("No PR data available")
        self.assertGreater(
            no_pr_idx, -1,
            msg=(
                "renderFiring(): 'No PR data available' message not found — "
                "it should still exist for the genuine-empty case, just not "
                "shown when status='computing'."
            ),
        )

        # There must be a data.status (or result.status) check BEFORE the
        # 'No PR data' branch.  We require 'data.status' (not just 'statusEl'
        # which is an element reference, not a status field check) to appear
        # before the 'No PR data available' message, indicating the branch is
        # guarded by the computing check.
        before_no_pr = body[:no_pr_idx]
        computing_before = bool(re.search(r"computing", before_no_pr, re.IGNORECASE))
        data_status_before = bool(re.search(r"data\.status|result\.status", before_no_pr))

        self.assertTrue(
            computing_before or data_status_before,
            msg=(
                "renderFiring(): 'No PR data available' is shown without any "
                "prior check for data.status === 'computing'.\n\n"
                "Before fix: prs.length === 0 unconditionally shows the message "
                "(no data.status check).\n"
                "After fix:  data.status is checked before prs.length; when "
                "status='computing' the computing branch fires first, leaving "
                "'No PR data available' only for genuine empty (warm + 0 PRs).\n\n"
                f"Body before 'No PR data available' (last 300 chars):\n"
                f"{before_no_pr[-300:]!r}"
            ),
        )

    def test_fetchFiring_schedules_retry_on_computing(self):
        """fetchFiring() or renderFiring() must schedule a short retry when computing.

        Before fix: no retry on computing state from /api/prd-firing —
          the 30s auto-refresh is the only refresh, so 'computing…' could
          persist up to 30s unnecessarily.
        After fix:  a setTimeout (<= 5000ms) to fetchFiring is scheduled
          when the response indicates status='computing'.
        """
        # Search the region around renderFiring + fetchFiring for a short setTimeout
        # that fires fetchFiring when computing.
        render_body = _extract_function_body(self.content, "renderFiring")
        fetch_body = _extract_function_body(self.content, "fetchFiring")
        combined = render_body + fetch_body

        # Look for setTimeout with a short delay (<= 5000ms) near fetchFiring
        short_timeouts = re.findall(
            r'setTimeout\s*\([^,)]+,\s*(\d+)\s*\)',
            combined,
        )
        short_with_fetch = []
        for m in re.finditer(r'setTimeout\s*\(([^)]{0,200}),\s*(\d+)\s*\)', combined, re.DOTALL):
            cb, delay_str = m.group(1), m.group(2)
            delay = int(delay_str)
            if delay <= 5000 and "fetchFiring" in cb:
                short_with_fetch.append(delay)

        # Fallback: find any short setTimeout near 'computing' keyword in combined
        if not short_with_fetch:
            for m in re.finditer(r'setTimeout\s*\([^)]{0,200},\s*(\d+)\s*\)', combined, re.DOTALL):
                delay = int(m.group(1))
                if delay <= 5000:
                    # Check if fetchFiring appears nearby (within 300 chars before/after)
                    surrounding = combined[max(0, m.start() - 300): m.end() + 300]
                    if "fetchFiring" in surrounding or "computing" in surrounding:
                        short_with_fetch.append(delay)

        self.assertTrue(
            len(short_with_fetch) > 0,
            msg=(
                "fetchFiring()/renderFiring(): no short setTimeout (<=5000ms) "
                "referencing fetchFiring found near computing handling.\n\n"
                "Before fix: only the 30s setInterval auto-refresh; computing "
                "state is not retried promptly.\n"
                "After fix:  setTimeout(fetchFiring, N<=5000) is scheduled "
                "when status='computing' to retry promptly.\n\n"
                f"Found setTimeout delays in combined body: {short_timeouts}"
            ),
        )


# ---------------------------------------------------------------------------
# (b) Session-firing tree: must use prd_n to distinguish PRD vs non-PRD nodes
# ---------------------------------------------------------------------------

class TestSessionFiringTreePrdNumber(unittest.TestCase):
    """Regression (b): the fetchSessionFiring() render must use prd_n
    (the resolved PRD number from each nested_groups node) to decide
    whether to label a group header as 'PRD #N'.

    Before fix: all nestedGroups keys are rendered identically with
      _renderNestedPrdNode(lbl, ...) — even 'PRD #727' for a captured
      issue (phantom PRD node).  Non-PRD dispatches appear as phantom
      'PRD #N (direct / unresolved)' nodes with 0 slices.
    After fix:  the render checks prd_n (or an equivalent field) to
      determine if a node is a genuine PRD; nodes without a valid PRD
      number are grouped under a 'maintenance / non-PRD' bucket (or
      equivalent label) rather than rendered as phantom 'PRD #N' nodes.
    """

    def setUp(self):
        self.content = _load_index()

    def _get_fetch_session_firing_body(self) -> str:
        return _extract_async_function_body(self.content, "fetchSessionFiring")

    def test_fetchSessionFiring_references_prd_n(self):
        """fetchSessionFiring() must reference prd_n (or prd_number) when
        deciding how to label/bucket nested_groups nodes.

        Before fix: all nodes go through _renderNestedPrdNode unconditionally;
          no check on prd_n.
        After fix:  prd_n (or equivalent) is read from the node data to
          differentiate PRD nodes from non-PRD nodes.
        """
        body = self._get_fetch_session_firing_body()

        has_prd_n_ref = bool(
            re.search(r'\bprd_n\b', body)
        )
        self.assertTrue(
            has_prd_n_ref,
            msg=(
                "fetchSessionFiring(): no reference to 'prd_n' found.\n\n"
                "Before fix: all nestedGroups nodes are rendered as PRD nodes "
                "unconditionally — phantom 'PRD #727' for captured issues.\n"
                "After fix:  prd_n is checked to distinguish genuine PRD nodes "
                "from non-PRD dispatches, routing the latter to a maintenance "
                "bucket instead.\n\n"
                f"fetchSessionFiring body (first 800 chars):\n{body[:800]}"
            ),
        )

    def test_fetchSessionFiring_has_nonprd_bucket(self):
        """fetchSessionFiring() must have a non-PRD maintenance bucket label.

        Non-PRD dispatches (captured issues, backlog items, etc.) must be
        grouped under a clearly-labelled bucket, NOT as phantom 'PRD #N'.

        Before fix: no maintenance/non-PRD bucket exists; all groups render
          as 'PRD #N' nodes.
        After fix:  a label such as 'maintenance', 'non-PRD', or equivalent
          is present in the session-firing render path to catch non-PRD nodes.
        """
        body = self._get_fetch_session_firing_body()

        # Also check the render helper and any nearby bucket constant
        idx = self.content.find("fetchSessionFiring")
        surrounding = self.content[max(0, idx - 100): idx + len(body) + 500]

        has_maintenance_bucket = bool(
            re.search(
                r'(maintenance|non.?prd|non_prd|non-prd)',
                surrounding,
                re.IGNORECASE,
            )
        )
        self.assertTrue(
            has_maintenance_bucket,
            msg=(
                "fetchSessionFiring() / surrounding session-firing code: no "
                "'maintenance' / 'non-PRD' bucket label found.\n\n"
                "Before fix: every nestedGroups key is rendered as a PRD node; "
                "phantom 'PRD #N' nodes appear for captured/backlog issues.\n"
                "After fix:  a 'maintenance / non-PRD' bucket (or equivalent) "
                "is rendered for dispatches that don't belong to a real PRD.\n\n"
                f"Surrounding code snippet (first 600 chars):\n{surrounding[:600]}"
            ),
        )

    def test_session_firing_does_not_label_every_node_prd(self):
        """The session-firing render must NOT unconditionally label every group
        as 'PRD #N' regardless of whether the node has a real PRD.

        Specifically: the _renderNestedPrdNode path must NOT be the ONLY
        render path for nestedGroups nodes — there must be an alternate path
        for non-PRD nodes.

        Before fix: html += prdLabels.map(function(lbl) {
                      return _renderNestedPrdNode(lbl, nestedGroups[lbl]);
                    }).join('');
          — ALL nodes (including phantom ones) go through _renderNestedPrdNode.

        After fix:  a conditional splits PRD vs non-PRD nodes; non-PRD nodes
          go to a different render path or bucket.
        """
        body = self._get_fetch_session_firing_body()

        # Before fix: unconditional prdLabels.map → _renderNestedPrdNode
        # The test verifies there is now conditional logic (if/else or filter)
        # near the _renderNestedPrdNode call that checks prd_n.
        #
        # Strategy: find _renderNestedPrdNode calls in fetchSessionFiring body,
        # then check that there's a conditional (prd_n / if / filter) nearby.
        render_prd_calls = [m.start() for m in re.finditer(r'_renderNestedPrdNode', body)]

        if not render_prd_calls:
            # If _renderNestedPrdNode is inlined / the fix refactored it away,
            # check for a prd_n conditional instead.
            has_conditional = bool(re.search(r'\bprd_n\b.*\bif\b|\bif\b.*\bprd_n\b', body, re.DOTALL))
            self.assertTrue(
                has_conditional,
                msg=(
                    "fetchSessionFiring(): _renderNestedPrdNode call not found and "
                    "no prd_n conditional found — the non-PRD routing is missing."
                ),
            )
            return

        # _renderNestedPrdNode exists; check that prd_n is referenced nearby
        # (within 500 chars before each call — the conditional must precede the call)
        found_conditional = False
        for call_pos in render_prd_calls:
            window = body[max(0, call_pos - 500): call_pos + 50]
            if re.search(r'\bprd_n\b', window):
                found_conditional = True
                break

        self.assertTrue(
            found_conditional,
            msg=(
                "fetchSessionFiring(): _renderNestedPrdNode is called but prd_n "
                "is not checked nearby (within 500 chars before the call).\n\n"
                "Before fix: _renderNestedPrdNode(lbl, nestedGroups[lbl]) called "
                "for EVERY nestedGroups key unconditionally.\n"
                "After fix:  prd_n is checked before _renderNestedPrdNode so only "
                "genuine PRD nodes are rendered as PRD nodes.\n\n"
                f"Context around first call:\n"
                f"{body[max(0, render_prd_calls[0]-400):render_prd_calls[0]+100]!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
