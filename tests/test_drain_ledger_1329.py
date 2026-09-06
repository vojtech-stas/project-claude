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
slices that ship the emitting protocols. The exceptions are the malformed-shape
regression legs below: they do not test the parked *protocol*, they pin that a
value violating the documented record schema reports a named FAIL instead of
crashing the row or passing it vacuously. Three of them cover `remaining` — a
list holding objects (#1335), or a value that is not a list at all (#1339) —
and a fourth pins that the FAIL quotes such a value in BOUNDED form (#1342):
naming the malformed shape is the observation, pasting all of it is noise.
The last walks that same class one layer deeper, over every required field the
row consumes as an IDENTITY: `kind`, `item` on all six kinds that carry it, and
`escalated`'s `label`. All but one of those are identities because they are
hashed; `escalated`'s `item` rides a second rationale — it is the sole thing
naming WHICH item escalated in that condition's two FAIL messages, so an
unvalidated one garbles the finding rather than crashing the row (#1356).

A final table (#1372) drives the four sequence-pass messages that name an item
id — condition 3's two escalated legs, which had no covering test at all, plus
the triage-precedence and fix-queued messages, which still quoted their
identifier unbounded — asserting the message lands and the identifier arrives
in `_drain_repr` form. Like the legs above it, it exercises those messages,
not the emitting protocols the follow-up slices own.

Rule #21 / CRI-004: every ledger in this file is written under pytest's
`tmp_path`, never into `.claude/logs/drain/`. That is the reason
`check_drain_ledger()` takes an injectable directory at all.
"""

import json
import sys
from pathlib import Path

try:
    import pytest
except ImportError:  # CI runs stdlib unittest without pytest (CHECK 12 / #985)
    pytest = None

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


def test_drain_ledger_fails_on_object_shaped_remaining_field(tmp_path):
    """FAIL leg (#1339 regression rider): `remaining` is a JSON object.

    A truthy non-list `remaining` clears the empty-list condition yet yields
    an empty parity set, so the fix-queued interlock would compare against
    nothing and PASS a ledger it never actually read. Silent degradation is
    the class VER-009 forbids: the shape violates the documented schema, so
    it owes the same named schema FAIL as a malformed list entry (#1335).
    """
    records = _valid_run()[:-1]   # park is this run's terminal, not run_end
    records.append({
        "kind": "parked", "ts": "2026-09-02T10:20:01Z",
        "remaining": {"next": "issue:1338"},
    })
    _write_ledger(tmp_path, "drain-test-1.jsonl", records)

    result = health.check_drain_ledger(ledger_dir=str(tmp_path))

    assert result["result"] == "FAIL", result["detail"]
    assert "non-list remaining field" in result["detail"]
    # The FAIL quotes the malformed value, not merely the record kind.
    assert "issue:1338" in result["detail"]


def test_drain_ledger_fails_on_bare_string_remaining_field(tmp_path):
    """FAIL leg (#1339 regression rider): `remaining` is a bare string.

    The second non-list shape, and the quieter one: a string is iterable, so
    a future reader could silently take its characters for item ids. The row
    reports the observation instead (ADR-0083 D5).
    """
    records = _valid_run()[:-1]
    records.append({
        "kind": "parked", "ts": "2026-09-02T10:20:01Z",
        "remaining": "issue:1338",
    })
    _write_ledger(tmp_path, "drain-test-1.jsonl", records)

    result = health.check_drain_ledger(ledger_dir=str(tmp_path))

    assert result["result"] == "FAIL", result["detail"]
    assert "non-list remaining field" in result["detail"]
    assert "issue:1338" in result["detail"]


def test_drain_ledger_bounds_the_quoted_malformed_value(tmp_path):
    """#1342: the FAIL quotes a malformed value without pasting all of it.

    A guard states its observation (VER-009 / ADR-0083 D5), and the whole of
    an arbitrarily large malformed value is not the observation — it is the
    finding's own noise, drowning the four other failures the detail string
    can carry. The row already bounds the sibling list-entry guard to the
    first offender; every malformed value it quotes owes the same restraint.
    """
    records = _valid_run()[:-1]   # park is this run's terminal, not run_end
    records.append({
        "kind": "parked", "ts": "2026-09-02T10:20:01Z",
        "remaining": {f"key{n}": f"issue:{2000 + n}" for n in range(40)},
    })
    _write_ledger(tmp_path, "drain-test-1.jsonl", records)

    result = health.check_drain_ledger(ledger_dir=str(tmp_path))

    assert result["result"] == "FAIL", result["detail"]
    # The observation still lands, and the first of the payload identifies it.
    assert "non-list remaining field" in result["detail"]
    assert "issue:2000" in result["detail"]
    # ...but the tail of a ~1000-char malformed value never reaches the row.
    assert "issue:2039" not in result["detail"], result["detail"]
    assert len(result["detail"]) < 300, len(result["detail"])


def _identity_cases() -> list:
    """Every malformed-identity shape the row must NAME rather than crash on.

    Each entry is (label, records, expected-detail fragments). The class is
    "an unvalidated JSON value reaches a hash-requiring operation": a set
    `add`/`discard`, a `in`-test against a set, or a dict-key assignment. A
    dict- or list-valued field there raises `TypeError: unhashable type`,
    which replaces the row's verdict with a traceback and reds the CI gate
    that delegates to it — the #1335/#1339 defect, one layer deeper.

    The table walks EVERY kind that carries `item`, plus the two other
    identity fields the row consumes the same way: the universal `kind`
    (looked up in the closed set) and `escalated`'s `label` (looked up in the
    allowed-label set). One row rides a SECOND rationale rather than the hash
    one: `escalated`'s `item` is only formatted, into the escalated failures,
    where it is the sole thing naming which item escalated — unvalidated it
    either garbles that finding or, behind a well-formed `label`, raises
    nothing at all (#1356). Fields the row only checks for presence —
    `open_prs`, `bucket`, `lane`, `pr` — are deliberately absent: they reach
    neither use, so failing them would be an invariant nothing owes (VER-009).
    """
    def base() -> list:
        return _valid_run()

    def with_record(rec, index=None) -> list:
        records = base()
        records.insert(len(records) - 1 if index is None else index, rec)
        return records

    def mutated(index, field, value) -> list:
        records = base()
        records[index] = dict(records[index], **{field: value})
        return records

    ident = ("must be a non-empty string",)
    return [
        # The universal field, hashed against the closed kind set.
        ("kind is a list",
         with_record({"kind": ["triaged"], "ts": "2026-09-02T10:00:01Z"}, 1),
         ("outside the closed set",)),
        # Every kind that carries `item`.
        ("triaged.item is an object",
         mutated(1, "item", {"n": 1337}), ident + ("`item`",)),
        ("triaged.item is an empty string",
         mutated(1, "item", ""), ident + ("`item`",)),
        ("item_start.item is a list",
         mutated(2, "item", ["issue:1337"]), ident + ("`item`",)),
        ("item_done.item is an object",
         mutated(3, "item", {"n": 1337}), ident + ("`item`",)),
        ("escalated.item is an object",
         with_record({"kind": "escalated", "ts": "2026-09-02T10:10:00Z",
                      "item": {"n": 1337}, "label": "needs-human-check",
                      "label_applied": True}),
         ident + ("`item`",)),
        ("escalated.label is an object",
         with_record({"kind": "escalated", "ts": "2026-09-02T10:10:00Z",
                      "item": "issue:1341", "label": {"name": "needs-human"},
                      "label_applied": True}),
         ident + ("`label`",)),
        ("fix_queued.item is an object",
         with_record({"kind": "fix_queued", "ts": "2026-09-02T10:10:00Z",
                      "item": {"handle": "fix:x"}}),
         ident + ("`item`",)),
        ("fixed_in_run.item is a list",
         with_record({"kind": "fixed_in_run", "ts": "2026-09-02T10:10:00Z",
                      "item": ["fix:x"], "pr": 1342}),
         ident + ("`item`",)),
    ]


def test_drain_ledger_names_malformed_identity_fields(tmp_path):
    """FAIL legs: an unhashable identity field is a named FAIL, not a crash.

    `check_drain_ledger` fed `rec.get("item")` straight into `set.add`,
    `set.discard`, a set membership test and a dict-key assignment, and did
    the same with `kind` and `escalated`'s `label`. A drain writer emitting a
    structured value in any of those positions therefore did not get a
    verdict — it got `TypeError: unhashable type`, an empty stdout and a red
    CI gate with nothing naming the offending record.

    A guard states its observation instead of crashing (ADR-0083 D5 /
    VER-009), so each shape below owes the same named schema FAIL the
    malformed-`remaining` legs above established. Every case is collected
    rather than asserted in place: before the guard, the first one aborts the
    loop, and the report should list the whole class, not its first member.
    """
    problems = []
    for label, records, fragments in _identity_cases():
        case_dir = tmp_path / label.replace(" ", "-").replace(".", "-")
        try:
            _write_ledger(case_dir, "drain-test-1.jsonl", records)
            result = health.check_drain_ledger(ledger_dir=str(case_dir))
        except Exception as exc:   # noqa: BLE001 — a crash IS the finding
            problems.append(f"{label}: crashed ({type(exc).__name__}: {exc})")
            continue
        if result["result"] != "FAIL":
            problems.append(
                f"{label}: {result['result']} — {result['detail']}")
            continue
        for fragment in fragments:
            if fragment not in result["detail"]:
                problems.append(
                    f"{label}: FAIL detail lacks {fragment!r} — "
                    f"{result['detail']}")

    assert not problems, "; ".join(problems)


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


# ---------------------------------------------------------------------------
# #1372: every identifier the sequence pass quotes, quoted in BOUNDED form
# ---------------------------------------------------------------------------
_TAIL_MARKER = "-tail-that-must-not-survive"


def _overlong(prefix: str) -> str:
    """A value whose `repr` exceeds `_drain_repr`'s limit, ending in a marker.

    The marker is what makes the bound checkable without restating the limit
    here: if the row pastes the whole value, the marker reaches the detail
    string; if it bounds the value, the marker cannot. The self-check pins
    that the value really is over-long, so a later limit change surfaces as a
    loud failure rather than a silently vacuous assertion.
    """
    value = prefix + "x" * 90 + _TAIL_MARKER
    assert health._drain_repr(value) != repr(value), (
        f"{prefix!r} case is too short to exercise the bound")
    return value


def _bounded_message_cases() -> list:
    """(id, records, fragments, over-long value) per identifier-quoting FAIL.

    One case per sequence-pass FAIL message that names an item id, so the
    class is covered rather than its first member. Two duties meet here.
    Condition 3's two `escalated` legs — a `label` outside the closed set, a
    `label_applied` that is not true — had no covering test at all, so
    ADR-0085 D6's recorded-escalation condition was enforced only in
    principle, and the bound already on those two messages was never
    exercised. The triage-precedence and fix-queued legs are the #1342
    bound's remaining gaps: they quoted their identifier with a bare `!r`,
    pasting an arbitrarily large one whole into the operator-facing detail.

    The expected label set and the expected rendering are re-derived from the
    module under test, never restated, so this table cannot drift away from
    the code the way a copied constant would.
    """
    long_label = _overlong("not-a-real-escalation-label")
    assert long_label not in health._DRAIN_ESCALATION_LABELS, (
        "the bad-label case must sit OUTSIDE the closed set it probes")
    allowed_label = sorted(health._DRAIN_ESCALATION_LABELS)[0]

    escalated_item = _overlong("issue:1372-escalated-")
    orphan_item = _overlong("issue:1372-orphan-")
    queued_fix = _overlong("fix:1372-unlanded-")

    def before_terminal(rec) -> list:
        """`_valid_run()` with `rec` spliced in ahead of its `run_end`."""
        records = _valid_run()
        records.insert(len(records) - 1, rec)
        return records

    return [
        ("escalated-label-outside-closed-set",
         before_terminal({"kind": "escalated", "ts": "2026-09-02T10:10:00Z",
                          "item": "issue:1372", "label": long_label,
                          "label_applied": True}),
         ("escalated record for", "issue:1372", "carries label"),
         long_label),
        ("escalated-label-applied-not-true",
         before_terminal({"kind": "escalated", "ts": "2026-09-02T10:10:00Z",
                          "item": escalated_item, "label": allowed_label,
                          "label_applied": False}),
         ("escalated record for", "label_applied", "evidence"),
         escalated_item),
        ("item-start-without-prior-triaged",
         before_terminal({"kind": "item_start", "ts": "2026-09-02T10:10:00Z",
                          "item": orphan_item}),
         ("has no prior triaged record",),
         orphan_item),
        ("fix-queued-unresolved-at-run-end",
         before_terminal({"kind": "fix_queued", "ts": "2026-09-02T10:10:00Z",
                          "item": queued_fix}),
         ("reached the run_end terminal", "no fixed_in_run"),
         queued_fix),
    ]


# Parametrized only when pytest is present — CHECK 12 falls back to stdlib
# unittest, which collects no module-level function in this file anyway.
if pytest is not None:
    _BOUNDED_CASES = _bounded_message_cases()

    @pytest.mark.parametrize(
        "records,fragments,overlong",
        [case[1:] for case in _BOUNDED_CASES],
        ids=[case[0] for case in _BOUNDED_CASES],
    )
    def test_drain_ledger_bounds_every_quoted_identifier(
            records, fragments, overlong, tmp_path):
        """FAIL legs: each message lands, and quotes its identifier bounded.

        A guard states its observation (VER-009 / ADR-0083 D5): WHICH item
        escalated, started untriaged, or escaped as an unlanded fix is the
        observation; the whole of an arbitrarily large id is the finding's
        own noise, and the detail string carries at most five findings. The
        two escalated messages additionally get their first execution here —
        an enumerated ADR-0085 D6 FAIL condition the suite had never run.
        """
        _write_ledger(tmp_path, "drain-test-1.jsonl", records)

        result = health.check_drain_ledger(ledger_dir=str(tmp_path))

        assert result["result"] == "FAIL", result["detail"]
        for fragment in fragments:
            assert fragment in result["detail"], result["detail"]
        # The bounded rendering the row owes, re-derived from the row itself...
        assert health._drain_repr(overlong) in result["detail"], result["detail"]
        # ...and not one character of the unbounded value's tail.
        assert _TAIL_MARKER not in result["detail"], result["detail"]
