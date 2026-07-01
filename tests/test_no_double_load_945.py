"""
Regression test for slice #945 — _global.md / _repo-map.md double-load.

PRD #937 slice #940 put the generated global rules in
.claude/rules/_global.md and @imported it from CLAUDE.md.  But every file
directly inside .claude/rules/ that lacks a `paths:` frontmatter key is
ALSO auto-loaded unconditionally by Claude Code every session (that is the
whole point of the .claude/rules/ auto-load mechanism AREA scopes rely on
via their `paths:` key to scope the load down).  Because _global.md and
_repo-map.md carry no `paths:` key, they load twice: once as an
unconditional .claude/rules/ file, and once via the explicit CLAUDE.md
@import line — wasting context tokens (ADR-0073 D1: "a scope is EITHER
global OR area — never both (no double-load)").

This test asserts the fix's invariant directly: no file that CLAUDE.md
@imports may also live in a path that Claude Code auto-loads unconditionally
(i.e. directly inside .claude/rules/ without a `paths:` frontmatter key).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_no_double_load_945.py -v
"""

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_RULES_DIR = _REPO_ROOT / ".claude" / "rules"
_CLAUDE_MD = _REPO_ROOT / "CLAUDE.md"

_IMPORT_RE = re.compile(r"^@(\..+\.md)\s*$", re.MULTILINE)


def _claude_md_import_targets() -> list[str]:
    """Return the list of @import-ed relative paths found in CLAUDE.md."""
    if not _CLAUDE_MD.exists():
        return []
    content = _CLAUDE_MD.read_text(encoding="utf-8", errors="replace")
    return _IMPORT_RE.findall(content)


def _has_paths_frontmatter(file_path: Path) -> bool:
    """Return True if the file's first two lines declare a paths: key."""
    if not file_path.exists():
        return False
    text = file_path.read_text(encoding="utf-8", errors="replace")
    # paths: appears on one of the first few lines (after the generated header)
    for line in text.splitlines()[:5]:
        if line.strip().startswith("paths:"):
            return True
    return False


class TestNoDoubleLoad(unittest.TestCase):
    """CLAUDE.md-@imported files must NOT also sit in an unconditionally
    auto-loaded location (directly in .claude/rules/ with no paths: key)."""

    def test_claude_md_imports_at_least_one_file(self):
        """Sanity: CLAUDE.md must actually @import something (or this test
        would pass vacuously)."""
        targets = _claude_md_import_targets()
        self.assertGreater(
            len(targets), 0,
            "CLAUDE.md must contain at least one @import line for this "
            "test to be meaningful",
        )

    def test_no_imported_file_is_also_unconditionally_autoloaded(self):
        """
        For every @import target in CLAUDE.md, the imported file must NOT
        resolve to a path directly inside .claude/rules/ lacking a paths:
        frontmatter key — that combination is exactly the double-load bug
        (auto-loaded AND @imported).
        """
        targets = _claude_md_import_targets()
        offenders = []
        for target in targets:
            resolved = (_REPO_ROOT / target.lstrip("./")).resolve()
            try:
                resolved.relative_to((_RULES_DIR).resolve())
            except ValueError:
                # Not inside .claude/rules/ at all — cannot double-load
                # via the rules auto-load mechanism.
                continue
            # It IS inside .claude/rules/ — only safe if it declares paths:
            # (making Claude Code load it conditionally, not unconditionally).
            if not _has_paths_frontmatter(resolved):
                offenders.append(target)

        self.assertEqual(
            offenders, [],
            f"@import target(s) {offenders} sit directly in .claude/rules/ "
            "WITHOUT a paths: frontmatter key — they are both "
            "unconditionally auto-loaded by Claude Code AND explicitly "
            "@imported by CLAUDE.md (double-load, ADR-0073 D1 violation). "
            "Move the generator output to a non-auto-loaded location "
            "(e.g. .claude/generated/) so the @import is the sole load path.",
        )

    def test_global_md_not_directly_in_rules_dir(self):
        """_global.md specifically must not live directly in .claude/rules/
        (the historical location of the #945 bug)."""
        offender = _RULES_DIR / "_global.md"
        self.assertFalse(
            offender.exists(),
            f"{offender.relative_to(_REPO_ROOT)} must not exist — "
            "_global.md must be relocated out of the unconditionally "
            "auto-loaded .claude/rules/ directory (slice #945)",
        )

    def test_repo_map_md_not_directly_in_rules_dir(self):
        """_repo-map.md specifically must not live directly in
        .claude/rules/ (the historical location of the #945 bug)."""
        offender = _RULES_DIR / "_repo-map.md"
        self.assertFalse(
            offender.exists(),
            f"{offender.relative_to(_REPO_ROOT)} must not exist — "
            "_repo-map.md must be relocated out of the unconditionally "
            "auto-loaded .claude/rules/ directory (slice #945)",
        )


if __name__ == "__main__":
    unittest.main()
