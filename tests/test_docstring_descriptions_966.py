"""
tests/test_docstring_descriptions_966.py

Regression tests for slice #966 — docstring-sourced descriptions + universal popup.

Per ADR-0067 D2: test-first ordering — these tests are written to FAIL before the
slice #966 implementation lands and PASS after.

Coverage:
  1. _description_from_docstring() returns a non-empty string for every check
     function registered in CHECK_REGISTRY.
  2. _build_health_data() (or the individual check assemblers) attaches a
     non-empty ``description`` field to every check dict in every group.
  3. The ``_parse_skill_rationale`` symbol does NOT exist in health.py
     (regression #955 removed).
  4. No check's description contains the "rationale unavailable — see SKILL.md"
     fallback string.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_docstring_descriptions_966.py -v
"""

import importlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


def _import_health():
    """Import (or reload) the health module, returning it."""
    if "health" in sys.modules:
        return sys.modules["health"]
    import health
    return health


class TestDescriptionFromDocstring(unittest.TestCase):
    """Unit tests for _description_from_docstring()."""

    def setUp(self):
        self.health = _import_health()

    def test_returns_string_for_check_function(self):
        """_description_from_docstring returns a non-empty string for a real check fn."""
        fn = self.health.check_rule_coverage
        desc = self.health._description_from_docstring(fn)
        self.assertIsInstance(desc, str)
        self.assertTrue(len(desc) > 0, "description should be non-empty")

    def test_returns_first_paragraph_only(self):
        """_description_from_docstring stops at the first blank line."""
        fn = self.health.check_rule_coverage
        desc = self.health._description_from_docstring(fn)
        # Should not contain a blank line
        self.assertNotIn("\n\n", desc)

    def test_returns_non_empty_for_every_registered_check(self):
        """Every function in CHECK_REGISTRY has a non-empty docstring description."""
        registry = self.health.CHECK_REGISTRY
        for check_id, fn in registry.items():
            with self.subTest(check_id=check_id):
                desc = self.health._description_from_docstring(fn)
                self.assertIsInstance(desc, str, f"{check_id}: description is not a string")
                self.assertTrue(
                    len(desc.strip()) > 0,
                    f"{check_id}: description is empty — add a docstring to {fn.__name__}",
                )

    def test_none_fn_returns_empty_string(self):
        """_description_from_docstring(None) returns empty string, no crash."""
        desc = self.health._description_from_docstring(None)
        self.assertEqual(desc, "")

    def test_no_rationale_unavailable_fallback(self):
        """No description should contain the old broken fallback string."""
        registry = self.health.CHECK_REGISTRY
        bad_string = "rationale unavailable"
        for check_id, fn in registry.items():
            with self.subTest(check_id=check_id):
                desc = self.health._description_from_docstring(fn)
                self.assertNotIn(
                    bad_string, desc,
                    f"{check_id}: description contains deprecated fallback text",
                )


class TestParseSkillRationaleGone(unittest.TestCase):
    """Assert _parse_skill_rationale is removed (regression #955 / slice #966)."""

    def test_symbol_not_present(self):
        """health module must NOT export _parse_skill_rationale (regression #955)."""
        health = _import_health()
        self.assertFalse(
            hasattr(health, "_parse_skill_rationale"),
            "_parse_skill_rationale still exists in health.py — must be removed (slice #966)",
        )


class TestDescriptionFieldInBuildHealthData(unittest.TestCase):
    """Integration test: _build_health_data attaches description to every check dict.

    Uses direct calls to individual group assemblers (audit_meta, _attach_descriptions)
    rather than running the full _build_health_data to avoid slow network checks.
    """

    def setUp(self):
        self.health = _import_health()

    def _assert_descriptions_present(self, checks: list, group_name: str):
        """Every dict in checks must have a non-empty description field."""
        self.assertTrue(
            len(checks) > 0,
            f"{group_name}: check list is empty — cannot verify description field",
        )
        for c in checks:
            check_id = c.get("id", "<no-id>")
            with self.subTest(group=group_name, check_id=check_id):
                self.assertIn(
                    "description", c,
                    f"{group_name}/{check_id}: missing 'description' key",
                )
                self.assertIsInstance(c["description"], str)
                self.assertTrue(
                    len(c["description"].strip()) > 0,
                    f"{group_name}/{check_id}: 'description' is empty",
                )
                self.assertNotIn(
                    "rationale unavailable",
                    c["description"],
                    f"{group_name}/{check_id}: 'description' contains deprecated fallback",
                )

    def test_audit_meta_checks_have_description(self):
        """audit_meta() checks have a description field (DOCS-* group)."""
        result = self.health.audit_meta()
        checks = result.get("checks", [])
        self._assert_descriptions_present(checks, "auditMeta")

    def test_attach_descriptions_adds_field(self):
        """_attach_descriptions() adds description to a minimal check dict list."""
        health = self.health
        # Create a minimal check list using a real check id
        sample = [{"id": "RULE-COVERAGE", "result": "WARN", "detail": "test"}]
        result = health._attach_descriptions(sample)
        self.assertEqual(len(result), 1)
        self.assertIn("description", result[0])
        self.assertTrue(len(result[0]["description"].strip()) > 0)

    def test_attach_descriptions_unknown_id_falls_back_to_id(self):
        """_attach_descriptions() falls back to the check id for unknown IDs."""
        health = self.health
        sample = [{"id": "NONEXISTENT-CHECK-ZZZ", "result": "PASS", "detail": ""}]
        result = health._attach_descriptions(sample)
        self.assertIn("description", result[0])
        # Fallback should be non-empty (check id or function name)
        self.assertTrue(len(result[0]["description"].strip()) > 0)


if __name__ == "__main__":
    unittest.main()
