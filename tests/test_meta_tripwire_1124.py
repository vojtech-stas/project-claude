"""
tests/test_meta_tripwire_1124.py

Regression tests for root-cause #1124 — META-TRIPWIRE unpassable for
guardrail-touching promotion batches because tools/promote.sh never wrote
the ack marker check_meta_tripwire() required.

Rule #13 / ADR-0067 D3: this test file is committed BEFORE the fix. Test (a)
below (and the promote.sh writer test) FAIL against current code and PASS
after the fix lands.

Two halves under test:
  1. dashboard/health.py check_meta_tripwire() — must treat the CURRENT
     existence of the .claude/PROMOTE_OK sentinel (at the canonical
     git-common-dir root) as a valid ack for a guardrail-touching batch,
     in addition to the existing retrospective last-promotion-record ack
     check (preserved as historical-bypass detection).
  2. tools/promote.sh — the appended promotion event must carry "ack":true
     (truthful: that line is only reached after the sentinel was verified
     present in step 0a and consumed/removed in step 3b).

Test seam: rather than adding a new env-var override, these tests use the
EXISTING documented seam — health.py's _telemetry_log_root() resolves the
canonical root relative to the module-level `_HEALTH_REPO_ROOT`, and that
constant is designed to be monkeypatched by test suites (see its docstring:
"ensures test suites that patch _HEALTH_REPO_ROOT to a temp dir will receive
the expected (patched) fallback"). Patching it to a scratch git repo makes
both the promotion-events read AND the sentinel-resolution AND the
guardrail-file git-log walk all operate against the scratch repo — no real
`.claude/logs/*` or real `.claude/PROMOTE_OK` is ever touched.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_meta_tripwire_1124.py -v
"""

import importlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PROMOTE_SH = REPO_ROOT / "tools" / "promote.sh"

_DASHBOARD_DIR = str(REPO_ROOT / "dashboard")
if _DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, _DASHBOARD_DIR)


# ---------------------------------------------------------------------------
# Shared git helpers (mirrors the pattern used by test_promote_ack_880.py /
# test_promote_gate_parse_1036.py — each test file owns its own scaffolding).
# ---------------------------------------------------------------------------

def _git(*args, cwd=None, check=True):
    return subprocess.run(
        ["git"] + list(args), cwd=cwd, check=check,
        capture_output=True, text=True,
    )


