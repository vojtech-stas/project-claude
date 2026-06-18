"""
Regression tests for PRD #888 slice #889 — gen_rules.py walking skeleton.
Updated in slice #938 (ADR-0073) for SCOPE_TARGET global/area split.

Verifies:
1. gen_rules.py excludes rule_ids from ADRs with status "superseded".
2. gen_rules.py includes rule_ids from non-superseded ADRs.
3. ADRs without frontmatter are skipped gracefully (no crash).
4. generate() with a fixture ADR set produces the expected output.
5. AREA scopes render into .claude/rules/<scope>.md with paths: frontmatter.
6. GLOBAL scopes render into CLAUDE.md generated-region blocks.
7. --check mode detects stale/missing outputs.

All fixture-based tests use a temp directory and monkeypatching.
Tests are offline, deterministic, and network-free.

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

# One active ADR for the "hooks" scope (AREA — renders to .claude/rules/hooks.md)
_ACTIVE_ADR_AREA = {
    "path": Path("/fake/decisions/0015-hooks.md"),
    "id": "ADR-0015",
    "status": "accepted",
    "supersedes": [],
    "superseded_by": [],
    "scope": "hooks",
    "rule_ids": ["HOK-001", "HOK-002"],
}

# One active ADR for the "capture" scope (GLOBAL — renders to CLAUDE.md region)
_ACTIVE_ADR_GLOBAL = {
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
    "scope": "hooks",
    "rule_ids": ["HOK-OBSOLETE"],
}

# An ADR that has superseded_by set but status still "accepted" (edge case)
_SUPERSEDED_BY_ADR = {
    "path": Path("/fake/decisions/0009-also-old.md"),
    "id": "ADR-0009",
    "status": "accepted",
    "supersedes": [],
    "superseded_by": ["ADR-0010"],  # superseded_by means excluded
    "scope": "hooks",
    "rule_ids": ["HOK-ALSO-OBSOLETE"],
}


# ---------------------------------------------------------------------------
# Helper: run generate() against a fixture set and capture output
# ---------------------------------------------------------------------------

def _run_with_fixture(adrs: list, scope_target_override: dict | None = None):
    """
    Run gen_rules.generate() against a fixture ADR list.

    Monkeypatches _load_adrs(), RULES_DIR, REPO_ROOT, and optionally
    SCOPE_TARGET. For AREA scopes, returns file content; for GLOBAL scopes,
    returns CLAUDE.md content.

    Returns (exit_code, area_files_dict, claude_md_content) where
    area_files_dict maps scope → content from .claude/rules/<scope>.md.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir) / ".claude" / "rules"
        claude_md = Path(tmpdir) / "CLAUDE.md"
        # Create an empty CLAUDE.md for global scopes to append to
        claude_md.write_text("# CLAUDE.md placeholder\n", encoding="utf-8")

        target_override = scope_target_override or gen_rules.SCOPE_TARGET

        with (
            patch.object(gen_rules, "_load_adrs", return_value=adrs),
            patch.object(gen_rules, "RULES_DIR", rules_dir),
            patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
            patch.object(gen_rules, "CLAUDE_MD", claude_md),
            patch.object(gen_rules, "SCOPE_TARGET", target_override),
        ):
            exit_code = gen_rules.generate(check_mode=False)

        # Collect generated area files
        area_files: dict[str, str] = {}
        if rules_dir.exists():
            for f in rules_dir.glob("*.md"):
                area_files[f.stem] = f.read_text(encoding="utf-8")

        claude_content = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""

    return exit_code, area_files, claude_content


