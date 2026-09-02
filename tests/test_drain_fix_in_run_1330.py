"""
tests/test_drain_fix_in_run_1330.py

Regression tests for PRD #1326 slice #1330 — the fix-in-run protocol
(ADR-0085 D5) that `.claude/skills/ship/SKILL.md`'s Queue-drain entry mode
D7 now documents, seen through the DRAIN-LEDGER health row that enforces it.

This file carries PRD §2 criterion 15's SECOND named FAIL leg: a `fix_queued`
that reaches the run's terminal record with neither a `fixed_in_run` nor a
`captured_ref` (the first leg — unknown record kind — landed with the row in
slice #1329's file).  The `parked`-terminal leg belongs to slice #1331, which
ships the park/resume emitting protocol.

The two PASS legs are not decoration: they assert that the exact record
sequences D7 tells the orchestrator to emit — land-in-run, and defer-with-a-
second-`fix_queued` — actually discharge the parity condition.  Without them a
row that FAILs every fix_queued would satisfy the FAIL assertion, and the
documented protocol could be one the check rejects.

The DRAIN-LEDGER condition set is deliberately NOT extended here: parity
landed in slice #1329 (`dashboard/health.py`).  This slice ships the emitting
protocol plus these tests.

Rule #21 / CRI-004: every ledger below is written under pytest's `tmp_path`
via the row's injectable `ledger_dir`; nothing is ever written into
`.claude/logs/drain/`.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)

import health  # noqa: E402  (path bootstrap must precede the import)

FIX = "fix:stale-grep-in-check-24"


def _run_with(*fix_records) -> list:
    """A well-formed bounded run with `fix_records` spliced in before run_end."""
    return [
        {"kind": "run_start", "ts": "2026-09-02T12:00:00Z",
         "run_id": "drain-fixrun-1",
         "counts": {"prd": 1, "slice": 4, "backlog": 67, "captured": 100},
         "open_prs": 1},
        {"kind": "triaged", "ts": "2026-09-02T12:00:01Z",
         "item": "issue:1400", "bucket": "autonomous", "lane": 1},
        {"kind": "item_start", "ts": "2026-09-02T12:00:02Z", "item": "issue:1400"},
        *fix_records,
        {"kind": "item_done", "ts": "2026-09-02T12:30:00Z", "item": "issue:1400"},
        {"kind": "run_end", "ts": "2026-09-02T12:30:01Z"},
    ]


def _check(tmp_path: Path, records: list) -> dict:
    path = tmp_path / "drain-fixrun-1.jsonl"
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    return health.check_drain_ledger(ledger_dir=str(tmp_path))


def test_drain_ledger_fails_on_unresolved_fix_queued(tmp_path):
    """FAIL leg (PRD §2 #15b): a queued fix escapes the run unaccounted for.

    ADR-0085 D5's whole point is that a trivial-lane discovery cannot be
    silently dropped: it either lands in-run or becomes a captured issue whose
    reference is pinned on the ledger before the terminal record.
    """
    result = _check(tmp_path, _run_with(
        {"kind": "fix_queued", "ts": "2026-09-02T12:10:00Z", "item": FIX},
    ))

    assert result["result"] == "FAIL", result["detail"]
    assert FIX in result["detail"]
    assert "no fixed_in_run" in result["detail"]
    assert "no captured_ref" in result["detail"]


def test_drain_ledger_passes_when_fix_lands_in_run(tmp_path):
    """PASS leg: D7 step 3 — the hotfix PR merged, `fixed_in_run` recorded."""
    result = _check(tmp_path, _run_with(
        {"kind": "fix_queued", "ts": "2026-09-02T12:10:00Z", "item": FIX},
        {"kind": "fixed_in_run", "ts": "2026-09-02T12:20:00Z",
         "item": FIX, "pr": 1401},
    ))

    assert result["result"] == "PASS", result["detail"]


def test_drain_ledger_passes_when_fix_deferred_with_captured_ref(tmp_path):
    """PASS leg: D7 step 4 — deferred, and the capture pinned before run_end.

    The ledger is append-only, so the reference arrives as a SECOND
    `fix_queued` record carrying the same handle plus `captured_ref`.  That is
    the shape D7 prescribes; this asserts the row accepts it.
    """
    result = _check(tmp_path, _run_with(
        {"kind": "fix_queued", "ts": "2026-09-02T12:10:00Z", "item": FIX},
        {"kind": "fix_queued", "ts": "2026-09-02T12:29:00Z",
         "item": FIX, "captured_ref": "issue:1402"},
    ))

    assert result["result"] == "PASS", result["detail"]
