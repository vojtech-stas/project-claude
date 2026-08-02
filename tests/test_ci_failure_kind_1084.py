"""
Regression tests for tools/ci-failure-kind.sh (slice #1084 round-2 fix).

Root cause (reviewer BLOCK, PR #1087 round 1, verbatim from the verdict):
the pre-review CI gate's original inline classifier in ship/SKILL.md --
`gh run view "$RUN_ID" --log-failed | grep -q "CHECK 3"` -- matched on
tools/ci-checks.sh's CHECK 3 section HEADER, which prints unconditionally
on every run (ci-checks.sh omits `set -e` and always runs all 20 checks
regardless of earlier failures). So ANY ci-checks.sh failure got
misclassified as the #869 commit-subject-format class, starving the
reviewer gate for up to 3 implementer rounds on defects the implementer
was never correctly told about. The reviewer proved this empirically
against real historical CI run 28578918251 (a genuine CHECK 12 failure;
CHECK 3 itself passed).

This test exercises `tools/ci-failure-kind.sh`, the extracted, testable
helper that replaced the inline grep, against two REAL log excerpts:

  - OTHER_LOG: a condensed excerpt of run 28578918251's actual output
    (`gh run view 28578918251 --log-failed`) -- the CHECK 3 section header
    plus two unrelated pytest test-name lines that happen to contain the
    substring "CHECK 3", plus the real `FAIL: CHECK 12` line. No
    `FAIL: commit subject ...` line is present anywhere in the real log
    (CHECK 3 passed). Must classify "other", not "format".

  - FORMAT_LOG: the real `FAIL: commit subject ...` line text
    tools/ci-checks.sh emits when CHECK 3 itself fails -- captured by
    running `bash tools/ci-checks.sh` locally against a synthesized
    over-length/non-Conventional-Commits fixture commit on this branch,
    then reverting the fixture commit (`git reset --hard` back to the
    reviewed commit; no push). Must classify "format".

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_ci_failure_kind_1084.py -v
  python -m unittest tests.test_ci_failure_kind_1084 -v
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HELPER = REPO_ROOT / "tools" / "ci-failure-kind.sh"

# Locate a POSIX shell to invoke the helper with (mirrors
# tests/test_commit_msg_hook_1041.py's SH pattern for cross-platform CI).
SH = os.environ.get("CI_FAILURE_KIND_TEST_SH", "bash")

# Condensed real excerpt from `gh run view 28578918251 --log-failed`
# (genuine CHECK 12 failure; CHECK 3 itself passed -- no FAIL: commit
# subject line exists anywhere in the real log for this run).
OTHER_LOG = (
    "ci\tRun CI checks\t2026-07-02T09:13:11.8894835Z "
    "--- CHECK 3: commit subjects over origin/develop..HEAD ---\n"
    "ci\tRun CI checks\t2026-07-02T09:13:14.2251797Z "
    "--- CHECK 12: tests/ suite ---\n"
    "ci\tRun CI checks\t2026-07-02T09:14:14.2716798Z "
    "FAIL: CHECK 12 — unittest: test suite failed (exit 1)\n"
    "ci\tRun CI checks\t2026-07-02T09:14:14.3187619Z "
    "CHECK 3 git log range must be origin/develop..HEAD. ... ok\n"
    "ci\tRun CI checks\t2026-07-02T09:14:14.3189144Z "
    "CHECK 3 must not fetch origin main (should be origin develop). ... ok\n"
    "ci\tRun CI checks\t2026-07-02T09:14:14.3651293Z "
    "FAIL: test_checkonly_stub_matching_sha_already_fresh "
    "(test_dashboard_up_1053.TestDashboardUpScript."
    "test_checkonly_stub_matching_sha_already_fresh)\n"
)

# Real FAIL: line text captured locally by running `bash
# tools/ci-checks.sh` against a synthesized fixture commit with a bad
# subject (>72 chars, non-Conventional-Commits shape), then reverting the
# fixture commit via `git reset --hard` (no push; branch history clean).
FORMAT_LOG = (
    "--- CHECK 3: commit subjects over origin/develop..HEAD ---\n"
    "FAIL: commit subject exceeds 72 chars (75): "
    "Bad Subject That Is Definitely Over Seventy Two Characters Long "
    "For Testing\n"
    "FAIL: commit subject not Conventional Commits format: "
    "Bad Subject That Is Definitely Over Seventy Two Characters Long "
    "For Testing\n"
)


def _classify(log_text):
    """Write log_text to a temp file and run the helper's --from-file mode.

    Returns (returncode, stdout_stripped, stderr).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, encoding="utf-8"
    ) as f:
        f.write(log_text)
        log_path = f.name
    try:
        result = subprocess.run(
            [SH, str(HELPER), "--from-file", log_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        return result.returncode, result.stdout.strip(), result.stderr
    finally:
        try:
            os.unlink(log_path)
        except OSError:
            pass


class TestHelperExists(unittest.TestCase):
    """Sanity: the helper file must exist before behavioral tests can run."""

    def test_helper_file_exists(self):
        self.assertTrue(
            HELPER.is_file(),
            f"tools/ci-failure-kind.sh not found at {HELPER}",
        )


class TestClassifiesRealNonFormatFailureAsOther(unittest.TestCase):
    """Regression test for the reviewer-caught defect (PR #1087 round 1):
    the OLD `grep -q "CHECK 3"` classifier matched this real log and
    misclassified a genuine CHECK 12 failure as the format class. The new
    classifier must NOT trip on header/test-name mentions of "CHECK 3".
    """

    def test_check12_failure_run_classifies_other(self):
        rc, out, err = _classify(OTHER_LOG)
        self.assertEqual(rc, 0, f"helper exited {rc}: {err}")
        self.assertEqual(
            out,
            "other",
            "misclassified a real non-format CI failure (run 28578918251, "
            "genuine CHECK 12 failure) as 'format'",
        )


class TestClassifiesRealFormatFailureAsFormat(unittest.TestCase):
    """The classifier must still correctly detect a genuine CHECK 3
    (commit-subject format) failure -- the #869 class this gate exists
    to intercept.
    """

    def test_check3_failure_output_classifies_format(self):
        rc, out, err = _classify(FORMAT_LOG)
        self.assertEqual(rc, 0, f"helper exited {rc}: {err}")
        self.assertEqual(
            out,
            "format",
            "failed to classify a genuine CHECK 3 commit-subject-format "
            "failure as 'format'",
        )


class TestUsageErrors(unittest.TestCase):
    """Missing/invalid --from-file argument is a usage error (exit 2), not
    a silent misclassification.
    """

    def test_missing_file_argument_is_usage_error(self):
        result = subprocess.run(
            [SH, str(HELPER), "--from-file"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 2)

    def test_nonexistent_file_is_usage_error(self):
        result = subprocess.run(
            [SH, str(HELPER), "--from-file", "/definitely/does/not/exist.log"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
