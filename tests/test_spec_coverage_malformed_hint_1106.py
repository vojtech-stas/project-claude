"""
tests/test_spec_coverage_malformed_hint_1106.py

Regression test for captured issue #1106(b), folded into slice #1086 (PRD
#1075 closing pass): SPEC-COVERAGE silently grandfathers a PRD whose slices
carry a bare `Covers: #N` line (missing ADR-0066 D2's required `§2` token) —
indistinguishable, in the prior detail string, from a PRD that predates the
Covers: convention entirely (no Covers: line at all). This test asserts the
malformed-form hint: when a bare `Covers: #N` line is present but the
canonical `Covers: §2 #N` form is not, check_spec_coverage()'s detail string
names it explicitly rather than reporting a bare "grandfathered" verdict.

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_spec_coverage_malformed_hint_1106.py -v
"""
import importlib
import json
import os
import sys
import unittest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_TESTS_DIR)
_DASHBOARD_DIR = os.path.join(_REPO_ROOT, "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


def _reimport(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


class TestMalformedCoversHint(unittest.TestCase):
    def _patch_gh_fetch(self, health_mod, prd_body: str, slice_body: str):
        prd_json = json.dumps([{"number": 2000, "title": "PRD: fixture", "body": prd_body}])
        slice_json = json.dumps([{"number": 2001, "title": "slice", "body": slice_body}])

        def _fake_health_gh_fetch(args, *, ttl=60.0, timeout=5.0):
            if "prd" in args:
                return (0, prd_json)
            if "slice" in args:
                return (0, slice_json)
            return (1, "")

        health_mod._health_gh_fetch = _fake_health_gh_fetch

    def test_bare_covers_line_is_named_as_malformed_not_silently_grandfathered(self):
        health = _reimport("health")
        prd_body = "## 2. Goal / Success criteria\n1. WHEN X SHALL Y.\n\n## 3. Non-goals\n"
        # Bare form — missing "§2" per ADR-0066 D2 — the exact #1106(a) defect.
        slice_body = "Part of PRD #2000.\n\nCovers: #1\n"
        self._patch_gh_fetch(health, prd_body, slice_body)

        result = health.check_spec_coverage()

        self.assertIn(2000, result.get("grandfathered", []))
        self.assertIn(
            "malformed", result.get("detail", "").lower(),
            msg=(
                "expected the detail string to call out the malformed bare "
                f"'Covers: #N' form; got: {result.get('detail')}"
            ),
        )
        self.assertIn("PRD#2000", result.get("detail", ""))

    def test_canonical_covers_line_triggers_no_malformed_hint(self):
        health = _reimport("health")
        prd_body = "## 2. Goal / Success criteria\n1. WHEN X SHALL Y.\n\n## 3. Non-goals\n"
        slice_body = "Part of PRD #2000.\n\nCovers: §2 #1\n"
        self._patch_gh_fetch(health, prd_body, slice_body)

        result = health.check_spec_coverage()

        self.assertNotIn("malformed", result.get("detail", "").lower())
        self.assertEqual("PASS", result["result"])


if __name__ == "__main__":
    unittest.main()
