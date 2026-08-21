"""
tests/test_verdict_presence_1219.py

Regression tests for PRD #1214 slice #1219 — the verdict-presence CI gate
(tools/check-verdict-presence.py), the D6-supersession compensating control
(ADR-0080 D1's supersession of ADR-0075 D6).

Reviewer round-1 BLOCK (R-TESTS, PR #1222): 253 lines of new executable
CI-gate code shipped with ZERO test coverage, and the soft-degrade
classifier (`_gh_unauthenticated`) matched the bare substring "token"
anywhere in stderr — a rate-limit message ("API rate limit exceeded for
token ...") would have silently turned this REQUIRED gate into an
invisible PASS. Fixed alongside this test file:
  - `_gh_unauthenticated()` no longer matches bare "token" (narrowed to
    gh's actual not-authenticated error shapes).
  - Every gh-calling helper now returns a tri-state (status, value) —
    "ok" / "soft_degrade" / "hard_fail" — where "soft_degrade" is reserved
    for a CONFIRMED local-dev condition (gh not installed, or gh's own
    not-authenticated stderr shape) and EVERYTHING else (rate limits,
    timeouts, non-JSON output, a per-PR fetch failing mid-window) is a
    "hard_fail" — `main()` turns that into FAIL/exit 1, never a silent
    SKIP/exit 0.

Covers:
  (a) the pure classifier functions (comment_has_verdict_approve,
      pr_has_verdict, classify_prs) — no I/O, mirrors
      tests/test_slicer_provenance.py's house pattern for its own pure
      functions.
  (b) the --fixture-file CLI exit-code contract: a clean fixture (every PR
      carries the trailer) exits 0; a fixture with one PR missing the
      trailer exits 1 and names it.
  (c) the soft-degrade / hard-fail tri-state — THE regression case:
        - `_gh_unauthenticated()` recognizes gh's real not-authenticated
          shapes ("not logged in to any hosts", "authentication",
          "unauthorized", "gh_token").
        - `_gh_unauthenticated()` does NOT match a rate-limit message that
          happens to contain the word "token" — the exact finding.
        - `_fetch_recent_merged_pr_numbers()` / `_fetch_pr_comments()`,
          driven through a monkeypatched `_run_gh`, correctly classify:
          gh-not-installed → soft_degrade; confirmed-unauthenticated →
          soft_degrade; rate-limit-shaped / unrecognized non-zero exit →
          hard_fail; non-JSON output → hard_fail.
        - `main()`'s end-to-end behavior for each tri-state outcome via a
          monkeypatched `_fetch_prs_with_comments`: soft_degrade → exit 0
          with a named SKIP reason; hard_fail → exit 1 with a named FAIL
          reason (never a silent pass).

All tests are offline, deterministic, and network-free — no real `gh`
calls anywhere in this file (mirrors tests/test_slicer_provenance.py's own
no-network discipline).

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_verdict_presence_1219.py -v
  python -m unittest tests.test_verdict_presence_1219 -v
"""

import importlib.util as _ilu
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Import tools/check-verdict-presence.py (hyphenated filename) via importlib,
# mirroring tests/test_slicer_provenance.py's exact pattern.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = _REPO_ROOT / "tools"

