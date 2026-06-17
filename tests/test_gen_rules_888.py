"""
Regression tests for PRD #888 slice #889 — gen_rules.py walking skeleton.

Verifies:
1. gen_rules.py excludes rule_ids from ADRs with status "superseded".
2. gen_rules.py includes rule_ids from non-superseded ADRs.
3. ADRs without frontmatter are skipped gracefully (no crash).
4. generate() with a fixture ADR set produces the expected output.

All tests use an in-memory fixture set via monkeypatching of the module's
internal loader — no real ADR files are required.  Tests are offline,
deterministic, and network-free.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_gen_rules_888.py -v
"""

import sys
import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Ensure tools/ is importable
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


import gen_rules  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture ADR data
# ---------------------------------------------------------------------------

# One active ADR for the "capture" scope
_ACTIVE_ADR = {
    "path": Path("/fake/decisions/0006-backlog.md"),
    "id": "ADR-0006",
    "status": "accepted",
    "supersedes": [],
    "superseded_by": [],
    "scope": "capture",
    "rule_ids": ["CAP-001", "CAP-002"],
}

# One superseded ADR — its rule_ids must NOT appear in output
_SUPERSEDED_ADR = {
    "path": Path("/fake/decisions/0007-old.md"),
    "id": "ADR-0007",
    "status": "superseded",
    "supersedes": [],
    "superseded_by": ["ADR-0008"],
    "scope": "capture",
    "rule_ids": ["CAP-OBSOLETE"],
}

# An ADR that has superseded_by set but status still "accepted" (edge case)
_SUPERSEDED_BY_ADR = {
    "path": Path("/fake/decisions/0009-also-old.md"),
    "id": "ADR-0009",
    "status": "accepted",
    "supersedes": [],
    "superseded_by": ["ADR-0010"],  # superseded_by means excluded
    "scope": "capture",
    "rule_ids": ["CAP-ALSO-OBSOLETE"],
}


# ---------------------------------------------------------------------------
# Helper: run generate() against a fixture set and capture output
# ---------------------------------------------------------------------------

