"""
tests/test_trace_kind_enum_1129.py

Regression test for slice #1129 (PRD #1127 walking skeleton), §2 criterion 9:
`tools/trace.py`'s `emit_span` must accept ONLY the closed v3 kind enum
{pr_opened, pr_merged, qa_verified, develop_green, promotion, dispatch,
dispatch_end, verdict}. An out-of-enum kind must hard-error (non-zero /
raised exception) and write NOTHING to the trace log. (The enum's ninth
member, `batch_planned`, was retired per ADR-0080 D2 / slice #1219 — see
`test_retired_batch_planned_kind_hard_errors_like_any_unknown_kind` below,
PRD #1214 criterion 2a2's regression coverage.)

Test-first discipline (rule #13 rider / ADR-0067 D3 shape, applied to this
new-feature slice per its own §2 #9 instruction): this commit lands BEFORE
`tools/trace.py` gains the enum check.

FAILS before the fix: `emit_span(kind="bogus_kind", ...)` currently succeeds
and writes a line — there is no kind validation at all today.
PASSES after the fix: `emit_span` raises `ValueError` for any kind outside
the closed enum, and the CLI `emit` subcommand exits non-zero with NO line
written to the log.

Also asserts every existing writer-produced kind (the five PRD #1075 kinds
plus the three surviving PRD #1127 kinds) remains accepted — the enum is
additive, never subtractive, over the pre-existing five.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_trace_kind_enum_1129.py -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TRACE_PY = REPO_ROOT / "tools" / "trace.py"

VALID_KINDS = (
    "pr_opened", "pr_merged", "qa_verified", "develop_green", "promotion",
    "dispatch", "dispatch_end", "verdict",
)


def _load_trace_module():
    spec = importlib.util.spec_from_file_location("trace_v3_enum_test", TRACE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


class TestClosedKindEnum(unittest.TestCase):
    def setUp(self):
        self._orig_override = os.environ.get("TRACE_LOG_OVERRIDE")

    def tearDown(self):
        if self._orig_override is None:
            os.environ.pop("TRACE_LOG_OVERRIDE", None)
        else:
            os.environ["TRACE_LOG_OVERRIDE"] = self._orig_override

    def test_out_of_enum_kind_raises_and_writes_nothing(self):
        mod = _load_trace_module()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            os.environ["TRACE_LOG_OVERRIDE"] = log_path

            with self.assertRaises(ValueError):
                mod.emit_span(trace_id="x-1", kind="bogus_kind", attrs={})

            self.assertEqual(
                _read_jsonl(log_path), [],
                "an out-of-enum kind must write NOTHING to the trace log",
            )

    def test_retired_batch_planned_kind_hard_errors_like_any_unknown_kind(self):
        """PRD #1214 criterion 2a2 / ADR-0080 D2, slice #1219: the retired
        `batch_planned` kind must hard-error EXACTLY like any other
        out-of-enum kind (it is not special-cased) and write nothing."""
        mod = _load_trace_module()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            os.environ["TRACE_LOG_OVERRIDE"] = log_path

            with self.assertRaises(ValueError):
                mod.emit_span(trace_id="x-retired", kind="batch_planned", attrs={})

            self.assertEqual(
                _read_jsonl(log_path), [],
                "the retired batch_planned kind must write NOTHING to the trace log",
            )
            self.assertNotIn("batch_planned", mod.VALID_KINDS)

    def test_every_valid_kind_is_accepted(self):
        mod = _load_trace_module()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            os.environ["TRACE_LOG_OVERRIDE"] = log_path

            for kind in VALID_KINDS:
                mod.emit_span(trace_id=f"x-{kind}", kind=kind, attrs={})

            lines = _read_jsonl(log_path)
            self.assertEqual(len(lines), len(VALID_KINDS))
            self.assertEqual({l["kind"] for l in lines}, set(VALID_KINDS))

    def test_cli_emit_out_of_enum_kind_exits_nonzero_no_line_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trace-v3.jsonl")
            env = os.environ.copy()
            env["TRACE_LOG_OVERRIDE"] = log_path
            result = subprocess.run(
                [sys.executable, str(TRACE_PY), "emit", "--kind", "bogus_kind",
                 "--trace-id", "x-2"],
                capture_output=True, text=True, cwd=str(REPO_ROOT), env=env, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(_read_jsonl(log_path), [])


if __name__ == "__main__":
    unittest.main()