_spec = _ilu.spec_from_file_location(
    "check_verdict_presence",
    str(_TOOLS_DIR / "check-verdict-presence.py"),
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

comment_has_verdict_approve = _mod.comment_has_verdict_approve
pr_has_verdict = _mod.pr_has_verdict
classify_prs = _mod.classify_prs
_gh_unauthenticated = _mod._gh_unauthenticated


# ---------------------------------------------------------------------------
# (a) Pure classifier functions — no I/O.
# ---------------------------------------------------------------------------


class TestCommentHasVerdictApprove(unittest.TestCase):
    def test_exact_trailer_detected(self):
        self.assertTrue(comment_has_verdict_approve("VERDICT: APPROVE"))

    def test_trailer_with_extra_whitespace(self):
        self.assertTrue(comment_has_verdict_approve("VERDICT:   APPROVE"))

    def test_trailer_embedded_in_longer_comment(self):
        body = "## Reviewer verdict\n\nVERDICT: APPROVE\nCRITIC: reviewer\nROUND: 1"
        self.assertTrue(comment_has_verdict_approve(body))

    def test_no_trailer_returns_false(self):
        self.assertFalse(comment_has_verdict_approve("Looks good, no complaints."))

    def test_block_verdict_does_not_match_approve(self):
        self.assertFalse(comment_has_verdict_approve("VERDICT: BLOCK"))

    def test_empty_body_returns_false(self):
        self.assertFalse(comment_has_verdict_approve(""))

    def test_none_body_returns_false(self):
        self.assertFalse(comment_has_verdict_approve(None))


class TestPrHasVerdict(unittest.TestCase):
    def test_any_matching_comment_is_sufficient(self):
        comments = [{"body": "no trailer here"}, {"body": "VERDICT: APPROVE"}]
        self.assertTrue(pr_has_verdict(comments))

    def test_no_matching_comment_returns_false(self):
        comments = [{"body": "no trailer"}, {"body": "still no trailer"}]
        self.assertFalse(pr_has_verdict(comments))

    def test_empty_comment_list_returns_false(self):
        self.assertFalse(pr_has_verdict([]))

    def test_comment_missing_body_key_tolerated(self):
        comments = [{}, {"body": "VERDICT: APPROVE"}]
        self.assertTrue(pr_has_verdict(comments))


class TestClassifyPrs(unittest.TestCase):
    def test_all_ok(self):
        prs = [
            {"number": 1, "comments": [{"body": "VERDICT: APPROVE"}]},
            {"number": 2, "comments": [{"body": "VERDICT: APPROVE"}]},
        ]
        result = classify_prs(prs)
        self.assertEqual(result["ok"], [1, 2])
        self.assertEqual(result["missing"], [])

    def test_one_missing(self):
        prs = [
            {"number": 1, "comments": [{"body": "no trailer"}]},
            {"number": 2, "comments": [{"body": "VERDICT: APPROVE"}]},
        ]
        result = classify_prs(prs)
        self.assertEqual(result["ok"], [2])
        self.assertEqual(result["missing"], [1])

    def test_missing_comments_key_treated_as_missing(self):
        prs = [{"number": 3}]
        result = classify_prs(prs)
        self.assertEqual(result["missing"], [3])

    def test_empty_pr_list(self):
        self.assertEqual(classify_prs([]), {"ok": [], "missing": []})


# ---------------------------------------------------------------------------
# (b) --fixture-file CLI exit-code contract.
# ---------------------------------------------------------------------------


class TestFixtureFileExitCodeContract(unittest.TestCase):
    def _write_fixture(self, tmp_dir, data):
        path = Path(tmp_dir) / "fixture.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_clean_fixture_exits_zero(self):
        """Every PR carries the trailer -> exit 0, PASS."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = self._write_fixture(tmp, [
                {"number": 9002, "comments": [{"body": "VERDICT: APPROVE"}]},
            ])
            exit_code = _mod.main(["--fixture-file", fixture_path])
        self.assertEqual(exit_code, 0)

    def test_missing_verdict_fixture_exits_one_and_names_pr(self):
        """One PR lacking the trailer -> exit 1, named in stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture_path = self._write_fixture(tmp, [
                {"number": 9001, "comments": [{"body": "Looks good, no complaints."}]},
                {"number": 9002, "comments": [{"body": "VERDICT: APPROVE"}]},
            ])
            captured_stderr = io.StringIO()
            orig_stderr = sys.stderr
            sys.stderr = captured_stderr
            try:
                exit_code = _mod.main(["--fixture-file", fixture_path])
            finally:
                sys.stderr = orig_stderr
        self.assertEqual(exit_code, 1)
        self.assertIn("#9001", captured_stderr.getvalue())
        self.assertNotIn("#9002", captured_stderr.getvalue().split("These merged")[0])


# ---------------------------------------------------------------------------
# (c) Soft-degrade / hard-fail tri-state — THE regression case.
# ---------------------------------------------------------------------------


class TestGhUnauthenticatedNarrowMatch(unittest.TestCase):
    """`_gh_unauthenticated()` must recognize gh's real not-authenticated
    shapes, and must NOT match a rate-limit message merely because it
    contains the word "token" (the reviewer's exact finding on PR #1222)."""

    def test_not_logged_in_is_recognized(self):
        self.assertTrue(_gh_unauthenticated("To get started, please run:  gh auth login"
                                             "\nerror: not logged in to any hosts"))

    def test_authentication_phrase_is_recognized(self):
        self.assertTrue(_gh_unauthenticated("gh: authentication required"))

    def test_unauthorized_is_recognized(self):
        self.assertTrue(_gh_unauthenticated("HTTP 401: Unauthorized"))

    def test_gh_token_env_hint_is_recognized(self):
        self.assertTrue(_gh_unauthenticated(
            "populate the GH_TOKEN environment variable with a GitHub API token"
        ))

    def test_rate_limit_message_with_bare_token_word_is_NOT_recognized(self):
        """THE regression case: gh's rate-limit error contains the word
        "token" but is NOT an authentication failure — matching it would
        silently soft-degrade (invisible PASS) on a transient condition."""
        bare_rate_limit_stderr = "gh: API rate limit exceeded for token ****. Try again later."
        self.assertFalse(_gh_unauthenticated(bare_rate_limit_stderr))

    def test_plain_network_error_is_not_recognized(self):
        self.assertFalse(_gh_unauthenticated("gh: connection reset by peer"))

    def test_empty_stderr_is_not_recognized(self):
        self.assertFalse(_gh_unauthenticated(""))

    def test_none_stderr_is_not_recognized(self):
        self.assertFalse(_gh_unauthenticated(None))


def _fake_run_gh_factory(responses):
    """Build a fake `_run_gh(args, timeout=30)` replacement that returns
    successive (status, value) tuples from `responses`, one per call, in
    order — enough to drive the list-call-then-per-PR-loop shape of
    `_fetch_prs_with_comments` deterministically, offline."""
    call_iter = iter(responses)

    def _fake(args, timeout=30):
        return next(call_iter)

    return _fake


class TestTriStateFetchLayer(unittest.TestCase):
    """Drives `_fetch_recent_merged_pr_numbers` / `_fetch_pr_comments` /
    `_fetch_prs_with_comments` through a monkeypatched `_run_gh` — no real
    `gh` subprocess is ever spawned in this test class."""

    def setUp(self):
        self._orig_run_gh = _mod._run_gh

    def tearDown(self):
        _mod._run_gh = self._orig_run_gh

    def test_gh_not_installed_is_soft_degrade(self):
        _mod._run_gh = _fake_run_gh_factory([("soft_degrade", "gh not found")])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "soft_degrade")
        self.assertIn("gh not found", value)

    def test_confirmed_unauthenticated_stderr_is_soft_degrade(self):
        fake_result = SimpleNamespace(
            returncode=1, stdout="", stderr="error: not logged in to any hosts"
        )
        _mod._run_gh = _fake_run_gh_factory([("ok", fake_result)])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "soft_degrade")
        self.assertIn("unauthenticated", value)

    def test_rate_limit_shaped_failure_is_hard_fail_not_soft_degrade(self):
        """THE regression case at the fetch layer: a rate-limit-shaped gh
        failure (contains "token" but is not an auth failure) must be a
        hard_fail, never a silent soft_degrade."""
        fake_result = SimpleNamespace(
            returncode=1, stdout="",
            stderr="gh: API rate limit exceeded for token ****. Try again later.",
        )
        _mod._run_gh = _fake_run_gh_factory([("ok", fake_result)])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "hard_fail")
        self.assertIn("gh pr list exited", value)

    def test_gh_timeout_is_hard_fail(self):
        _mod._run_gh = _fake_run_gh_factory([("hard_fail", "gh timed out")])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "hard_fail")
        self.assertIn("timed out", value)

    def test_non_json_stdout_is_hard_fail(self):
        fake_result = SimpleNamespace(returncode=0, stdout="not json at all", stderr="")
        _mod._run_gh = _fake_run_gh_factory([("ok", fake_result)])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "hard_fail")
        self.assertIn("non-JSON", value)

    def test_empty_stdout_is_ok_empty_list(self):
        fake_result = SimpleNamespace(returncode=0, stdout="  ", stderr="")
        _mod._run_gh = _fake_run_gh_factory([("ok", fake_result)])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "ok")
        self.assertEqual(value, [])

    def test_successful_list_parses_pr_numbers(self):
        fake_result = SimpleNamespace(
            returncode=0, stdout=json.dumps([{"number": 10}, {"number": 11}]), stderr="",
        )
        _mod._run_gh = _fake_run_gh_factory([("ok", fake_result)])
        status, value = _mod._fetch_recent_merged_pr_numbers(20)
        self.assertEqual(status, "ok")
        self.assertEqual(value, [10, 11])

    def test_per_pr_comment_fetch_failure_mid_window_is_hard_fail(self):
        """A per-PR gh pr view failure (after the list call already
        succeeded, proving gh IS authenticated) must be a hard_fail —
        never silently degraded to an empty comment list, which would
        mischaracterize an unverifiable PR as one genuinely lacking the
        trailer."""
        list_result = SimpleNamespace(
            returncode=0, stdout=json.dumps([{"number": 42}]), stderr="",
        )
        view_failure = SimpleNamespace(
            returncode=1, stdout="", stderr="gh: API rate limit exceeded",
        )
        _mod._run_gh = _fake_run_gh_factory([("ok", list_result), ("ok", view_failure)])
        status, value = _mod._fetch_prs_with_comments(20)
        self.assertEqual(status, "hard_fail")
        self.assertIn("gh pr view #42", value)

    def test_full_success_path_returns_ok_with_comments(self):
        list_result = SimpleNamespace(
            returncode=0, stdout=json.dumps([{"number": 42}]), stderr="",
        )
        view_result = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"comments": [{"body": "VERDICT: APPROVE"}]}),
            stderr="",
        )
        _mod._run_gh = _fake_run_gh_factory([("ok", list_result), ("ok", view_result)])
        status, value = _mod._fetch_prs_with_comments(20)
        self.assertEqual(status, "ok")
        self.assertEqual(value, [{"number": 42, "comments": [{"body": "VERDICT: APPROVE"}]}])