def _run_check_with_fixture(adrs: list, scope_target_override: dict | None = None):
    """
    Run gen_rules.generate(check_mode=True) on a clean pre-generated tree.

    Returns exit_code.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_dir = Path(tmpdir) / ".claude" / "rules"
        claude_md = Path(tmpdir) / "CLAUDE.md"
        claude_md.write_text("# CLAUDE.md placeholder\n", encoding="utf-8")

        target_override = scope_target_override or gen_rules.SCOPE_TARGET

        # First generate
        with (
            patch.object(gen_rules, "_load_adrs", return_value=adrs),
            patch.object(gen_rules, "RULES_DIR", rules_dir),
            patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
            patch.object(gen_rules, "CLAUDE_MD", claude_md),
            patch.object(gen_rules, "SCOPE_TARGET", target_override),
        ):
            gen_rules.generate(check_mode=False)

        # Now check
        with (
            patch.object(gen_rules, "_load_adrs", return_value=adrs),
            patch.object(gen_rules, "RULES_DIR", rules_dir),
            patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
            patch.object(gen_rules, "CLAUDE_MD", claude_md),
            patch.object(gen_rules, "SCOPE_TARGET", target_override),
        ):
            exit_code = gen_rules.generate(check_mode=True)

    return exit_code


# ---------------------------------------------------------------------------
# Tests: superseded ADR exclusion (using AREA scope fixture)
# ---------------------------------------------------------------------------

class TestGenRulesSuperseded(unittest.TestCase):
    """Rule IDs from superseded ADRs must be excluded (tested via AREA scope)."""

    def test_superseded_rule_id_absent(self):
        """HOK-OBSOLETE from a status=superseded ADR must not appear in output."""
        adrs = [_ACTIVE_ADR_AREA, _SUPERSEDED_ADR]
        exit_code, area_files, _ = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0, "generate() should exit 0")
        self.assertIn("hooks", area_files, "hooks.md should be generated (AREA scope)")
        self.assertNotIn(
            "HOK-OBSOLETE",
            area_files["hooks"],
            "Rule from superseded ADR must not appear in digest",
        )

    def test_superseded_by_rule_id_absent(self):
        """HOK-ALSO-OBSOLETE from an ADR with superseded_by must not appear."""
        adrs = [_ACTIVE_ADR_AREA, _SUPERSEDED_BY_ADR]
        exit_code, area_files, _ = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0)
        self.assertIn("hooks", area_files)
        self.assertNotIn(
            "HOK-ALSO-OBSOLETE",
            area_files["hooks"],
            "Rule from ADR with superseded_by must not appear in digest",
        )


# ---------------------------------------------------------------------------
# Tests: active rule IDs included (AREA scope)
# ---------------------------------------------------------------------------

class TestGenRulesCurrentIncluded(unittest.TestCase):
    """Rule IDs from non-superseded ADRs must be present in output."""

    def test_active_rule_ids_present_area_scope(self):
        """HOK-001 and HOK-002 from active AREA ADR must appear in rules file."""
        adrs = [_ACTIVE_ADR_AREA]
        exit_code, area_files, _ = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0)
        self.assertIn("hooks", area_files)
        content = area_files["hooks"]
        self.assertIn("HOK-001", content, "HOK-001 must appear in digest")
        self.assertIn("HOK-002", content, "HOK-002 must appear in digest")

    def test_generated_header_present_area_scope(self):
        """AREA output file must start with the DO-NOT-EDIT generated header."""
        adrs = [_ACTIVE_ADR_AREA]
        _, area_files, _ = _run_with_fixture(adrs)
        self.assertIn("hooks", area_files)
        self.assertIn(
            "GENERATED by tools/gen_rules.py",
            area_files["hooks"],
            "Generated header must be present in AREA scope file",
        )
        self.assertIn(
            "DO NOT EDIT",
            area_files["hooks"],
            "DO NOT EDIT warning must be present in AREA scope file",
        )

    def test_paths_frontmatter_present_for_area_scope(self):
        """AREA scope .claude/rules/<scope>.md must contain a paths: frontmatter key."""
        adrs = [_ACTIVE_ADR_AREA]
        _, area_files, _ = _run_with_fixture(adrs)
        self.assertIn("hooks", area_files)
        # The hooks scope has a declared paths: value in SCOPE_PATHS
        self.assertIn(
            "paths:",
            area_files["hooks"],
            "AREA scope rules file must contain paths: frontmatter key",
        )


# ---------------------------------------------------------------------------
# Tests: GLOBAL scope renders into CLAUDE.md
# ---------------------------------------------------------------------------

class TestGenRulesGlobalScope(unittest.TestCase):
    """GLOBAL scopes must render into CLAUDE.md generated-region blocks."""

    def test_global_scope_renders_to_claude_md(self):
        """GLOBAL scope (capture) renders into CLAUDE.md, not .claude/rules/."""
        adrs = [_ACTIVE_ADR_GLOBAL]
        exit_code, area_files, claude_content = _run_with_fixture(adrs)
        self.assertEqual(exit_code, 0)
        # GLOBAL scope must NOT produce a rules file
        self.assertNotIn(
            "capture",
            area_files,
            "GLOBAL scope must NOT render to .claude/rules/capture.md",
        )
        # GLOBAL scope must produce a CLAUDE.md region
        self.assertIn(
            "BEGIN GENERATED:rules:capture",
            claude_content,
            "GLOBAL scope must render into CLAUDE.md region markers",
        )
        self.assertIn(
            "CAP-001",
            claude_content,
            "CAP-001 must appear in CLAUDE.md global region",
        )

    def test_global_scope_region_has_end_marker(self):
        """GLOBAL scope region in CLAUDE.md must have both BEGIN and END markers."""
        adrs = [_ACTIVE_ADR_GLOBAL]
        _, _, claude_content = _run_with_fixture(adrs)
        self.assertIn("BEGIN GENERATED:rules:capture", claude_content)
        self.assertIn("END GENERATED:rules:capture", claude_content)


# ---------------------------------------------------------------------------
# Tests: SCOPE_TARGET classification
# ---------------------------------------------------------------------------

class TestScopeTargetMap(unittest.TestCase):
    """SCOPE_TARGET map must declare all 12 known scopes with correct target."""

    def test_scope_target_has_global_scopes(self):
        """Expected GLOBAL scopes must be declared."""
        global_scopes = [
            "pipeline", "capture", "commits", "critics",
            "verification", "regression", "output-contracts", "glossary",
        ]
        for scope in global_scopes:
            self.assertEqual(
                gen_rules.SCOPE_TARGET.get(scope),
                "global",
                f"scope '{scope}' must be 'global' in SCOPE_TARGET",
            )

    def test_scope_target_has_area_scopes(self):
        """Expected AREA scopes must be declared."""
        area_scopes = ["hooks", "isolation", "docs", "slicing"]
        for scope in area_scopes:
            self.assertEqual(
                gen_rules.SCOPE_TARGET.get(scope),
                "area",
                f"scope '{scope}' must be 'area' in SCOPE_TARGET",
            )

    def test_no_scope_is_both_global_and_area(self):
        """No scope appears in both GLOBAL and AREA classifications (ADR-0073 D1)."""
        global_scopes = {s for s, t in gen_rules.SCOPE_TARGET.items() if t == "global"}
        area_scopes = {s for s, t in gen_rules.SCOPE_TARGET.items() if t == "area"}
        overlap = global_scopes & area_scopes
        self.assertEqual(
            overlap, set(),
            f"Scopes must not be both global and area: {overlap}",
        )


# ---------------------------------------------------------------------------
# Tests: empty frontmatter (unchanged from #888)
# ---------------------------------------------------------------------------

class TestGenRulesEmptyFrontmatter(unittest.TestCase):
    """ADRs without frontmatter are skipped gracefully (no crash)."""

    def test_no_frontmatter_skipped(self):
        """An ADR without frontmatter should not crash generate()."""
        adrs = [_ACTIVE_ADR_AREA]
        exit_code, area_files, _ = _run_with_fixture(adrs)
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


# ---------------------------------------------------------------------------
# Tests: --check mode
# ---------------------------------------------------------------------------

class TestGenRulesCheckMode(unittest.TestCase):
    """--check mode detects stale/missing files and passes on clean tree."""

    def test_check_mode_fails_on_missing_area_file(self):
        """--check mode returns non-zero when .claude/rules/<scope>.md is absent."""
        adrs = [_ACTIVE_ADR_AREA]
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text("# placeholder\n", encoding="utf-8")
            # Do NOT create rules_dir — file is missing
            with (
                patch.object(gen_rules, "_load_adrs", return_value=adrs),
                patch.object(gen_rules, "RULES_DIR", rules_dir),
                patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
                patch.object(gen_rules, "CLAUDE_MD", claude_md),
            ):
                exit_code = gen_rules.generate(check_mode=True)
        self.assertEqual(exit_code, 1, "check_mode must return 1 when area file is missing")

    def test_check_mode_fails_on_missing_claude_md_region(self):
        """--check mode returns non-zero when CLAUDE.md region markers are absent."""
        adrs = [_ACTIVE_ADR_GLOBAL]
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            claude_md = Path(tmpdir) / "CLAUDE.md"
            # CLAUDE.md exists but has no generated regions
            claude_md.write_text("# No generated regions here\n", encoding="utf-8")
            with (
                patch.object(gen_rules, "_load_adrs", return_value=adrs),
                patch.object(gen_rules, "RULES_DIR", rules_dir),
                patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
                patch.object(gen_rules, "CLAUDE_MD", claude_md),
            ):
                exit_code = gen_rules.generate(check_mode=True)
        self.assertEqual(
            exit_code, 1,
            "check_mode must return 1 when CLAUDE.md global region is missing",
        )

    def test_check_mode_passes_on_clean_area_tree(self):
        """--check mode returns 0 when committed AREA files match fresh output."""
        exit_code = _run_check_with_fixture([_ACTIVE_ADR_AREA])
        self.assertEqual(exit_code, 0, "check_mode must return 0 on clean area tree")

    def test_check_mode_passes_on_clean_global_tree(self):
        """--check mode returns 0 when CLAUDE.md global regions match fresh output."""
        exit_code = _run_check_with_fixture([_ACTIVE_ADR_GLOBAL])
        self.assertEqual(exit_code, 0, "check_mode must return 0 on clean global tree")


# ---------------------------------------------------------------------------
# Tests: rule_id count guard (slice #938 addition)
# ---------------------------------------------------------------------------

class TestRuleIdCountGuard(unittest.TestCase):
    """_count_rule_ids correctly tallies across all scopes."""

    def test_count_sums_all_active_rule_ids(self):
        """Total rule_id count equals sum across all active scopes."""
        adrs = [_ACTIVE_ADR_AREA, _ACTIVE_ADR_GLOBAL]
        active = [a for a in adrs if not gen_rules._is_superseded(a)]
        scopes: dict = {}
        for a in active:
            scopes.setdefault(a["scope"], []).append(a)
        count = gen_rules._count_rule_ids(scopes)
        # 2 from HOK + 2 from CAP = 4
        self.assertEqual(count, 4, "count must sum all active rule_ids")

    def test_count_excludes_superseded(self):
        """Superseded ADRs must not contribute to rule_id count."""
        adrs = [_ACTIVE_ADR_AREA, _SUPERSEDED_ADR]
        active = [a for a in adrs if not gen_rules._is_superseded(a)]
        scopes: dict = {}
        for a in active:
            scopes.setdefault(a["scope"], []).append(a)
        count = gen_rules._count_rule_ids(scopes)
        self.assertEqual(count, 2, "count must not include superseded rule_ids")


# ---------------------------------------------------------------------------
# Integration tests: real ADR files
# ---------------------------------------------------------------------------

class TestGenRulesRealFrontmatter(unittest.TestCase):
    """Integration: real ADR files in decisions/ have frontmatter and produce output."""

    def test_real_adr_frontmatter_produces_output(self):
        """Running gen_rules --check against the real repo exits 0."""
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

    def test_hooks_area_scope_has_paths_frontmatter(self):
        """Real .claude/rules/hooks.md must exist and contain paths: frontmatter."""
        rules_file = _REPO_ROOT / ".claude" / "rules" / "hooks.md"
        self.assertTrue(
            rules_file.exists(),
            ".claude/rules/hooks.md must exist (AREA scope; run gen_rules.py first)",
        )
        content = rules_file.read_text(encoding="utf-8")
        self.assertIn(
            "paths:",
            content,
            ".claude/rules/hooks.md must contain paths: frontmatter key",
        )
        self.assertIn("HOK-001", content, "HOK-001 from ADR-0015 must be in hooks.md")

    def test_pipeline_global_scope_in_claude_md(self):
        """Real CLAUDE.md must contain the pipeline global-scope generated region."""
        claude_md = _REPO_ROOT / "CLAUDE.md"
        self.assertTrue(claude_md.exists(), "CLAUDE.md must exist")
        content = claude_md.read_text(encoding="utf-8")
        self.assertIn(
            "BEGIN GENERATED:rules:pipeline",
            content,
            "CLAUDE.md must contain the pipeline global-scope region marker",
        )
        self.assertIn(
            "PIP-001",
            content,
            "PIP-001 from pipeline global scope must appear in CLAUDE.md",
        )


if __name__ == "__main__":
    unittest.main()
