"""
tests/test_drain_schema_parity_1347.py

Captured issue #1347 (codebase-critic RECOMMEND R2 from the PRD #1326 pass):
the closed drain-ledger record schema is stated four times independently —
ADR-0085 D4, the `/ship` SKILL.md kind table, `dashboard/health.py`'s
`_DRAIN_KINDS` / `_DRAIN_REQUIRED_FIELDS`, and the generated PIP-028 rule text.
Nothing mechanically tied them together, so the next schema change would have
left at least one copy behind (a rule-#9 divergence).

This file makes `health.py` the machine-checkable source and the SKILL.md table
a *verified view* of it: the table is parsed and compared against
`_DRAIN_REQUIRED_FIELDS` in both directions — no kind and no required field may
exist in one statement and be missing from the other.

The other two copies are deliberately out of scope: the ADR is an immutable
decision record, and the PIP-028 text regenerates from ADR frontmatter via
`tools/gen_rules.py`.

Parsing contract: the table is located by its section *title* and its own
header row rather than by a heading id, so a renumbering like PR #1359's
`### D8` -> `### QD8` does not red the suite, while an actually-missing or
relocated table does. Prose around the table may reflow freely; the kind and
field cells are read strictly. Parenthetical annotations inside a fields cell
(`counts` (`prd`/`slice`/...), `(+ `captured_ref` when deferred)`) qualify the
field rather than adding one, so they are stripped before field extraction.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)

import health  # noqa: E402  (path bootstrap must precede the import)

SKILL_PATH = REPO_ROOT / ".claude" / "skills" / "ship" / "SKILL.md"

# Heading that owns the table, matched on its title and not its id.
_SECTION_RE = re.compile(
    r"^###\s+\S+\s+Ledger write protocol\s*$", re.MULTILINE
)
_NEXT_HEADING_RE = re.compile(r"^###\s", re.MULTILINE)
# The table's own header row: "| Kind | Required fields beyond `kind` | ... |".
_TABLE_HEADER_RE = re.compile(
    r"^\|\s*Kind\s*\|\s*Required fields[^|]*\|", re.MULTILINE
)
_BACKTICKED_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")
_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")


def _section_text() -> str:
    """The `Ledger write protocol` section body of the /ship SKILL.md."""
    text = SKILL_PATH.read_text(encoding="utf-8")
    starts = list(_SECTION_RE.finditer(text))
    assert len(starts) == 1, (
        f"expected exactly 1 'Ledger write protocol' heading in {SKILL_PATH}, "
        f"found {len(starts)} — the drain kind table moved or was renamed"
    )
    body_start = starts[0].end()
    nxt = _NEXT_HEADING_RE.search(text, body_start)
    return text[body_start:nxt.start() if nxt else len(text)]


def _parse_skill_table() -> dict:
    """Parse the SKILL.md drain kind table into {kind: set(required fields)}."""
    section = _section_text()
    header = _TABLE_HEADER_RE.search(section)
    assert header, (
        "no '| Kind | Required fields ... |' table header found in the "
        f"'Ledger write protocol' section of {SKILL_PATH}"
    )

    parsed: dict = {}
    rows_start = section.find("\n", header.end()) + 1  # skip the header row
    for line in section[rows_start:].splitlines():
        line = line.strip()
        if not line.startswith("|"):
            break  # table ends at the first non-row line
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("- :"):
            continue  # the |---|---| separator row
        # A cell may name several kinds at once ("`item_start` / `item_done`").
        kinds = _BACKTICKED_RE.findall(cells[0])
        assert kinds, f"table row names no kind in backticks: {line!r}"
        fields = set(
            _BACKTICKED_RE.findall(_PARENTHETICAL_RE.sub("", cells[1]))
        )
        for kind in kinds:
            assert kind not in parsed, f"kind `{kind}` listed twice in the table"
            parsed[kind] = fields
    assert parsed, "the drain kind table was found but parsed to zero rows"
    return parsed


def test_skill_table_kinds_match_health_required_fields():
    """Every kind is in both the SKILL.md table and `_DRAIN_REQUIRED_FIELDS`."""
    documented = set(_parse_skill_table())
    implemented = set(health._DRAIN_REQUIRED_FIELDS)
    assert documented == implemented, (
        "drain kind set diverged: "
        f"in SKILL.md only={sorted(documented - implemented)}, "
        f"in health._DRAIN_REQUIRED_FIELDS only={sorted(implemented - documented)}"
    )


def test_skill_table_fields_match_health_required_fields():
    """Per kind, the documented required fields match the implemented ones."""
    documented = _parse_skill_table()
    divergences = []
    for kind, fields in sorted(documented.items()):
        implemented = set(health._DRAIN_REQUIRED_FIELDS.get(kind, ()))
        if fields != implemented:
            divergences.append(
                f"`{kind}`: in SKILL.md only={sorted(fields - implemented)}, "
                f"in health only={sorted(implemented - fields)}"
            )
    assert not divergences, (
        "drain required-field sets diverged between the /ship SKILL.md table "
        "and health._DRAIN_REQUIRED_FIELDS: " + "; ".join(divergences)
    )