def _to_bash_path(win_path: str) -> str:
    """Convert a Windows path to a bash-compatible POSIX path for Git Bash."""
    if platform.system() != "Windows":
        return win_path
    try:
        result = subprocess.run(
            ["cygpath", "-u", win_path], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    p = win_path.replace("\\", "/")
    p = re.sub(r"^([A-Za-z]):/", lambda m: f"/{m.group(1).lower()}/", p)
    return p


def _make_scratch_repo(tmp_dir: str) -> tuple[str, str]:
    """Build a minimal scratch repo with a 'last promotion' commit followed
    by an unpromoted commit that touches a guardrail path.

    Returns (repo_path, last_promotion_sha).
    """
    repo = os.path.join(tmp_dir, "repo")
    os.makedirs(repo)
    _git("init", "-b", "main", repo)
    _git("-C", repo, "config", "user.email", "test@example.com")
    _git("-C", repo, "config", "user.name", "Test")

    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("hello")
    _git("-C", repo, "add", "README.md")
    _git("-C", repo, "commit", "-m", "init")
    last_sha = _git("-C", repo, "rev-parse", "HEAD").stdout.strip()

    hooks_dir = os.path.join(repo, ".claude", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    with open(os.path.join(hooks_dir, "dummy.sh"), "w") as f:
        f.write("#!/bin/bash\necho hi\n")
    _git("-C", repo, "add", ".claude/hooks/dummy.sh")
    _git("-C", repo, "commit", "-m", "touch guardrail hook (unpromoted batch)")

    return repo, last_sha


def _write_promotion_event(repo: str, sha: str, ack: bool | None = None) -> None:
    """Write a single promotion event to the scratch repo's workflow-events.jsonl."""
    logs_dir = os.path.join(repo, ".claude", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    event = {
        "v": 2, "ts": "2026-08-02T11:00:00Z", "session_id": "test",
        "src": "orchestrator", "event": "promotion",
        "from": "develop", "to": "main", "sha": sha,
    }
    if ack is not None:
        event["ack"] = ack
    with open(os.path.join(logs_dir, "workflow-events.jsonl"), "w") as f:
        f.write(json.dumps(event) + "\n")


def _create_sentinel(repo: str) -> str:
    sentinel_dir = os.path.join(repo, ".claude")
    os.makedirs(sentinel_dir, exist_ok=True)
    sentinel = os.path.join(sentinel_dir, "PROMOTE_OK")
    with open(sentinel, "w") as f:
        f.write("")
    return sentinel


def _call_check_meta_tripwire(repo_path: str) -> dict:
    """Reload health.py fresh, patch _HEALTH_REPO_ROOT to the scratch repo,
    call check_meta_tripwire(), then restore the module to its real state.
    """
    old_override = os.environ.pop("_META_TRIPWIRE_RESULT_OVERRIDE", None)
    try:
        import health as h
        importlib.reload(h)
        h._HEALTH_REPO_ROOT = Path(repo_path)
        return h.check_meta_tripwire()
    finally:
        import health as h
        importlib.reload(h)  # restore real _HEALTH_REPO_ROOT for subsequent tests
        if old_override is not None:
            os.environ["_META_TRIPWIRE_RESULT_OVERRIDE"] = old_override


# ---------------------------------------------------------------------------
# Group 1: (a) sentinel present + last promotion WITHOUT ack -> PASS
#          KEY regression — FAILS against current code (returns FAIL).
# ---------------------------------------------------------------------------

class TestSentinelPresentPassesGuardrailBatch(unittest.TestCase):
    """A guardrail-touching batch with a CURRENTLY-present PROMOTE_OK sentinel
    must PASS, even if the last promotion record carries no ack marker.
    """

    def test_sentinel_present_no_last_ack_passes(self):
        with tempfile.TemporaryDirectory(prefix="mt1124_a_") as tmp:
            repo, last_sha = _make_scratch_repo(tmp)
            _write_promotion_event(repo, last_sha, ack=None)
            _create_sentinel(repo)

            result = _call_check_meta_tripwire(repo)

            self.assertEqual(
                result.get("result"), "PASS",
                f"guardrail-touching batch with a present PROMOTE_OK sentinel "
                f"must PASS regardless of the last promotion's ack status; "
                f"got: {result!r} (this is the #1124 regression — promote.sh "
                f"never wrote an ack marker, so the retrospective check alone "
                f"always FAILs for every guardrail batch after the first)",
            )
            self.assertIn(
                "sentinel", result.get("detail", "").lower(),
                f"PASS detail should mention the sentinel as the reason; "
                f"got: {result.get('detail')!r}",
            )


# ---------------------------------------------------------------------------
# Group 2: (b) NO sentinel + last promotion without ack -> FAIL
#          Bypass-detection class preserved (passes before AND after).
# ---------------------------------------------------------------------------

class TestNoSentinelNoAckStillFails(unittest.TestCase):
    """Without a sentinel and without a last-promotion ack, the guardrail
    batch must still FAIL — the historical-bypass detection class must not
    regress.
    """

    def test_no_sentinel_no_ack_fails(self):
        with tempfile.TemporaryDirectory(prefix="mt1124_b_") as tmp:
            repo, last_sha = _make_scratch_repo(tmp)
            _write_promotion_event(repo, last_sha, ack=None)
            # No sentinel created.

            result = _call_check_meta_tripwire(repo)

            self.assertEqual(
                result.get("result"), "FAIL",
                f"guardrail-touching batch with NO sentinel and NO last-promotion "
                f"ack must still FAIL (bypass-detection class preserved); "
                f"got: {result!r}",
            )


# ---------------------------------------------------------------------------
# Group 3: (c) last promotion record WITH ack:true + no sentinel -> PASS
#          Forward path preserved (already passes pre-fix; guards regression).
# ---------------------------------------------------------------------------

class TestAckedLastPromotionPasses(unittest.TestCase):
    """A last-promotion record carrying ack:true must PASS even with no
    sentinel currently present (the forward path once promote.sh writes it).
    """

    def test_acked_last_promotion_passes(self):
        with tempfile.TemporaryDirectory(prefix="mt1124_c_") as tmp:
            repo, last_sha = _make_scratch_repo(tmp)
            _write_promotion_event(repo, last_sha, ack=True)
            # No sentinel created.

            result = _call_check_meta_tripwire(repo)

            self.assertEqual(
                result.get("result"), "PASS",
                f"guardrail-touching batch whose last promotion record carries "
                f"ack:true must PASS even with no sentinel present; "
                f"got: {result!r}",
            )


# ---------------------------------------------------------------------------
# Group 4: promote.sh writer — appended event must carry "ack":true
#          KEY regression — FAILS against current promote.sh (no ack field).
# ---------------------------------------------------------------------------

def _make_bare_and_work_repo(tmp_dir: str) -> str:
    """Bare-origin + clone, with main and develop branches (mirrors the
    scaffolding in test_promote_ack_880.py / test_promote_gate_parse_1036.py).
    """
    bare = os.path.join(tmp_dir, "bare.git")
    os.makedirs(bare)
    _git("init", "--bare", "-b", "main", bare)

    work = os.path.join(tmp_dir, "work")
    _git("clone", bare, work)
    _git("-C", work, "config", "user.email", "test@example.com")
    _git("-C", work, "config", "user.name", "Test")

    current = subprocess.run(
        ["git", "-C", work, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    if current != "main":
        _git("-C", work, "checkout", "-b", "main")

    with open(os.path.join(work, "README.md"), "w") as f:
        f.write("hello")
    _git("-C", work, "add", "README.md")
    _git("-C", work, "commit", "-m", "init")
    _git("-C", work, "push", "-u", "origin", "HEAD:main")

    _git("-C", work, "checkout", "-b", "develop")
    with open(os.path.join(work, "CHANGES.md"), "w") as f:
        f.write("dev change")
    _git("-C", work, "add", "CHANGES.md")
    _git("-C", work, "commit", "-m", "dev commit")
    _git("-C", work, "push", "-u", "origin", "develop")

    return work


def _make_stub_health(tmpdir: str) -> str:
    """Stub health.py CLI that always reports the gate open."""
    stub_path = os.path.join(tmpdir, "stub_health.sh")
    with open(stub_path, "w", newline="\n") as f:
        f.write("#!/bin/bash\n")
        f.write('printf "%s\\n" "PASS: RELEASE-READY - gate open: stub for #1124 test"\n')
        f.write("exit 0\n")
    mode = os.stat(stub_path).st_mode
    os.chmod(stub_path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return _to_bash_path(stub_path)


class TestPromoteShWritesAckField(unittest.TestCase):
    """promote.sh's appended promotion event must carry \"ack\":true.

    KEY regression: before the fix, promote.sh writes the event with no ack
    field at all, so this test FAILS. After the fix, the appended line
    contains "ack":true.
    """

    def test_promotion_event_carries_ack_true(self):
        with tempfile.TemporaryDirectory(prefix="mt1124_writer_") as tmp:
            work = _make_bare_and_work_repo(tmp)

            sentinel_dir = os.path.join(work, ".claude")
            os.makedirs(sentinel_dir, exist_ok=True)
            with open(os.path.join(sentinel_dir, "PROMOTE_OK"), "w") as f:
                f.write("")

            stub_posix_path = _make_stub_health(tmp)
            env = os.environ.copy()
            env["PROMOTE_HEALTH_CMD"] = f"bash {stub_posix_path}"
            env["MSYS_NO_PATHCONV"] = "1"
            env["_PROMOTE_SH_SKIP_PUSH"] = "1"

            result = subprocess.run(
                ["bash", str(PROMOTE_SH)],
                cwd=work, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                result.returncode, 0,
                f"promote.sh must exit 0 in this scenario (sentinel present, "
                f"gate stubbed open).\nstdout={result.stdout!r}\n"
                f"stderr={result.stderr!r}",
            )

            events_log = os.path.join(work, ".claude", "logs", "workflow-events.jsonl")
            self.assertTrue(
                os.path.exists(events_log),
                f"promote.sh must append a promotion event to {events_log!r}; "
                f"file does not exist.\nstdout={result.stdout!r}",
            )
            with open(events_log) as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            self.assertTrue(lines, "workflow-events.jsonl must contain at least one line")
            last_event = json.loads(lines[-1])
            self.assertEqual(
                last_event.get("event"), "promotion",
                f"last event must be a promotion event; got: {last_event!r}",
            )
            self.assertIs(
                last_event.get("ack"), True,
                f"promote.sh's appended promotion event must carry \"ack\":true "
                f"(truthful: this line is only reachable after the sentinel was "
                f"verified present and consumed); got event: {last_event!r}",
            )


if __name__ == "__main__":
    unittest.main()