class TestMainEndToEndTriState(unittest.TestCase):
    """Drives `main()` itself through a monkeypatched `_fetch_prs_with_comments`
    — confirms the SKIP/exit-0 vs FAIL/exit-1 behavior at the CLI boundary."""

    def setUp(self):
        self._orig = _mod._fetch_prs_with_comments

    def tearDown(self):
        _mod._fetch_prs_with_comments = self._orig

    def test_soft_degrade_exits_zero_with_named_reason(self):
        _mod._fetch_prs_with_comments = lambda limit: ("soft_degrade", "gh not found")
        captured_stdout = io.StringIO()
        orig_stdout = sys.stdout
        sys.stdout = captured_stdout
        try:
            exit_code = _mod.main([])
        finally:
            sys.stdout = orig_stdout
        self.assertEqual(exit_code, 0)
        self.assertIn("SKIP", captured_stdout.getvalue())
        self.assertIn("gh not found", captured_stdout.getvalue())

    def test_hard_fail_exits_one_with_named_reason_never_silent_pass(self):
        """THE regression case end-to-end: an ambiguous/rate-limit-shaped
        gh failure must exit 1 (FAIL), never exit 0 (a silent invisible
        PASS for this REQUIRED gate)."""
        _mod._fetch_prs_with_comments = lambda limit: (
            "hard_fail", "gh pr list exited 1: API rate limit exceeded for token ****"
        )
        captured_stderr = io.StringIO()
        orig_stderr = sys.stderr
        sys.stderr = captured_stderr
        try:
            exit_code = _mod.main([])
        finally:
            sys.stderr = orig_stderr
        self.assertEqual(exit_code, 1)
        self.assertIn("FAIL", captured_stderr.getvalue())
        self.assertIn("rate limit", captured_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