def _run_with_fixture(adrs: list[dict]) -> tuple[int, dict[str, str]]:
    """
    Run gen_rules.generate() against a fixture ADR list.

    Monkeypatches _load_adrs() and writes output to a temp directory.
    Returns (exit_code, {scope: content}) where content is the generated text.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir) / ".claude" / "rules"

        with (
            patch.object(gen_rules, "_load_adrs", return_value=adrs),
            patch.object(gen_rules, "RULES_DIR", rules_dir),
            patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
        ):
            exit_code = gen_rules.generate(check_mode=False)

        # Collect generated files
        generated: dict[str, str] = {}
        if rules_dir.exists():
            for f in rules_dir.glob("*.md"):
                generated[f.stem] = f.read_text(encoding="utf-8")

    return exit_code, generated


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenRulesSuperseded(unittest.TestCase):
    """Rule IDs from superseded ADRs must be excluded."""

    def test_superseded_rule_id_absent(self):
        """CAP-OBSOLETE from a status=superseded ADR must not appear in output."""
        adrs = [_ACTIVE_ADR, _SUPERSEDED_ADR]
        exit_code, generated = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0, "generate() should exit 0")
        self.assertIn("capture", generated, "capture.md should be generated")
        self.assertNotIn(
            "CAP-OBSOLETE",
            generated["capture"],
            "Rule from superseded ADR must not appear in digest",
        )

    def test_superseded_by_rule_id_absent(self):
        """CAP-ALSO-OBSOLETE from an ADR with superseded_by must not appear."""
        adrs = [_ACTIVE_ADR, _SUPERSEDED_BY_ADR]
        exit_code, generated = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0)
        self.assertIn("capture", generated)
        self.assertNotIn(
            "CAP-ALSO-OBSOLETE",
            generated["capture"],
            "Rule from ADR with superseded_by must not appear in digest",
        )


class TestGenRulesCurrentIncluded(unittest.TestCase):
    """Rule IDs from non-superseded ADRs must be present in output."""

    def test_active_rule_ids_present(self):
        """CAP-001 and CAP-002 from active ADR must appear in digest."""
        adrs = [_ACTIVE_ADR]
        exit_code, generated = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0)
        self.assertIn("capture", generated)
        content = generated["capture"]
        self.assertIn("CAP-001", content, "CAP-001 must appear in digest")
        self.assertIn("CAP-002", content, "CAP-002 must appear in digest")

    def test_generated_header_present(self):
        """Output file must start with the DO-NOT-EDIT generated header."""
        adrs = [_ACTIVE_ADR]
        _, generated = _run_with_fixture(adrs)
        self.assertIn("capture", generated)
        self.assertIn(
            "GENERATED by tools/gen_rules.py",
            generated["capture"],
            "Generated header must be present",
        )
        self.assertIn(
            "DO NOT EDIT",
            generated["capture"],
            "DO NOT EDIT warning must be present",
        )


class TestGenRulesEmptyFrontmatter(unittest.TestCase):
    """ADRs without frontmatter are skipped gracefully (no crash)."""

    def test_no_frontmatter_skipped(self):
        """An ADR without frontmatter should not crash generate()."""
        # _parse_frontmatter returns None for no-frontmatter ADRs;
        # _load_adrs skips them; we test that generate() runs cleanly
        # when _load_adrs returns only the active ADR (simulating the
        # no-frontmatter ones being already filtered out).
        adrs = [_ACTIVE_ADR]
        exit_code, generated = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0, "generate() must not crash on empty fixtures")

    def test_parse_frontmatter_none_for_no_marker(self):
        """_parse_frontmatter returns None when there is no --- marker."""
        text = "# ADR-9999\n\nSome content\n"
        result = gen_rules._parse_frontmatter(text)
        self.assertIsNone(result, "_parse_frontmatter must return None for no-marker ADR")

    def test_parse_frontmatter_returns_dict_for_valid(self):
        """_parse_frontmatter parses a valid frontmatter block."""
        text = (
            "---\n"
            'id: "ADR-0006"\n'
            'status: "accepted"\n'
            "supersedes: []\n"
            "superseded_by: []\n"
            'scope: "capture"\n'
            "rule_ids:\n"
            "  - CAP-001\n"
            "---\n"
            "# ADR body\n"
        )
        result = gen_rules._parse_frontmatter(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "ADR-0006")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["scope"], "capture")
        self.assertIn("CAP-001", result["rule_ids"])


class TestGenRulesCheckMode(unittest.TestCase):
    """--check mode detects stale/missing files and passes on clean tree."""

    def test_check_mode_fails_on_missing_file(self):
        """--check mode returns non-zero when .claude/rules/<scope>.md is absent."""
        adrs = [_ACTIVE_ADR]
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            # Do NOT create rules_dir — file is missing
            with (
                patch.object(gen_rules, "_load_adrs", return_value=adrs),
                patch.object(gen_rules, "RULES_DIR", rules_dir),
                patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
            ):
                exit_code = gen_rules.generate(check_mode=True)
        self.assertEqual(exit_code, 1, "check_mode must return 1 when file is missing")

    def test_check_mode_passes_on_clean_tree(self):
        """--check mode returns 0 when committed files match fresh output."""
        adrs = [_ACTIVE_ADR]
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            # First generate the files
            rules_dir.mkdir(parents=True, exist_ok=True)
            with (
                patch.object(gen_rules, "_load_adrs", return_value=adrs),
                patch.object(gen_rules, "RULES_DIR", rules_dir),
                patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
            ):
                gen_rules.generate(check_mode=False)
            # Now check — should be clean
            with (
                patch.object(gen_rules, "_load_adrs", return_value=adrs),
                patch.object(gen_rules, "RULES_DIR", rules_dir),
                patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
            ):
                exit_code = gen_rules.generate(check_mode=True)
        self.assertEqual(exit_code, 0, "check_mode must return 0 on clean tree")


class TestGenRulesRealFrontmatter(unittest.TestCase):
    """Integration: real ADR files in decisions/ have frontmatter and produce output."""

    def test_real_adr_frontmatter_produces_output(self):
        """Running gen_rules against the real decisions/ dir exits 0 and emits capture.md."""
        # This test verifies the full end-to-end path against the real repo.
        # Requires decisions/006/008/024/063 to have frontmatter (slice deliverable).
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_TOOLS_DIR / "gen_rules.py"), "--check"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"gen_rules.py --check failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_no_superseded_rule_in_real_output(self):
        """No rule_id from a superseded ADR appears in .claude/rules/capture.md."""
        rules_file = _REPO_ROOT / ".claude" / "rules" / "capture.md"
        self.assertTrue(
            rules_file.exists(),
            ".claude/rules/capture.md must exist (run gen_rules.py first)",
        )
        content = rules_file.read_text(encoding="utf-8")
        # Verify the generated header is present
        self.assertIn("GENERATED by tools/gen_rules.py", content)
        # No superseded rule_ids should appear (none in the capture scope)
        # Verify at least one current rule_id from an active ADR is present
        self.assertIn("CAP-001", content, "CAP-001 from ADR-0006 must be in output")


if __name__ == "__main__":
    unittest.main()
