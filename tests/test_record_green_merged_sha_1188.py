"""
tests/test_record_green_merged_sha_1188.py

Regression test for root-cause capture #1183 / slice #1188: the
pr-merge -> record-green chain must certify the CONFIRMED MERGE sha (the
one GitHub's REST API just reported), never a local `origin/develop`
remote-tracking ref that may be stale by the time the chain fires
(#1163's ci-trust fast path made the chain fire 2-6s post-merge, which
widened the exposure -- fast emission + stale local ref = systematic
off-by-one-merge attribution; 13/23 merged develop shas had NO
develop_green span at all).

Per ADR-0067 D2/D3 (rule #13 root-cause regression rider): this test
commit PRECEDES the fix commit. It is WRITTEN TO FAIL on pre-fix code
(tools/pipe/pr-merge's `_chain_record_green` drops the confirmed merge
sha on the floor and re-invokes tools/pipe/record-green with no sha
argument at all -- which then falls back to resolving the LOCAL
`origin/develop` ref, unrelated to the sha that was just merged) and to
PASS after the fix (the confirmed merge oid is threaded through to both
the v2 develop_green event and the v3 develop_green span).

Technique: the fake `merge_commit_sha` returned by the stubbed `gh api
repos/.../pulls/<n>` call is a value that can NEVER coincide with this
worktree's real `origin/develop` sha (a 40-char hex git object id) --
so a "deliberately stale local origin/develop ref" falls straight out
of the existing fixture with NO extra fixture-repo machinery required
(exactly the pattern named in slice #1188's acceptance criteria: imitate
tests/test_pr_merge_record_green_chain_1134.py's fake-gh/override seams).

Fixture discipline (rule #21): every write in this file targets a temp
path via TRACE_LOG_OVERRIDE / RECORD_GREEN_TEST_LOG_PATH -- never a real
`.claude/logs/*` store. RECORD_GREEN_CI_STATUS + RECORD_GREEN_PYTEST_CMD
short-circuit record-green.sh's own gh/pytest sub-calls before any nested
subprocess spawns (the #1119/#1134 PATH-stub lesson).

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_record_green_merged_sha_1188.py -v
"""
import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PR_MERGE = REPO_ROOT / "tools" / "pipe" / "pr-merge"

# A merge_commit_sha that can never collide with a real 40-char-hex git sha
# resolvable in this worktree -- proves the certified sha came from the
# GitHub API response threaded through the chain, not from any local ref.
_FAKE_MERGE_SHA = "fakemergedsha1188-not-a-real-git-object"

_SUBPROCESS_TIMEOUT_S = 30

_FAKE_GH_BODY = """import sys, os, json

args = sys.argv[1:]
sub0 = args[0] if len(args) > 0 else ""
sub1 = args[1] if len(args) > 1 else ""

if sub0 == "pr" and sub1 == "view":
    out = os.environ.get("FAKE_GH_VIEW_JSON", json.dumps({"comments": []}))
    print(out)
    sys.exit(int(os.environ.get("FAKE_GH_VIEW_EXIT", "0")))
elif sub0 == "pr" and sub1 == "merge":
    exit_code = int(os.environ.get("FAKE_GH_MERGE_EXIT", "0"))
    err = os.environ.get("FAKE_GH_MERGE_STDERR", "")
    if err:
        print(err, file=sys.stderr)
    sys.exit(exit_code)
elif sub0 == "pr" and sub1 == "update-branch":
    sys.exit(int(os.environ.get("FAKE_GH_UPDATE_BRANCH_EXIT", "0")))
elif sub0 == "pr" and sub1 == "checks":
    exit_code = int(os.environ.get("FAKE_GH_CHECKS_EXIT", "0"))
    out = os.environ.get("FAKE_GH_CHECKS_STDOUT", "")
    if out:
        print(out)
    sys.exit(exit_code)
elif sub0 == "api":
    out = os.environ.get("FAKE_GH_API_JSON", "{}")
    print(out)
    sys.exit(int(os.environ.get("FAKE_GH_API_EXIT", "0")))
else:
    sys.exit(0)
"""


