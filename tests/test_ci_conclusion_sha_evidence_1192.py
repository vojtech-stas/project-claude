"""
tests/test_ci_conclusion_sha_evidence_1192.py

Regression tests for issue #1192 (ADR-0079 D2) -- dashboard/health.py's
_fetch_github_ci_conclusion() must accept the CERTIFIED sha as an explicit
parameter instead of re-deriving it internally via `git rev-parse
origin/develop`. The internal derivation is a stale-local-ref race: PR
#1190/#1191 proved live that record-green.sh already resolves the correct
merged sha, but the CI-trust lookup re-derived its OWN sha independently and
cited a NEIGHBOURING PR's CI run when the local ref had moved between the
two derivations.

Per ADR-0067 D2/D3 (REG-002): this test commit PRECEDES the fix commit.
Pre-fix, `_fetch_github_ci_conclusion` takes exactly one positional arg
(`repo_root`) -- calling it with `sha=...` raises TypeError, so every test
below that passes `sha=` FAILS on pre-fix code and PASSES once the additive
`sha=None` kwarg lands.

Fix shape (dashboard/health.py::_fetch_github_ci_conclusion ONLY):
  _fetch_github_ci_conclusion(repo_root, sha=None)
    sha is None  -> BYTE-IDENTICAL to the pre-fix code: derive develop_sha
                    via `git rev-parse origin/develop` as before (existing
                    RELEASE-READY no-sha callers untouched).
    sha given    -> use it directly as develop_sha; the internal
                    `git rev-parse origin/develop` call is SKIPPED entirely
                    (closes the #1192 race by construction -- the recent
                    merged-PR search below can only ever match the
                    requested sha, never a stale one).

Acceptance criteria verified (slice #1197 / PRD #1193 SS2 2a/2b):
  2a  certify sha X (local `origin/develop` would resolve to a DIFFERENT
      sha Y) -> evidence cites X's PR, and `git rev-parse` is never even
      invoked (proving Y is never consulted).
  2b  certify sha X, but the fetched merged-PR list contains a match ONLY
      for a DIFFERENT sha Y (the exact #1192 incident shape: the OLD
      no-sha code would have found & cited Y) -> function returns
      "unavailable" citing X, never a false "pass" citing Y's PR. The
      downstream "no green event written" consequence is the EXISTING
      (unmodified) record-green.sh unavailable -> local-pytest-fallback
      chain -- see
      tests/test_record_green_ci_trust_1161.py::
      TestNoRecordedRunFallsBackToLocalPytest::test_unavailable_plus_pytest_fail_refuses
      (untouched by this slice; a companion test below asserts it still
      exists and still covers exactly that chain).
  freeze     the no-sha call path is BYTE-IDENTICAL pre/post-fix (the
      slicer's named risk) -- calling without `sha` still derives locally
      and matches exactly as before; `sha=None` explicit == omitted.
  boundary   the sha kwarg does NOT introduce a new status value and does
      NOT alter unavailable-sentinel semantics (#1166 is untouched by this
      slice, named as out-of-bounds in slice #1197's body) -- the
      sha-explicit no-match case returns the SAME "unavailable" status and
      the SAME "no merged PR to develop matched HEAD ..." detail shape as
      the pre-existing no-sha no-match case.
  wiring     tools/record-green.sh's real (non-injected) code path must
      thread its resolved DEV_SHA into the sha= kwarg, or the health.py fix
      is dead code from the actual production caller's perspective.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_ci_conclusion_sha_evidence_1192.py -v
"""

import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).parent.parent
DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)


def _reload_health():
    if "health" in sys.modules:
        importlib.reload(sys.modules["health"])
    else:
        importlib.import_module("health")
    return sys.modules["health"]


class _FakeGhFetch:
    """Fake-gh seam standing in for health._health_gh_fetch -- returns
    canned (rc, stdout) tuples keyed by the gh subcommand ("pr list" vs
    "pr checks"). Mirrors the spy technique used in
    tests/test_record_green_ci_trust_1161.py: no real subprocess/gh call."""

    def __init__(self, pr_list, checks_by_pr):
        self._pr_list = pr_list
        self._checks_by_pr = checks_by_pr
        self.calls = []

    def __call__(self, args, *, ttl=60.0, timeout=5.0):
        self.calls.append(list(args))
        if args[:2] == ["pr", "list"]:
            return 0, json.dumps(self._pr_list)
        if args[:2] == ["pr", "checks"]:
            pr_num = int(args[2])
            checks = self._checks_by_pr.get(pr_num, [])
            return 0, json.dumps(checks)
        return 1, ""


SHA_X = "x" * 40  # the CERTIFIED sha (what record-green.sh resolved)
SHA_Y = "y" * 40  # a DIFFERENT sha (what a stale local ref would resolve to)


class TestShaExplicitCitesCorrectPr(unittest.TestCase):
    """2a: certify X while a fake local git-rev-parse would resolve Y ->
    evidence must cite X, and git is never even consulted."""

    def test_pass_cites_certified_sha_not_local_ref(self):
        h = _reload_health()
        fake = _FakeGhFetch(
            pr_list=[{"number": 42, "mergeCommit": {"oid": SHA_X}}],
            checks_by_pr={42: [{"name": "ci", "state": "SUCCESS"}]},
        )
        with mock.patch.object(h, "_health_gh_fetch", fake), \
                mock.patch("subprocess.run") as mock_sp:
            mock_sp.side_effect = AssertionError(
                "git rev-parse must NOT be invoked when sha= is given explicitly"
            )
            status, detail = h._fetch_github_ci_conclusion(str(REPO_ROOT), sha=SHA_X)

        self.assertEqual(status, "pass", f"expected pass; got {status!r} ({detail!r})")
        self.assertIn("#42", detail, f"detail must cite the certified sha's PR: {detail!r}")
        mock_sp.assert_not_called()


