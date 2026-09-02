"""
tests/test_drain_park_resume_1331.py

Regression tests for PRD #1326 slice #1331 — the park/resume protocol
(ADR-0085 D4) that `.claude/skills/ship/SKILL.md`'s Queue-drain entry mode D9
now documents, seen through the DRAIN-LEDGER health row that enforces it.

This file carries the two legs the earlier slices deliberately left to the one
that ships the emitting protocol:

  * the **empty remaining-items list** FAIL (condition 7, landed with the row
    in slice #1329) — PRD §2 criterion 14's last unexercised condition;
  * the **`parked`-terminal fix-queued interlock** (condition 6's park branch,
    named by slice #1330's file as belonging here) — a queued fix must not
    escape a run through the park path, so a park either names it in
    `remaining` or FAILs.

The PASS legs are load-bearing, not decoration: they assert that the exact
record sequence D9 prescribes — park naming the unlanded fix, `resumed`, then
the fix landing before `run_end` — is one the row accepts. A documented
protocol that the check rejects would be a defect in the pair, and without a
PASS control every FAIL assertion here is satisfied by a row that FAILs on
everything.

The DRAIN-LEDGER condition set is NOT extended by this slice: ADR-0085 D6
enumerates what the ledger owes, both conditions already exist in
`dashboard/health.py`, and a check may only FAIL a subject on an invariant
that subject owes (VER-009 / ADR-0083 D3).

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

ITEM = "issue:1400"
FIX = "fix:drain-park-handle"


def _prefix() -> list:
    """A run that has one queue item in flight and one fix queued."""
    return [
        {"kind": "run_start", "ts": "2026-09-02T14:00:00Z",
         "run_id": "drain-park-1",
         "counts": {"prd": 1, "slice": 4, "backlog": 67, "captured": 100},
         "open_prs": 1},
        {"kind": "triaged", "ts": "2026-09-02T14:00:01Z",
         "item": ITEM, "bucket": "autonomous", "lane": 1},
        {"kind": "item_start", "ts": "2026-09-02T14:00:02Z", "item": ITEM},
        {"kind": "fix_queued", "ts": "2026-09-02T14:05:00Z", "item": FIX},
    ]


def _check(tmp_path: Path, records: list) -> dict:
    path = tmp_path / "drain-park-1.jsonl"
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    return health.check_drain_ledger(ledger_dir=str(tmp_path))


def test_drain_ledger_fails_on_empty_parked_remaining(tmp_path):
    """FAIL leg (PRD §2 #14, condition 7): a park that names nothing.

    D9 makes the two terminals non-interchangeable: a run with nothing left to
    do writes `run_end`. A `parked` record carrying an empty list claims the
    run was interrupted while recording no way to pick it back up — the
    resumable-state property the ledger exists for, asserted but not delivered.
    """
    records = _prefix() + [
        {"kind": "parked", "ts": "2026-09-02T14:30:00Z", "remaining": []},
    ]

    result = _check(tmp_path, records)

    assert result["result"] == "FAIL", result["detail"]
    assert "empty remaining-items list" in result["detail"]
    assert "resume order" in result["detail"]


def test_drain_ledger_fails_when_fix_escapes_through_the_park(tmp_path):
    """FAIL leg (ADR-0085 D4/D6): an unlanded fix omitted from `remaining`.

    The park path is the gap the fix-in-run parity window was widened to
    close: a run that parks and never reaches `run_end` would otherwise let a
    queued fix vanish between the two terminals. Naming a queue item in
    `remaining` does not discharge a *fix* that is missing from it.
    """
    records = _prefix() + [
        {"kind": "parked", "ts": "2026-09-02T14:30:00Z",
         "remaining": [ITEM]},
    ]

    result = _check(tmp_path, records)

    assert result["result"] == "FAIL", result["detail"]
    assert FIX in result["detail"]
    assert "no place in the remaining list" in result["detail"]


def test_drain_ledger_passes_when_park_names_the_unlanded_fix(tmp_path):
    """PASS leg: D9 step 2 — `remaining` carries the queue item AND the fix.

    This is the record shape D9 tells the orchestrator to emit at a park, so
    the row must accept it; it is also the control that makes the FAIL leg
    above mean "the fix was missing" rather than "parks always FAIL".
    """
    records = _prefix() + [
        {"kind": "parked", "ts": "2026-09-02T14:30:00Z",
         "remaining": [ITEM, FIX]},
    ]

    result = _check(tmp_path, records)

    assert result["result"] == "PASS", result["detail"]


def test_drain_ledger_passes_on_park_then_resume_then_land(tmp_path):
    """PASS leg: the full D9 lifecycle in ONE ledger file.

    Resume does not open a new ledger — the resumed run appends `resumed` to
    the parked run's own file and works `remaining` in the recorded order.
    This pins that the row reads such a file as one coherent run rather than
    tripping over its second terminal.
    """
    records = _prefix() + [
        {"kind": "parked", "ts": "2026-09-02T14:30:00Z",
         "remaining": [ITEM, FIX]},
        {"kind": "resumed", "ts": "2026-09-03T09:00:00Z"},
        {"kind": "fixed_in_run", "ts": "2026-09-03T09:20:00Z",
         "item": FIX, "pr": 1403},
        {"kind": "item_done", "ts": "2026-09-03T09:40:00Z", "item": ITEM},
        {"kind": "run_end", "ts": "2026-09-03T09:40:01Z"},
    ]

    result = _check(tmp_path, records)

    assert result["result"] == "PASS", result["detail"]


def test_drain_ledger_fails_when_resumed_run_ends_with_the_fix_unlanded(
        tmp_path):
    """FAIL leg: a park defers a fix, it does not discharge one.

    Being named in `remaining` clears the parity assertion only at that park.
    If the resumed run reaches `run_end` with the fix still neither landed nor
    captured, the deferral was never honoured — and the run's real terminal
    says so.
    """
    records = _prefix() + [
        {"kind": "parked", "ts": "2026-09-02T14:30:00Z",
         "remaining": [ITEM, FIX]},
        {"kind": "resumed", "ts": "2026-09-03T09:00:00Z"},
        {"kind": "item_done", "ts": "2026-09-03T09:40:00Z", "item": ITEM},
        {"kind": "run_end", "ts": "2026-09-03T09:40:01Z"},
    ]

    result = _check(tmp_path, records)

    assert result["result"] == "FAIL", result["detail"]
    assert FIX in result["detail"]
    assert "no fixed_in_run" in result["detail"]
