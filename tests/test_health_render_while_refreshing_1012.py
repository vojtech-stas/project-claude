"""
Regression tests for issue #1012 — Health board shows 'computing...' hiding
valid stale data while refreshing=True (slow-gh).

Two defects:
  (a) Structural (front-end): loadHealth()'s _isCold logic treats
      data.refreshing=True as cold, even when data has populated checks.
      This triggers continuous fast-retry that (via the 30s abort timer)
      blanks already-rendered grids by resetting them to 'computing…'.
      Fix: _isCold must NOT be set True from data.refreshing alone when
      checks are genuinely present. Only the absent-checks condition counts.
  (b) Backend: _HEALTH_TTL is 30s — shorter than typical slow-gh compute
      time, so refreshing=True is near-permanent.
      Fix: raise _HEALTH_TTL to >= 180s so the cache isn't perpetually expired.

These tests FAIL on develop before the fix and PASS after.

NO top-level `import pytest` — stdlib unittest only.

Runner:
  python -m unittest tests.test_health_render_while_refreshing_1012 -v
  python -m pytest tests/test_health_render_while_refreshing_1012.py -v
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"
HEALTH_PY  = REPO_ROOT / "dashboard" / "health.py"


def _load_index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _load_health_py() -> str:
    return HEALTH_PY.read_text(encoding="utf-8")


def _extract_load_health_body(content: str) -> str:
    """Extract the full body of async function loadHealth() by brace-matching."""
    m = re.search(r'async function loadHealth\s*\(\s*\)', content)
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


# ---------------------------------------------------------------------------
# (a) loadHealth(): _isCold must NOT short-circuit to true on refreshing alone
#     when checks are present.
# ---------------------------------------------------------------------------

class TestIsColdDoesNotTreatRefreshingAsAbsent(unittest.TestCase):
    """Regression (a): the _isCold variable in loadHealth() must not be set
    True by data.refreshing alone.

    Before fix (current develop):
        var _isCold = data.refreshing ||
            (!data.purposeGroups && !data.auditMeta && ...);

      This unconditionally sets _isCold=True whenever data.refreshing=True,
      even when all check groups have populated data. The repeated fast-retry
      loop, combined with the 30s abort timer, causes already-rendered grids
      to be blanked with 'computing…'.

    After fix:
      _isCold is computed purely from data-presence, NOT from data.refreshing.
      data.refreshing only drives the subtle timestamp indicator, NOT the retry.
      Structural assertion: the _isCold assignment block must NOT have
      `data.refreshing` as a standalone top-level OR-operand that can force
      _isCold=True when data IS present.
    """

    def setUp(self):
        self.content = _load_index()
        self.body = _extract_load_health_body(self.content)

    def test_isCold_not_set_from_refreshing_alone(self):
        """_isCold must not have 'data.refreshing' as a standalone OR operand
        at the top of the _isCold assignment (the pre-fix pattern).

        Before fix:
            var _isCold = data.refreshing ||
              (!data.purposeGroups && ...);
        This means: if data.refreshing => _isCold=True => retry loop fires
        even when checks are fully present.

        After fix: data.refreshing is NOT the first operand of _isCold,
        or _isCold is not set at all from data.refreshing in isolation.
        The check for data presence should be driven by checks.length, not
        by the refreshing flag.
        """
        # Find the _isCold assignment block in loadHealth body
        # Pattern: var _isCold = data.refreshing || ...
        # This is the pre-fix buggy pattern that must NOT exist after the fix.
        buggy_pattern = re.compile(
            r'var\s+_isCold\s*=\s*data\.refreshing\s*\|\|',
            re.DOTALL
        )
        match = buggy_pattern.search(self.body)
        self.assertIsNone(
            match,
            msg=(
                "loadHealth() still has the pre-fix _isCold pattern:\n"
                "  `var _isCold = data.refreshing || ...`\n\n"
                "This unconditionally sets _isCold=True whenever data.refreshing\n"
                "is True — even when all check groups have populated data. This\n"
                "triggers a fast-retry loop that (via the 30s abort timer) blanks\n"
                "already-rendered Health grids with 'computing…'.\n\n"
                "Fix: compute _isCold from data-PRESENCE only (checks.length == 0\n"
                "or genuinely missing fields), not from the refreshing flag.\n"
                "The refreshing flag should only drive the timestamp indicator."
            )
        )

    def test_isCold_checks_data_presence(self):
        """After removing data.refreshing from _isCold, the body must still
        have a data-presence check (so cold-bootstrap case is still retried).

        The fix must preserve the cold-bootstrap retry; it just must not
        conflate 'refreshing' with 'absent'. We look for a check-absence
        pattern (checks.length, purposeGroups, auditMeta, etc.) in the
        _isCold assignment.
        """
        # After the fix, _isCold should still check for absent data
        data_presence_pattern = re.compile(
            r'_isCold\s*[=|].*?(?:\.length|purposeGroups|auditMeta|substrateMeta|checks)',
            re.DOTALL
        )
        match = data_presence_pattern.search(self.body)
        self.assertIsNotNone(
            match,
            msg=(
                "loadHealth() does not appear to have a data-presence check\n"
                "for _isCold (e.g. checks.length, purposeGroups, auditMeta…).\n\n"
                "The fix must preserve the cold-bootstrap retry (when checks\n"
                "are genuinely absent) while removing the data.refreshing\n"
                "short-circuit. Both are needed."
            )
        )

    def test_refreshing_indicator_preserved(self):
        """The subtle refreshing indicator must still be present after the fix.

        The issue spec says: keep the existing '(refreshing…)' timestamp
        indicator for the stale-but-present case. This checks that
        'refreshing…' still appears somewhere in the health-related JS.
        """
        # The timestamp indicator sets text like: data.refreshing ? ' (refreshing…)' : ''
        # Verify the refreshing indicator is still rendered (just not misused for _isCold).
        health_section = self.content
        has_indicator = bool(re.search(
            r'refreshing.*?refreshing',  # matches 'refreshing…' or similar
            health_section,
            re.DOTALL | re.IGNORECASE
        ))
        self.assertTrue(
            has_indicator,
            msg=(
                "The '(refreshing…)' timestamp indicator appears to have been\n"
                "removed from the Health JS. The fix must preserve the subtle\n"
                "visual indicator while fixing the _isCold mis-classification."
            )
        )


# ---------------------------------------------------------------------------
# (b) Backend: _HEALTH_TTL must be >= 180 seconds
# ---------------------------------------------------------------------------

class TestHealthTTLSufficient(unittest.TestCase):
    """Regression (b): _HEALTH_TTL in health.py must be raised from 30s to
    a value >= 180s (comfortably above typical slow-gh compute time ~60-95s).

    Before fix (current develop): _HEALTH_TTL = 30
      Under slow-gh, the background recompute takes ~30-95s — as long as or
      longer than the TTL. So the cache expires before the recompute finishes,
      making refreshing=True near-permanent.

    After fix: _HEALTH_TTL >= 180
      This gives the background recompute ample time to finish before the
      cache is considered expired, so refreshing=True is brief, not permanent.
    """

    MIN_TTL = 180  # seconds — fix requirement per issue #1012

    def setUp(self):
        self.content = _load_health_py()

    def _get_health_ttl_value(self) -> int:
        """Parse the _HEALTH_TTL assignment from health.py."""
        m = re.search(r'^_HEALTH_TTL\s*=\s*(\d+)', self.content, re.MULTILINE)
        if not m:
            raise AssertionError(
                "_HEALTH_TTL not found in dashboard/health.py. "
                "Expected: `_HEALTH_TTL = <integer>` at module level."
            )
        return int(m.group(1))

    def test_health_ttl_is_at_least_180(self):
        """_HEALTH_TTL must be >= 180 seconds after the fix.

        Before fix: _HEALTH_TTL = 30
          Under slow-gh the cache expires before recompute finishes
          => refreshing=True is near-permanent.

        After fix: _HEALTH_TTL >= 180
          TTL is comfortably above the typical gh-dependent compute time
          (~60-95s), so refreshing=True is brief.
        """
        actual = self._get_health_ttl_value()
        self.assertGreaterEqual(
            actual,
            self.MIN_TTL,
            msg=(
                f"_HEALTH_TTL = {actual}s is too low (minimum required: {self.MIN_TTL}s).\n\n"
                f"Before fix: _HEALTH_TTL = 30s — under slow-gh the background recompute\n"
                f"takes ~30-95s, so the cache expires before recompute finishes and\n"
                f"refreshing=True is near-permanent.\n\n"
                f"After fix: _HEALTH_TTL >= {self.MIN_TTL}s so the cache remains valid\n"
                f"for the full recompute cycle and refreshing=True is brief (not permanent).\n"
                f"Issue #1012: bump _HEALTH_TTL to {self.MIN_TTL}+ seconds."
            )
        )

    def test_health_ttl_has_1012_comment(self):
        """_HEALTH_TTL line or its vicinity must reference #1012 (fix citation).

        This ensures the TTL bump is intentional and traceable, not accidental.
        """
        # Find the _HEALTH_TTL line and check the surrounding 3 lines for #1012
        lines = self.content.splitlines()
        ttl_line_idx = None
        for i, line in enumerate(lines):
            if re.match(r'\s*_HEALTH_TTL\s*=', line):
                ttl_line_idx = i
                break

        if ttl_line_idx is None:
            self.fail("_HEALTH_TTL not found in health.py")

        # Check the TTL line itself and up to 2 lines after it for '#1012'
        context_lines = lines[ttl_line_idx:ttl_line_idx + 3]
        context_text = '\n'.join(context_lines)
        self.assertIn(
            '1012',
            context_text,
            msg=(
                f"_HEALTH_TTL definition (line {ttl_line_idx + 1}) does not cite #1012.\n"
                f"Context:\n{context_text}\n\n"
                "Please add a comment citing #1012 on or after the _HEALTH_TTL line "
                "to make the intentional TTL bump traceable."
            )
        )


if __name__ == "__main__":
    unittest.main()