class TestShaExplicitMismatchRefusesNotAttributes(unittest.TestCase):
    """2b: certify X, but the merged-PR list ONLY has a match for a
    DIFFERENT sha Y (the exact #1192 incident shape) -> must NOT cite Y's
    evidence as X's. Returns 'unavailable' (honest no-match), never a false
    'pass' citing the neighbour."""

    def test_no_false_positive_pass_for_neighbour_sha(self):
        h = _reload_health()
        fake = _FakeGhFetch(
            pr_list=[{"number": 99, "mergeCommit": {"oid": SHA_Y}}],
            checks_by_pr={99: [{"name": "ci", "state": "SUCCESS"}]},
        )
        with mock.patch.object(h, "_health_gh_fetch", fake):
            status, detail = h._fetch_github_ci_conclusion(str(REPO_ROOT), sha=SHA_X)

        self.assertNotEqual(
            status, "pass",
            f"must NOT report pass by citing PR #99's (sha={SHA_Y}) evidence "
            f"for a DIFFERENT certified sha ({SHA_X}) -- this is the exact "
            f"#1192 mis-attribution bug. Got: {status!r} {detail!r}",
        )
        self.assertNotIn(
            "#99", detail,
            f"detail must not cite the neighbour PR's number as evidence: {detail!r}",
        )
        self.assertEqual(
            status, "unavailable",
            f"no match for the certified sha -> honest 'unavailable' "
            f"(#1166's status shape is unchanged by this slice); got {status!r}",
        )
        self.assertIn(
            SHA_X[:8], detail,
            f"detail must name the REQUESTED (certified) sha, not the "
            f"neighbour's: {detail!r}",
        )

    def test_downstream_fallback_refuses_no_green_written(self):
        """Companion check: the record-green.sh 'unavailable' fallback
        (unchanged, per slice #1197 out-of-bounds) refuses and writes NO
        develop_green event when the local pytest fallback also fails to
        verify green -- already proven, UNMODIFIED, by
        tests/test_record_green_ci_trust_1161.py. This test only asserts
        that companion coverage is still present, keeping the two files
        linked without duplicating the fake-gh-at-bash-level scenario."""
        content = (REPO_ROOT / "tests" / "test_record_green_ci_trust_1161.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("test_unavailable_plus_pytest_fail_refuses", content)
        self.assertIn("_assert_no_event_written", content)


class TestNoShaPathByteIdentical(unittest.TestCase):
    """Freeze test (the slicer's named risk): the sha=None / omitted-sha
    call path must derive develop_sha via git rev-parse exactly as before
    -- the sha kwarg is strictly additive."""

    def test_omitted_sha_still_derives_locally(self):
        h = _reload_health()
        fake = _FakeGhFetch(
            pr_list=[{"number": 7, "mergeCommit": {"oid": SHA_Y}}],
            checks_by_pr={7: [{"name": "ci", "state": "SUCCESS"}]},
        )
        fake_git = mock.Mock()
        fake_git.returncode = 0
        fake_git.stdout = SHA_Y + "\n"
        with mock.patch.object(h, "_health_gh_fetch", fake), \
                mock.patch("subprocess.run", return_value=fake_git) as mock_sp:
            status, detail = h._fetch_github_ci_conclusion(str(REPO_ROOT))

        mock_sp.assert_called_once()
        self.assertEqual(mock_sp.call_args[0][0][:2], ["git", "rev-parse"])
        self.assertEqual(status, "pass")
        self.assertIn("#7", detail)

    def test_sha_none_explicit_same_as_omitted(self):
        h = _reload_health()
        fake = _FakeGhFetch(
            pr_list=[{"number": 7, "mergeCommit": {"oid": SHA_Y}}],
            checks_by_pr={7: [{"name": "ci", "state": "SUCCESS"}]},
        )
        fake_git = mock.Mock()
        fake_git.returncode = 0
        fake_git.stdout = SHA_Y + "\n"
        with mock.patch.object(h, "_health_gh_fetch", fake), \
                mock.patch("subprocess.run", return_value=fake_git):
            result_omitted = h._fetch_github_ci_conclusion(str(REPO_ROOT))
        with mock.patch.object(h, "_health_gh_fetch", fake), \
                mock.patch("subprocess.run", return_value=fake_git):
            result_explicit_none = h._fetch_github_ci_conclusion(str(REPO_ROOT), sha=None)
        self.assertEqual(result_omitted, result_explicit_none)


class TestRecordGreenShWiresShaExplicitly(unittest.TestCase):
    """Wiring check: tools/record-green.sh's real (non-injected) code path
    must pass its resolved DEV_SHA into _fetch_github_ci_conclusion as the
    sha= kwarg -- otherwise the health.py fix is dead code from the actual
    production caller's perspective."""

    def test_record_green_sh_passes_sha_kwarg(self):
        content = (REPO_ROOT / "tools" / "record-green.sh").read_text(encoding="utf-8")
        self.assertIn(
            "sha='$DEV_SHA'", content,
            "tools/record-green.sh must thread its resolved DEV_SHA into "
            "_fetch_github_ci_conclusion(..., sha=...) -- see ADR-0079 D2 / "
            f"#1192. Script content:\n{content}",
        )


if __name__ == "__main__":
    unittest.main()