def _write_fake_gh(dirpath):
    if platform.system() == "Windows":
        impl_path = os.path.join(dirpath, "_fake_gh_impl.py")
        with open(impl_path, "w", encoding="utf-8") as f:
            f.write(_FAKE_GH_BODY)
        bat_path = os.path.join(dirpath, "gh.bat")
        with open(bat_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{impl_path}" %*\r\n')
    else:
        sh_path = os.path.join(dirpath, "gh")
        with open(sh_path, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write(_FAKE_GH_BODY)
        os.chmod(sh_path, 0o755)
    return dirpath


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


class MergedShaChainTestBase(unittest.TestCase):
    def setUp(self):
        if not PR_MERGE.exists():
            self.skip_reason = f"tools/pipe/pr-merge not found at {PR_MERGE}"
        else:
            self.skip_reason = None
        self.tmp = tempfile.mkdtemp(prefix="record_green_merged_sha_1188_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, args, env_updates):
        if self.skip_reason:
            self.fail(self.skip_reason)
        env = os.environ.copy()
        env.update(env_updates)
        cmd = [sys.executable, str(PR_MERGE)] + args
        return subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
            timeout=_SUBPROCESS_TIMEOUT_S,
        )

    def _base_env(self, log_path, fake_gh_dir, v2_log_path):
        return {
            "PATH": fake_gh_dir + os.pathsep + os.environ.get("PATH", ""),
            "TRACE_LOG_OVERRIDE": log_path,
            "FAKE_GH_VIEW_JSON": json.dumps({"comments": [
                {"body": "VERDICT: APPROVE\nREASON: ok\nROUND: 1\nCRITIC: reviewer"},
            ]}),
            "FAKE_GH_API_JSON": json.dumps({"merged": True, "merge_commit_sha": _FAKE_MERGE_SHA}),
            "PR_MERGE_BUDGET_S": "20",
            # Deterministic record-green success -- bypasses its internal gh
            # lookup AND its real pytest run (see tests/test_pr_merge_record_
            # green_chain_1134.py's docstring for why this is mandatory).
            "RECORD_GREEN_CI_STATUS": "pass",
            "RECORD_GREEN_PYTEST_CMD": "true",
            "RECORD_GREEN_TEST_LOG_PATH": v2_log_path,
        }


class TestChainCertifiesConfirmedMergeSha(MergedShaChainTestBase):
    """The chained record-green call must certify the CONFIRMED MERGE sha
    (from the GitHub API response pr-merge already holds), not whatever a
    stale local `origin/develop` ref happens to resolve to.

    FAILS on pre-fix code: tools/pipe/pr-merge's `_chain_record_green`
    ignores the confirmed merge sha entirely, so both the v2 event and the
    v3 span end up certifying this worktree's real local `origin/develop`
    sha instead of `_FAKE_MERGE_SHA`.
    """

    def test_default_mode_v2_event_carries_pushed_sha(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._base_env(log_path, fake_gh_dir, v2_log_path)
        env_updates["FAKE_GH_MERGE_EXIT"] = "0"

        result = self._run(["900"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

        v2_lines = _read_jsonl(v2_log_path)
        develop_green = [e for e in v2_lines if e.get("event") == "develop_green"]
        self.assertEqual(len(develop_green), 1, f"expected exactly one develop_green event, got {v2_lines}")
        self.assertEqual(
            develop_green[0].get("sha"), _FAKE_MERGE_SHA,
            f"develop_green v2 event must certify the CONFIRMED MERGE sha "
            f"({_FAKE_MERGE_SHA!r}), not a locally-resolved origin/develop "
            f"ref; got {develop_green[0].get('sha')!r}",
        )

    def test_default_mode_v3_span_carries_pushed_sha(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._base_env(log_path, fake_gh_dir, v2_log_path)
        env_updates["FAKE_GH_MERGE_EXIT"] = "0"

        result = self._run(["901"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

        v3_lines = _read_jsonl(log_path)
        green_spans = [s for s in v3_lines if s.get("kind") == "develop_green"]
        self.assertEqual(len(green_spans), 1, f"expected exactly one develop_green span, got {v3_lines}")
        self.assertEqual(
            green_spans[0].get("attrs", {}).get("sha"), _FAKE_MERGE_SHA,
            f"develop_green v3 span attrs.sha must equal the CONFIRMED MERGE "
            f"sha ({_FAKE_MERGE_SHA!r}), not a locally-resolved origin/develop "
            f"ref; got {green_spans[0].get('attrs')!r}",
        )

    def test_confirm_mode_carries_pushed_sha_in_both_event_and_span(self):
        fake_gh_dir = _write_fake_gh(self.tmp)
        log_path = os.path.join(self.tmp, "trace-v3.jsonl")
        v2_log_path = os.path.join(self.tmp, "workflow-events.jsonl")
        env_updates = self._base_env(log_path, fake_gh_dir, v2_log_path)

        result = self._run(["--confirm", "902"], env_updates)
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout!r} stderr={result.stderr!r}")

        v2_lines = _read_jsonl(v2_log_path)
        develop_green = [e for e in v2_lines if e.get("event") == "develop_green"]
        self.assertEqual(len(develop_green), 1, f"expected exactly one develop_green event, got {v2_lines}")
        self.assertEqual(develop_green[0].get("sha"), _FAKE_MERGE_SHA)

        v3_lines = _read_jsonl(log_path)
        green_spans = [s for s in v3_lines if s.get("kind") == "develop_green"]
        self.assertEqual(len(green_spans), 1, f"expected exactly one develop_green span, got {v3_lines}")
        self.assertEqual(green_spans[0].get("attrs", {}).get("sha"), _FAKE_MERGE_SHA)


if __name__ == "__main__":
    unittest.main()
