"""
tests/test_pre_tool_bash_gh_merge_nudge_1086.py

New-feature test for slice #1086 (PRD #1075 closing pass): the advisory
deny-guard nudge in .claude/hooks/pre-tool-bash.sh. A raw `gh pr merge`
Bash invocation is warned (systemMessage), NEVER denied — the sanctioned
tools/pipe/pr-merge wrapper remains the recommendation, not a hard block.

Runner: stdlib unittest + pytest compatible.
    python -m pytest tests/test_pre_tool_bash_gh_merge_nudge_1086.py -v
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HOOK = REPO_ROOT / ".claude" / "hooks" / "pre-tool-bash.sh"


def _resolve_jq_dir():
    """Resolve jq's directory via a login-shell bash (sources rc files, so it
    sees PATH entries a bare non-login python-spawned bash would miss) and
    convert to a Windows-native path for env["PATH"] prepending. Returns None
    if jq cannot be located at all."""
    try:
        found = subprocess.run(
            ["bash", "-lc", "command -v jq"], capture_output=True, text=True, timeout=10,
        )
        if found.returncode != 0 or not found.stdout.strip():
            return None
        posix_path = found.stdout.strip()
        win = subprocess.run(
            ["bash", "-lc", f"cygpath -w '{posix_path}'"], capture_output=True, text=True, timeout=10,
        )
        if win.returncode != 0 or not win.stdout.strip():
            return None
        return str(Path(win.stdout.strip()).parent)
    except Exception:
        return None


_JQ_DIR = _resolve_jq_dir()


def _run_hook(command: str):
    """Invoke the hook with the JSON payload delivered via a real temp FILE
    (not an anonymous pipe) on stdin — the hook's `jq ... </dev/stdin` read
    fails ("No such file or directory") when fed an anonymous pipe created by
    a non-MSYS parent process (python.exe), a Windows/MSYS fd-inheritance
    quirk; a genuine file redirection works reliably across that boundary."""
    payload = json.dumps({"tool_input": {"command": command}})
    env = os.environ.copy()
    if _JQ_DIR:
        env["PATH"] = _JQ_DIR + os.pathsep + env.get("PATH", "")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(payload)
        tmp_path = f.name
    try:
        with open(tmp_path, "r", encoding="utf-8") as stdin_f:
            return subprocess.run(
                ["bash", str(HOOK)], stdin=stdin_f, capture_output=True, text=True,
                timeout=15, env=env,
            )
    finally:
        os.unlink(tmp_path)


def _jq_available_in_bash() -> bool:
    """Whether jq is resolvable at all — the hook soft-degrades to a silent
    exit 0 with no output when it can't find jq; skip rather than conflate
    that with a real bug in this environment."""
    return _JQ_DIR is not None


@unittest.skipUnless(_jq_available_in_bash(), "jq not visible to the hook's bash context — soft-degrades without it")
class TestGhPrMergeAdvisoryNudge(unittest.TestCase):
    def test_raw_gh_pr_merge_warns_not_denies(self):
        result = _run_hook("gh pr merge 123 --squash --auto")
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)
        self.assertIn("systemMessage", out, msg=f"expected a warn-only systemMessage, got: {out}")
        self.assertIn("tools/pipe/pr-merge", out["systemMessage"])
        self.assertNotIn("hookSpecificOutput", out, msg="raw gh pr merge must be advisory, never denied")

    def test_wrapper_invocation_not_nudged(self):
        result = _run_hook("python tools/pipe/pr-merge 123")
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout) if result.stdout.strip() else {}
        self.assertNotIn("systemMessage", out, msg=f"the sanctioned wrapper call must not be nudged: {out}")

    def test_push_main_still_denied_not_downgraded(self):
        """Regression guard: adding the advisory nudge must not weaken the
        existing hard deny on `git push origin main` (ADR-0023 D4)."""
        result = _run_hook("git push origin main")
        self.assertEqual(result.returncode, 0)
        out = json.loads(result.stdout)
        self.assertEqual(
            out.get("hookSpecificOutput", {}).get("permissionDecision"), "deny"
        )


if __name__ == "__main__":
    unittest.main()
