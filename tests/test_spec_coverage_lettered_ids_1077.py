"""
Regression tests for issue #1077 — SPEC-COVERAGE's regexes silently dropped
the trailing letter on lettered §2 sub-criteria (e.g. PRD #1075's `2a.`/`2b.`/
`10a.`-`10d.`), collapsing distinct criteria onto one bare digit and producing
FALSE phantoms/orphans against a PRD with complete semantic coverage.

Verbatim symptom (from #1077, verified against the pre-fix regexes):
    _crit_num.findall("1. WHEN...\\n2a. WHEN...\\n2b. WHEN...\\n10a. WHEN...\\n10d. WHEN...")
    -> ['1', '3']   # 2a/2b/10a/10d invisible to the parser
    _covers_num.findall("Covers: §2 #1, #2a, #2b, #10a, #10b, #10c, #10d")
    -> ['1', '2', '2', '10', '10', '10', '10']   # letter suffixes silently dropped

Fix (dashboard/health.py, PRD #1075 slice #1085): widen both regexes to accept
an optional trailing lowercase letter (`^(\\d+[a-z]?)\\.\\s+\\S` /
`#(\\d+[a-z]?)`) and switch the criterion-ID model from int to str so "2" and
"2a" cannot collide.

These tests FAIL on develop before the fix (only bare-integer IDs are parsed)
and PASS after (per ADR-0067 D3 test-first ordering — this test commit
precedes the fix commit in branch history).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_spec_coverage_lettered_ids_1077.py -v
"""

import importlib
import os
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_DASHBOARD_DIR = os.path.join(_REPO_ROOT, "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


def _reimport(module_name: str):
    """Force a fresh import of *module_name* (reliable module-attr monkeypatching)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


# ---------------------------------------------------------------------------
# Group 1: regex/helper-level — the exact #1077 symptom fixtures
# ---------------------------------------------------------------------------

class TestLetteredCriteriaRegexes(unittest.TestCase):
    """_parse_sec2_criteria() and the Covers-line regex must retain the
    trailing letter on lettered sub-criteria IDs."""

    def test_prd_side_parses_lettered_criteria(self):
        """PRD #1075's actual §2 shape: 1, 2a, 2b, 3-9, 10a-10d."""
        health = _reimport("health")
        body = (
            "## 1. Problem\nsome problem text\n\n"
            "## 2. Goal / Success criteria\n"
            "1. WHEN a thing happens SHALL do X.\n"
            "2a. WHEN a query happens SHALL answer Y.\n"
            "2b. WHEN a pre-v3 query happens SHALL fail loudly.\n"
            "10a. WHEN the suite runs SHALL pass.\n"
            "10d. WHEN integrity fixes land SHALL be fixed.\n"
            "\n## 3. Non-goals\nsome non-goal text\n"
        )
        criteria = health._parse_sec2_criteria(body)
        self.assertEqual(
            {"1", "2a", "2b", "10a", "10d"},
            criteria,
            msg=f"lettered criteria dropped or collapsed; got {criteria}",
        )

    def test_slice_side_covers_line_parses_lettered_ids(self):
        """A slice's 'Covers: §2 #n' line with lettered IDs must not collapse
        distinct sub-criteria onto the same bare digit."""
        health = _reimport("health")
        matches = health._SPEC_COVERS_NUM.findall(
            "Covers: §2 #1, #2a, #2b, #10a, #10b, #10c, #10d"
        )
        self.assertEqual(
            ["1", "2a", "2b", "10a", "10b", "10c", "10d"],
            matches,
            msg=f"letter suffixes dropped/collapsed; got {matches}",
        )

    def test_criterion_ids_are_strings_not_ints(self):
        """'2' and '2a' must be distinct entries — never collide under an int model."""
        health = _reimport("health")
        criteria = health._parse_sec2_criteria(
            "## 2. Goal\n2. WHEN X SHALL Y.\n2a. WHEN Z SHALL W.\n## 3. Non-goals\n"
        )
        self.assertIn("2", criteria)
        self.assertIn("2a", criteria)
        self.assertEqual(2, len(criteria), msg=f"'2' and '2a' collided: {criteria}")

    def test_crit_sort_key_orders_numerically_then_alphabetically(self):
        """A bare string sort would put '10a' before '2a' — the sort key must not."""
        health = _reimport("health")
        ids = ["10a", "2a", "1", "2", "10b"]
        ordered = sorted(ids, key=health._crit_sort_key)
        self.assertEqual(["1", "2", "2a", "10a", "10b"], ordered)


# ---------------------------------------------------------------------------
# Group 2: end-to-end check_spec_coverage() — false-FAIL must not recur
# ---------------------------------------------------------------------------

class TestSpecCoverageEndToEndLettered(unittest.TestCase):
    """A PRD with lettered §2 criteria, fully covered by a slice's lettered
    Covers: line, must report PASS (fully covered) — never a false FAIL with
    phantom/orphan criteria (the exact #1077 regression scenario)."""

    def _patch_gh_fetch(self, health_mod, prd_body: str, slice_body: str):
        import json as _json

        prd_json = _json.dumps([{"number": 1075, "title": "PRD: A+ trace core", "body": prd_body}])
        slice_json = _json.dumps([{"number": 1085, "title": "slice", "body": slice_body}])

        def _fake_health_gh_fetch(args, *, ttl=60.0, timeout=5.0):
            if "prd" in args:
                return (0, prd_json)
            if "slice" in args:
                return (0, slice_json)
            return (1, "")

        health_mod._health_gh_fetch = _fake_health_gh_fetch

    def test_fully_covered_lettered_prd_is_pass_not_false_fail(self):
        health = _reimport("health")
        prd_body = (
            "## 2. Goal / Success criteria\n"
            "1. WHEN X SHALL Y.\n"
            "2a. WHEN A SHALL B.\n"
            "2b. WHEN C SHALL D.\n"
            "10a. WHEN E SHALL F.\n"
            "10d. WHEN G SHALL H.\n"
            "\n## 3. Non-goals\n"
        )
        slice_body = (
            "Part of PRD #1075.\n\n"
            "Covers: §2 #1, #2a, #2b, #10a, #10d\n"
        )
        self._patch_gh_fetch(health, prd_body, slice_body)

        result = health.check_spec_coverage()

        self.assertEqual(
            "PASS",
            result["result"],
            msg=(
                "expected PASS (fully covered) for a lettered PRD with a matching "
                f"lettered Covers: line; got {result['result']}: {result.get('detail')} "
                "-- this is the exact #1077 false-FAIL regression"
            ),
        )
        self.assertEqual([], result.get("partial", []))


if __name__ == "__main__":
    unittest.main()
