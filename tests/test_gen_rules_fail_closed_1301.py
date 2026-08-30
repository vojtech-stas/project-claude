"""
Regression test for issue #1301 — gen_rules.py must fail CLOSED (non-zero
exit) when the active-ADR set is empty, instead of the prior fail-OPEN
behavior (exit 0) that let the generated 86-rule enforcement layer silently
vanish while CI stayed green.

Root cause (per #1301): `decisions/` missing, unreadable, or all frontmatter
filtered out (e.g. via a bad partial clone / sparse checkout / vendored copy)
left `active_adrs` empty; the early-return at the top of `generate()` printed
a warning to stderr but returned 0 — success — bypassing the one guard
(`total_rule_ids != RULE_IDS_BASELINE`) designed to catch exactly this,
because that guard lives inside the `if check_mode:` block *after* the
early return.

This test is distinct from tests/test_gen_rules_888.py's `TestGenRulesEmptyFrontmatter`
suite (which covers a single ADR without frontmatter being *skipped*, not
the *entire active set* being empty) and distinct from issue #1175's
YAML-shape fail-open path (not touched here).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_gen_rules_fail_closed_1301.py -v
"""

import sys
import unittest
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


class TestGenRulesFailsClosedOnEmptyActiveSet(unittest.TestCase):
    """generate() must exit non-zero when active_adrs is empty (#1301)."""

    def test_empty_adr_list_exits_nonzero(self):
        """No ADRs discovered at all (e.g. decisions/ missing/unreadable)."""
        with patch.object(gen_rules, "_load_adrs", return_value=[]):
            exit_code = gen_rules.generate(check_mode=False)
        self.assertNotEqual(
            exit_code, 0,
            "generate() must fail loud (non-zero) when zero active ADRs "
            "are discovered, not silently report success (#1301)",
        )

    def test_all_superseded_exits_nonzero(self):
        """ADRs exist but every single one is superseded (active set empty)."""
        all_superseded = [
            {
                "path": Path("/fake/decisions/0001-old.md"),
                "id": "ADR-0001",
                "status": "superseded",
                "supersedes": [],
                "superseded_by": ["ADR-0002"],
                "scope": "hooks",
                "rule_ids": ["HOK-999"],
            },
        ]
        with patch.object(gen_rules, "_load_adrs", return_value=all_superseded):
            exit_code = gen_rules.generate(check_mode=False)
        self.assertNotEqual(
            exit_code, 0,
            "generate() must fail loud when the active-ADR set is empty "
            "even if superseded ADRs exist (#1301)",
        )

    def test_empty_adr_list_exits_nonzero_in_check_mode(self):
        """--check mode must also fail closed on an empty active-ADR set."""
        with patch.object(gen_rules, "_load_adrs", return_value=[]):
            exit_code = gen_rules.generate(check_mode=True)
        self.assertNotEqual(
            exit_code, 0,
            "generate(check_mode=True) must fail loud on an empty "
            "active-ADR set (#1301)",
        )

    def test_healthy_run_is_unaffected(self):
        """A normal, non-empty active-ADR set must still exit 0 (no regression)."""
        healthy_adr = {
            "path": Path("/fake/decisions/0015-hooks.md"),
            "id": "ADR-0015",
            "status": "accepted",
            "supersedes": [],
            "superseded_by": [],
            "scope": "hooks",
            "rule_ids": ["HOK-001"],
        }
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            rules_dir = Path(tmpdir) / ".claude" / "rules"
            rules_dir.mkdir(parents=True, exist_ok=True)
            claude_md = Path(tmpdir) / "CLAUDE.md"
            claude_md.write_text(
                "# placeholder\n\n@.claude/generated/_global.md\n",
                encoding="utf-8",
            )
            global_rules_file = rules_dir / "_global.md"
            with (
                patch.object(gen_rules, "_load_adrs", return_value=[healthy_adr]),
                patch.object(gen_rules, "RULES_DIR", rules_dir),
                patch.object(gen_rules, "REPO_ROOT", Path(tmpdir)),
                patch.object(gen_rules, "CLAUDE_MD", claude_md),
                patch.object(gen_rules, "GLOBAL_RULES_FILE", global_rules_file),
            ):
                exit_code = gen_rules.generate(check_mode=False)
        self.assertEqual(
            exit_code, 0,
            "A healthy run with a non-empty active-ADR set must still exit 0",
        )

    def test_real_repo_active_adr_set_is_nonempty(self):
        """Sanity: the real repo's active-ADR set must never be empty (86 rules)."""
        adrs = gen_rules._load_adrs()
        active_adrs = [a for a in adrs if not gen_rules._is_superseded(a)]
        self.assertGreater(
            len(active_adrs), 0,
            "Real repo must have a non-empty active-ADR set",
        )


if __name__ == "__main__":
    unittest.main()
