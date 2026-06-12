"""
Tests for tools/run_evals.py parse_verdict() and dashboard/health.py
_check_eval_critic() (R-TESTS coverage for the eval runner PR, slice #817).

parse_verdict is the correctness bottleneck for the eval runner: silent
miscategorisation produces wrong pass rates undetected.  _check_eval_critic
has 7 conditional branches; each is exercised below.

Runner: stdlib unittest (no pytest dependency — matches CI's CHECK 12 fallback).
  python -m unittest discover -s tests
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path helpers — mirror pattern from test_events_interleave.py
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _add_tools_to_path() -> None:
    tools_dir = str(_repo_root() / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)


def _add_dashboard_to_path() -> None:
    dashboard_dir = str(_repo_root() / "dashboard")
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)


# ---------------------------------------------------------------------------
# parse_verdict tests
# ---------------------------------------------------------------------------

class TestParseVerdict(unittest.TestCase):
    """parse_verdict() must deterministically return APPROVE, BLOCK, or UNPARSEABLE.

    Correctness bottleneck: wrong parse → wrong pass rates → silent regressions.
    """

    def setUp(self):
        _add_tools_to_path()
        from run_evals import parse_verdict  # noqa: PLC0415
        self.parse_verdict = parse_verdict

    def test_fenced_approve(self):
        """Standard fenced CRITIC trailer with APPROVE returns APPROVE."""
        output = "```\nVERDICT: APPROVE\nREASON: looks good\nROUND: 1\n```"
        self.assertEqual(self.parse_verdict(output), "APPROVE")

    def test_fenced_block(self):
        """Standard fenced CRITIC trailer with BLOCK returns BLOCK."""
        output = "```\nVERDICT: BLOCK\nREASON: scope drift\nROUND: 1\n```"
        self.assertEqual(self.parse_verdict(output), "BLOCK")

    def test_no_fenced_block(self):
        """Plain text with VERDICT: APPROVE (not inside backticks) returns UNPARSEABLE.

        The function only scans fenced blocks — a bare VERDICT line is not valid.
        """
        output = "VERDICT: APPROVE\nREASON: ok"
        self.assertEqual(self.parse_verdict(output), "UNPARSEABLE")

    def test_garbage_verdict_token(self):
        """An unrecognised verdict token inside a fenced block returns UNPARSEABLE."""
        output = "```\nVERDICT: BANANA\nREASON: ???\n```"
        self.assertEqual(self.parse_verdict(output), "UNPARSEABLE")

    def test_empty_output(self):
        """Empty string (e.g. model timeout / empty response) returns UNPARSEABLE."""
        self.assertEqual(self.parse_verdict(""), "UNPARSEABLE")

    def test_fenced_with_language_tag(self):
        """Fenced block with a language specifier (```text) is still parsed."""
        output = "```text\nVERDICT: APPROVE\nREASON: all good\n```"
        self.assertEqual(self.parse_verdict(output), "APPROVE")

    def test_lowercase_verdict_value(self):
        """Lowercase 'approve' is normalised to APPROVE via .upper()."""
        output = "```\nVERDICT: approve\n```"
        self.assertEqual(self.parse_verdict(output), "APPROVE")

    def test_trailing_punctuation_stripped(self):
        """Trailing punctuation (period, colon) is stripped before comparison."""
        output = "```\nVERDICT: APPROVE.\n```"
        self.assertEqual(self.parse_verdict(output), "APPROVE")

    def test_first_valid_verdict_wins(self):
        """When multiple fenced blocks exist, the first valid verdict is returned."""
        output = "```\nVERDICT: BLOCK\n```\n\n```\nVERDICT: APPROVE\n```"
        self.assertEqual(self.parse_verdict(output), "BLOCK")

    def test_no_verdict_key_in_fenced_block(self):
        """A fenced block with no VERDICT: line returns UNPARSEABLE."""
        output = "```\nROUND: 1\nREASON: no verdict here\n```"
        self.assertEqual(self.parse_verdict(output), "UNPARSEABLE")


# ---------------------------------------------------------------------------
# _check_eval_critic tests
# ---------------------------------------------------------------------------

class TestCheckEvalCritic(unittest.TestCase):
    """_check_eval_critic() covers 7 branches:
      1. results.json absent           → WARN (honest no-baseline)
      2. results.json unreadable       → WARN
      3. no entry for critic           → WARN
      4. stale (>14 days)              → WARN
      5. pass_rate is None (0 cases)   → WARN
      6. pass_rate < 1.0               → WARN
      7. pass_rate == 1.0, fresh run   → PASS
    """

    def _import_check(self):
        _add_dashboard_to_path()
        import health  # noqa: PLC0415
        return health._check_eval_critic

    def _ts_fresh(self) -> str:
        """ISO timestamp for a run that happened 1 day ago (well within 14-day window)."""
        return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    def _ts_stale(self) -> str:
        """ISO timestamp for a run that happened 20 days ago (stale)."""
        return (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()

    def _write_results(self, tmp_dir: Path, data: dict) -> Path:
        results_path = tmp_dir / "results.json"
        results_path.write_text(json.dumps(data), encoding="utf-8")
        return results_path

    # ------------------------------------------------------------------
    # Branch 1: file absent → WARN
    # ------------------------------------------------------------------
    def test_absent_results_file_returns_warn(self):
        """WARN when results.json does not exist (honest no-baseline bucket)."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "does_not_exist" / "results.json"
            with patch.object(health, "_EVALS_RESULTS_FILE", absent):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "WARN")
        self.assertIn("not found", result["detail"])

    # ------------------------------------------------------------------
    # Branch 2: file unreadable → WARN
    # ------------------------------------------------------------------
    def test_unreadable_results_file_returns_warn(self):
        """WARN when results.json exists but contains invalid JSON."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = Path(tmp) / "results.json"
            bad_file.write_text("not valid json {{{{", encoding="utf-8")
            with patch.object(health, "_EVALS_RESULTS_FILE", bad_file):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "WARN")
        self.assertIn("unreadable", result["detail"])

    # ------------------------------------------------------------------
    # Branch 3: no critic data in results → WARN
    # ------------------------------------------------------------------
    def test_no_critic_data_returns_warn(self):
        """WARN when results.json exists but has no entry for this critic."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            results_path = self._write_results(
                Path(tmp),
                {"prd-critic": {"pass_rate": 1.0, "ts": self._ts_fresh()}},
            )
            with patch.object(health, "_EVALS_RESULTS_FILE", results_path):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "WARN")
        self.assertIn("no run recorded", result["detail"])

    # ------------------------------------------------------------------
    # Branch 4: stale results → WARN
    # ------------------------------------------------------------------
    def test_stale_results_returns_warn(self):
        """WARN when the last run timestamp is older than _EVAL_STALE_DAYS (14)."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            results_path = self._write_results(
                Path(tmp),
                {
                    "reviewer": {
                        "pass_rate": 1.0,
                        "total": 8,
                        "passed": 8,
                        "ts": self._ts_stale(),
                    }
                },
            )
            with patch.object(health, "_EVALS_RESULTS_FILE", results_path):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "WARN")
        self.assertIn("stale", result["detail"])

    # ------------------------------------------------------------------
    # Branch 5: pass_rate is None (0 cases run) → WARN
    # ------------------------------------------------------------------
    def test_null_pass_rate_returns_warn(self):
        """WARN when pass_rate is None (no cases were executed, e.g. all filtered)."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            results_path = self._write_results(
                Path(tmp),
                {
                    "reviewer": {
                        "pass_rate": None,
                        "total": 0,
                        "passed": 0,
                        "ts": self._ts_fresh(),
                    }
                },
            )
            with patch.object(health, "_EVALS_RESULTS_FILE", results_path):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "WARN")
        self.assertIn("no pass_rate", result["detail"])

    # ------------------------------------------------------------------
    # Branch 6: pass_rate < 1.0 → WARN
    # ------------------------------------------------------------------
    def test_partial_pass_rate_returns_warn(self):
        """WARN when pass_rate < 1.0 (some cases failed)."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            results_path = self._write_results(
                Path(tmp),
                {
                    "reviewer": {
                        "pass_rate": 0.75,
                        "total": 8,
                        "passed": 6,
                        "ts": self._ts_fresh(),
                    }
                },
            )
            with patch.object(health, "_EVALS_RESULTS_FILE", results_path):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "WARN")
        self.assertIn("pass_rate", result["detail"])

    # ------------------------------------------------------------------
    # Branch 7: pass_rate == 1.0, fresh run → PASS
    # ------------------------------------------------------------------
    def test_full_pass_rate_fresh_returns_pass(self):
        """PASS when pass_rate is 1.0 and the run is within the 14-day window."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            results_path = self._write_results(
                Path(tmp),
                {
                    "reviewer": {
                        "pass_rate": 1.0,
                        "total": 8,
                        "passed": 8,
                        "ts": self._ts_fresh(),
                    }
                },
            )
            with patch.object(health, "_EVALS_RESULTS_FILE", results_path):
                result = check("reviewer", "EVAL-REVIEWER")
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["id"], "EVAL-REVIEWER")

    # ------------------------------------------------------------------
    # check_id propagation
    # ------------------------------------------------------------------
    def test_check_id_propagated_in_result(self):
        """The check_id parameter is present as 'id' in every returned dict."""
        check = self._import_check()
        import health  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "no_results.json"
            with patch.object(health, "_EVALS_RESULTS_FILE", absent):
                result = check("prd-critic", "EVAL-PRD-CRITIC")
        self.assertEqual(result["id"], "EVAL-PRD-CRITIC")


if __name__ == "__main__":
    unittest.main()
