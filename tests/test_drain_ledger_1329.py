"""
tests/test_drain_ledger_1329.py

Regression tests for PRD #1326 slice #1329 — the DRAIN-LEDGER health row
(ADR-0085 D6), which validates the newest `/ship` queue-drain run ledger
offline, from the ledger file alone.

Scope of THIS file, per the slicer-critic's finding 4 amendment: the row must
not land with zero FAIL-leg coverage (a fresh instance of the guards-that-lie
class — ADR-0083 D3). So the mandatory leg here is the **unknown-record-kind
FAIL**, plus the PASS control that makes it meaningful (without the control, a
FAIL assertion is satisfied by a row that FAILs on everything), plus the
no-ledger WARN leg that also proves the ledger path is genuinely injectable.

PRD §2 criterion 15's remaining FAIL legs (fix-queued parity, parked) are
deliberately NOT here — the slicer-critic assigned them to the follow-up
slices that ship the emitting protocols. The one exception is the #1335
regression leg below: it does not test the parked *protocol*, it pins that a
malformed `remaining` list reports a named FAIL instead of crashing the row.

Rule #21 / CRI-004: every ledger in this file is written under pytest's
`tmp_path`, never into `.claude/logs/drain/`. That is the reason
`check_drain_ledger()` takes an injectable directory at all.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)

import health  # noqa: E402  (path bootstrap must precede the import)


def _write_ledger(directory: Path, name: str, records: list) -> Path:
    """Write a JSONL ledger of `records` into `directory` (tmp_path only)."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    return path


def _valid_run() -> list:
    """A minimal well-formed bounded drain run: one item, full lifecycle."""
    return [
        {"kind": "run_start", "ts": "2026-09-02T10:00:00Z",
         "run_id": "drain-test-1",
         "counts": {"prd": 2, "slice": 6, "backlog": 72, "captured": 96},
         "open_prs": 1},
        {"kind": "triaged", "ts": "2026-09-02T10:00:01Z",
         "item": "issue:1337", "bucket": "autonomous", "lane": 1},
        {"kind": "item_start", "ts": "2026-09-02T10:00:02Z", "item": "issue:1337"},
        {"kind": "item_done", "ts": "2026-09-02T10:20:00Z", "item": "issue:1337"},
        {"kind": "run_end", "ts": "2026-09-02T10:20:01Z"},
    ]


def test_drain_ledger_pass_on_well_formed_run(tmp_path):
    """PASS control: a well-formed bounded run satisfies all seven conditions."""
    _write_ledger(tmp_path, "drain-test-1.jsonl", _valid_run())

    result = health.check_drain_ledger(ledger_dir=str(tmp_path))

    assert result["id"] == "DRAIN-LEDGER"
    assert result["result"] == "PASS", result["detail"]
    # The prose detail is the operator-facing surface (no JSON mode — #1324).
    assert "5 records valid" in result["detail"]


def test_drain_ledger_fails_on_unknown_record_kind(tmp_path):
    """FAIL leg (mandatory, slicer-critic finding 4): kind outside the closed set.

    ADR-0085 D4 closes the kind set; an unrecognized kind must be a named
    FAIL, never a silent skip — otherwise a drain emitting a typo'd or
    invented kind would record state the row happily blesses.
    """
    records = _valid_run()
    # Insert a kind that is NOT in the ADR-0085 D4 closed set.
    records.insert(2, {"kind": "lane", "ts": "2026-09-02T10:00:01Z", "lane": 1})
    _write_ledger(tmp_path, "drain-test-1.jsonl", records)

    result = health.check_drain_ledger(ledger_dir=str(tmp_path))

    assert result["result"] == "FAIL", result["detail"]
    assert "'lane'" in result["detail"]
    assert "outside the closed set" in result["detail"]


def test_drain_ledger_fails_on_object_shaped_remaining_entry(tmp_path):
    """FAIL leg (#1335 regression rider): `remaining` holding an object.

    The ledger schema documents `remaining` as a list of item ids. A
    malformed writer emitting objects there used to reach `set(remaining)`
    and raise an uncaught `TypeError: unhashable type: 'dict'`, so the row
    returned a traceback instead of a verdict. A guard states its
    observation rather than crashing (ADR-0083 D5 / VER-009), so the honest
    result is a named schema FAIL.
    """
    records = _valid_run()[:-1]   # park is this run's terminal, not run_end
    records.append({
        "kind": "parked", "ts": "2026-09-02T10:20:01Z",
        "remaining": [{"item": "issue:1338"}, "issue:1339"],
    })
    _write_ledger(tmp_path, "drain-test-1.jsonl", records)

    result = health.check_drain_ledger(ledger_dir=str(tmp_path))

    assert result["result"] == "FAIL", result["detail"]
    assert "non-string remaining entries" in result["detail"]
    # The FAIL names the offending entry, not merely the record kind.
    assert "issue:1338" in result["detail"]


def test_drain_ledger_warns_when_no_ledger_present(tmp_path):
    """Absence is WARN, not FAIL — and the path is genuinely injectable.

    A drain may simply never have run in this environment (a fresh clone, or
    CI). Failing there would be a guard asserting an invariant nothing owes.
    """
    empty = tmp_path / "no-drain-here"
    empty.mkdir()

    result = health.check_drain_ledger(ledger_dir=str(empty))

    assert result["result"] == "WARN", result["detail"]
    # Proof the injected path was the one consulted (rule #21: not .claude/logs).
    assert str(empty) in result["detail"]
    assert ".claude" not in result["detail"]
