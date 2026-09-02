"""
Live-fire regression tests for slice #1310 (PRD #1266, ADR-0083 D1/D2/D5).

These are NOT grep tests. Each case executes the real hook script with a real
stdin payload and then reads the beacon file the hook actually wrote, so a
regression in the emitter is caught by the emitter's own output rather than by
its source text.

What is asserted:

1. `pre-tool-edit.sh` writes EXACTLY ONE terminal beacon per fire, at every one
   of its seven exit sites, and never two (ADR-0083 D1). The seven sites are
   the seven `exit` statements in the script:
     - inside `emit_ask`      -> terminal `status:"ok"`, `outcome:"ask"`
     - inside `emit_deny`     -> terminal `status:"ok"`, `outcome:"deny"`
     - subagent-context skip  -> terminal `status:"ok"`, no gate decision
     - parser-failure path    -> terminal `status:"ERROR"` (already existed;
                                 asserted here so the new trap cannot double-emit)
     - allowlisted file_path  -> terminal `status:"ok"`, no gate decision
     - empty file_path        -> terminal `status:"ok"`, no gate decision
     - untracked file_path    -> terminal `status:"ok"`, no gate decision

2. `status` never carries a gate decision (ADR-0083 D2): the closed lifecycle
   set is {attempt, ok, ERROR}. A DENY is a *completion*, so it reports
   `status:"ok"` with the decision in the additive `outcome` field. A hook that
   forges a crash signature to express a policy decision fails these tests.

3. `stop-reviewer-gate.sh`'s DENY path (exit 2) emits `status:"ok"` +
   `outcome:"deny"`, and its stderr states the observation plus BOTH states
   consistent with it (reviewer not yet dispatched; or the PR is correctly
   awaiting its prerequisite codebase-critic pass per PIP-013) plus the
   `STOP_GATE_BYPASS=1` escape (ADR-0083 D5).

4. Rule #21 (fixture discipline): every fire in this module writes to a scratch
   `WORKFLOW_LOG_DIR`; the production `.claude/logs/hook-fires.jsonl` must never
   contain this module's synthetic session id.

Preconditions are checked, never assumed. When `bash`, `jq`, `python3`, or a
usable `gh` shim is unavailable, the affected test SKIPS WITH AN EXPLICIT
REASON — it never passes silently on an unexercised code path.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_terminal_beacons_1310.py -v
  python -m unittest tests.test_terminal_beacons_1310 -v
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRE_TOOL_EDIT = REPO_ROOT / ".claude" / "hooks" / "pre-tool-edit.sh"
STOP_GATE = REPO_ROOT / ".claude" / "hooks" / "stop-reviewer-gate.sh"

# Synthetic id — must never reach a production data store (CLAUDE.md rule #21).
FIXTURE_SID = "live-fire-1310-fixture"

BASH = shutil.which("bash")
JQ = shutil.which("jq")
PY3 = shutil.which("python3") or shutil.which("python")

# The closed lifecycle vocabulary (ADR-0083 D2). Anything else is a schema break.
ALLOWED_STATUS = {"attempt", "ok", "ERROR"}
TERMINAL_STATUS = {"ok", "ERROR"}


def _path_without(tool: str) -> str:
    """Return $PATH with every directory that provides `tool` removed.

    Used instead of prepending a shim so no path-form conversion is needed on
    the Windows/Git-Bash boundary — entries are only dropped, never rewritten.
    """
    keep = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        if shutil.which(tool, path=entry):
            continue
        keep.append(entry)
    return os.pathsep.join(keep)


def _read_beacons(log_dir: Path, hook_name: str):
    """Parse hook-fires.jsonl, keeping only records emitted by `hook_name`."""
    path = log_dir / "hook-fires.jsonl"
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("hook") == hook_name:
            records.append(rec)
    return records


class _HookFireMixin:
    def _require_bash(self):
        if BASH is None:
            self.skipTest(
                "SKIPPED (not passed): `bash` is not resolvable from this Python "
                "process, so the hook could not be executed at all. The terminal-beacon "
                "contract is UNVERIFIED on this machine."
            )

    def _fire(self, script: Path, payload, hook_name: str, extra_env=None, path_override=None):
        """Execute a hook for real and return (CompletedProcess, [beacon records])."""
        self._require_bash()
        log_dir = Path(tempfile.mkdtemp(prefix="beacon-1310-"))
        self.addCleanup(shutil.rmtree, log_dir, ignore_errors=True)

        env = dict(os.environ)
        env["WORKFLOW_LOG_DIR"] = str(log_dir)
        env["CLAUDE_PROJECT_DIR"] = str(REPO_ROOT)
        # These two would short-circuit the very paths under test.
        env.pop("CLAUDE_AGENT_TYPE", None)
        env.pop("STOP_GATE_BYPASS", None)
        if path_override is not None:
            env["PATH"] = path_override
        if extra_env:
            env.update(extra_env)

        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        proc = subprocess.run(
            [BASH, str(script)],
            input=stdin,
            env=env,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        return proc, _read_beacons(log_dir, hook_name)

    def _assert_single_terminal(self, beacons, expected_status, expected_outcome, site):
        """Core ADR-0083 D1/D2 assertion: one attempt, exactly one terminal, closed status."""
        self.assertTrue(
            beacons,
            f"[{site}] hook wrote NO beacons at all — attempt beacon missing too.",
        )
        for rec in beacons:
            self.assertIn(
                rec.get("status"), ALLOWED_STATUS,
                f"[{site}] status {rec.get('status')!r} is outside the closed set "
                f"{sorted(ALLOWED_STATUS)} (ADR-0083 D2). Record: {rec}",
            )

        attempts = [r for r in beacons if r.get("status") == "attempt"]
        terminals = [r for r in beacons if r.get("status") in TERMINAL_STATUS]

        self.assertEqual(
            len(attempts), 1,
            f"[{site}] expected exactly 1 attempt beacon, got {len(attempts)}: {beacons}",
        )
        self.assertEqual(
            len(terminals), 1,
            f"[{site}] expected exactly 1 terminal beacon (ADR-0083 D1), got "
            f"{len(terminals)}. A missing terminal means the exit site is silent; two "
            f"means the trap double-fired. Records: {beacons}",
        )

        terminal = terminals[0]
        self.assertEqual(
            terminal.get("status"), expected_status,
            f"[{site}] terminal status mismatch. Records: {beacons}",
        )
        # ADR-0083 D2: the gate decision lives in `outcome`, never in `status`.
        self.assertEqual(
            terminal.get("outcome", ""), expected_outcome,
            f"[{site}] terminal `outcome` mismatch — a policy decision must be recorded "
            f"additively in `outcome`, never forged into `status`. Records: {beacons}",
        )
        return terminal


class TestPreToolEditTerminalBeacons(_HookFireMixin, unittest.TestCase):
    """One terminal beacon at each of pre-tool-edit.sh's seven exit sites."""

    HOOK = "pre-tool-edit"

    def _payload(self, file_path):
        return {
            "session_id": FIXTURE_SID,
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path} if file_path is not None else {},
        }

    # --- site 1: emit_ask ---------------------------------------------------

    def test_site_emit_ask_emits_ok_with_outcome_ask(self):
        """Rule-#10 escalate-to-ask fallback. Driven offline by removing `gh`
        from PATH, which makes the script skip the spec-gate block entirely and
        fall through to emit_ask — no network call, no issue lookup."""
        if JQ is None:
            self.skipTest(
                "SKIPPED (not passed): `jq` is unavailable, so the script would take the "
                "jq-missing branch instead of the branch under test. emit_ask's terminal "
                "beacon is UNVERIFIED here."
            )
        no_gh = _path_without("gh")
        proc, beacons = self._fire(
            PRE_TOOL_EDIT, self._payload("CLAUDE.md"), self.HOOK, path_override=no_gh
        )
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        self.assertIn(
            '"permissionDecision":"ask"', proc.stdout.replace(" ", ""),
            f"expected an ask decision on stdout, got: {proc.stdout!r}",
        )
        self._assert_single_terminal(beacons, "ok", "ask", "emit_ask")

    # --- site 2: emit_deny --------------------------------------------------

    def test_site_emit_deny_emits_ok_with_outcome_deny(self):
        """Spec-gate DENY on a branch that matches no <type>/<issue#>- pattern.

        `gh` must merely be present (the script tests for it); the deny fires in
        the else-branch before `gh` is ever invoked, so this stays offline.
        """
        if JQ is None:
            self.skipTest(
                "SKIPPED (not passed): `jq` is unavailable, so the script short-circuits "
                "to the jq-missing ask branch and never reaches emit_deny. The deny "
                "terminal beacon is UNVERIFIED here."
            )
        if shutil.which("gh") is None:
            self.skipTest(
                "SKIPPED (not passed): `gh` is unavailable, so the spec-gate block is "
                "skipped entirely and emit_deny is unreachable. UNVERIFIED here."
            )
        proc, beacons = self._fire(
            PRE_TOOL_EDIT,
            self._payload("CLAUDE.md"),
            self.HOOK,
            extra_env={"BRANCH": "branch-matching-no-known-pattern"},
        )
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        self.assertIn(
            '"permissionDecision":"deny"', proc.stdout.replace(" ", ""),
            f"expected a deny decision on stdout, got: {proc.stdout!r}",
        )
        terminal = self._assert_single_terminal(beacons, "ok", "deny", "emit_deny")
        # The load-bearing half of ADR-0083 D1: a DENY is a completion, not a crash.
        self.assertNotEqual(
            terminal.get("status"), "ERROR",
            "a deliberate DENY must not be reported as an ERROR (forged crash signature)",
        )

    # --- site 3: subagent-context skip -------------------------------------

    def test_site_subagent_skip_emits_ok_terminal(self):
        proc, beacons = self._fire(
            PRE_TOOL_EDIT,
            self._payload("CLAUDE.md"),
            self.HOOK,
            extra_env={"CLAUDE_AGENT_TYPE": "implementer"},
        )
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        self._assert_single_terminal(beacons, "ok", "", "subagent-skip")

    # --- site 4: parser-failure ERROR path ---------------------------------

    def test_site_parser_failure_emits_exactly_one_error_terminal(self):
        """Pre-existing ERROR terminal. Asserted so the new EXIT trap cannot
        append a second terminal on top of it."""
        proc, beacons = self._fire(
            PRE_TOOL_EDIT, '{"session_id": "' + FIXTURE_SID + '", NOT-JSON', self.HOOK
        )
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        terminal = self._assert_single_terminal(beacons, "ERROR", "", "parser-failure")
        self.assertEqual(terminal.get("session_id"), FIXTURE_SID)

    # --- site 5: allowlisted path ------------------------------------------

    def test_site_allowlisted_path_emits_ok_terminal(self):
        proc, beacons = self._fire(
            PRE_TOOL_EDIT, self._payload(".claude/logs/hook-fires.jsonl"), self.HOOK
        )
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        self._assert_single_terminal(beacons, "ok", "", "allowlist")

    # --- site 6: empty file_path -------------------------------------------

    def test_site_empty_file_path_emits_ok_terminal(self):
        if JQ is None:
            self.skipTest(
                "SKIPPED (not passed): `jq` is unavailable, so the script exits at the "
                "jq-missing ask branch before reaching the empty-path exit. UNVERIFIED here."
            )
        proc, beacons = self._fire(PRE_TOOL_EDIT, self._payload(None), self.HOOK)
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        self._assert_single_terminal(beacons, "ok", "", "empty-file-path")

    # --- site 7: untracked file --------------------------------------------

    def test_site_untracked_file_emits_ok_terminal(self):
        if JQ is None:
            self.skipTest(
                "SKIPPED (not passed): `jq` is unavailable, so the script exits at the "
                "jq-missing ask branch before reaching the untracked-file exit. "
                "UNVERIFIED here."
            )
        untracked = ".claude/this-path-is-deliberately-untracked-1310.tmp"
        self.assertFalse(
            (REPO_ROOT / untracked).exists(),
            "fixture path must not exist in the repo",
        )
        proc, beacons = self._fire(PRE_TOOL_EDIT, self._payload(untracked), self.HOOK)
        self.assertEqual(proc.returncode, 0, f"stderr={proc.stderr}")
        self._assert_single_terminal(beacons, "ok", "", "untracked-file")


class TestStopReviewerGateDenyBeacon(_HookFireMixin, unittest.TestCase):
    """ADR-0083 D1/D2/D5 for stop-reviewer-gate.sh's blocking (exit 2) path."""

    HOOK = "stop-reviewer-gate"

    def _gh_shim_path(self):
        """Create a `gh` shim that reports one open PR with zero APPROVE comments.

        Returns a PATH with the shim first, or None when the shim cannot be made
        to win command lookup (in which case the caller skips loudly).
        """
        shim_dir = Path(tempfile.mkdtemp(prefix="ghshim-1310-"))
        self.addCleanup(shutil.rmtree, shim_dir, ignore_errors=True)
        shim = shim_dir / "gh"
        shim.write_text(
            "#!/bin/sh\n"
            '# Test double for slice #1310: one open PR, zero VERDICT: APPROVE comments.\n'
            'case "$1 $2" in\n'
            '  "pr list") echo \'[{"number":999999}]\' ;;\n'
            '  "pr view") echo 0 ;;\n'
            '  *) echo "" ;;\n'
            "esac\n"
            "exit 0\n",
            encoding="utf-8",
            newline="\n",
        )
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        new_path = str(shim_dir) + os.pathsep + os.environ.get("PATH", "")
        # Verify the precondition rather than assuming it.
        probe_env = dict(os.environ)
        probe_env["PATH"] = new_path
        probe = subprocess.run(
            [BASH, "-c", "command -v gh"],
            env=probe_env, capture_output=True, text=True, timeout=60,
        )
        resolved = probe.stdout.strip()
        if probe.returncode != 0 or shim_dir.name not in resolved:
            return None
        return new_path

    def test_deny_path_emits_ok_status_with_outcome_deny(self):
        self._require_bash()
        if JQ is None:
            self.skipTest(
                "SKIPPED (not passed): `jq` is unavailable, so the gate soft-degrades to "
                "an ERROR beacon and never reaches the DENY path. UNVERIFIED here."
            )
        path_override = self._gh_shim_path()
        if path_override is None:
            self.skipTest(
                "SKIPPED (not passed): the `gh` test double could not be made to win "
                "command lookup in bash, so the blocking path could not be driven. The "
                "DENY terminal beacon is UNVERIFIED here."
            )
        proc, beacons = self._fire(
            STOP_GATE,
            {"session_id": FIXTURE_SID, "stop_hook_active": False},
            self.HOOK,
            path_override=path_override,
        )
        self.assertEqual(
            proc.returncode, 2,
            f"expected the gate to block with exit 2; got {proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        terminal = self._assert_single_terminal(beacons, "ok", "deny", "stop-gate-deny")
        self.assertEqual(terminal.get("session_id"), FIXTURE_SID)

    def test_deny_stderr_names_both_consistent_states_and_the_escape(self):
        """ADR-0083 D5: the message states the observation and the states
        consistent with it, never a single cause it cannot distinguish."""
        self._require_bash()
        if JQ is None:
            self.skipTest(
                "SKIPPED (not passed): `jq` is unavailable, so the DENY message was never "
                "produced. UNVERIFIED here."
            )
        path_override = self._gh_shim_path()
        if path_override is None:
            self.skipTest(
                "SKIPPED (not passed): the `gh` test double could not be made to win "
                "command lookup in bash. The DENY message is UNVERIFIED here."
            )
        proc, _ = self._fire(
            STOP_GATE,
            {"session_id": FIXTURE_SID, "stop_hook_active": False},
            self.HOOK,
            path_override=path_override,
        )
        err = proc.stderr
        self.assertIn("999999", err, "the message must name the PR(s) it observed")
        low = err.lower()
        # State (a): the reviewer has not been dispatched yet.
        self.assertIn("not been dispatched", low,
                      f"first consistent state not named in: {err!r}")
        # State (b): the PR is correctly awaiting codebase-critic first (PIP-013).
        self.assertIn("codebase-critic", low,
                      f"second consistent state not named in: {err!r}")
        self.assertIn("PIP-013", err, f"the PIP-013 basis is not cited in: {err!r}")
        # The escape hatch stays discoverable.
        self.assertIn("STOP_GATE_BYPASS=1", err,
                      f"the bypass escape is not offered in: {err!r}")

    def test_deny_message_does_not_assert_a_single_undistinguishable_cause(self):
        """The pre-ADR-0083 wording ordered one corrective action as if the cause
        were known. That imperative must be gone (ADR-0083 D5)."""
        needle = "dispatch reviewer subagent before declaring done"
        offending = [
            (n, line.strip())
            for n, line in enumerate(
                STOP_GATE.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            )
            if needle in line
        ]
        self.assertEqual(
            offending, [],
            "the single-cause imperative must be replaced by an observation + the "
            f"states consistent with it (ADR-0083 D5); still present at: {offending}",
        )


class TestFixtureDiscipline(unittest.TestCase):
    """CLAUDE.md rule #21 — this module's synthetic data must never reach a
    production data store."""

    def test_production_beacon_log_has_no_fixture_session_id(self):
        prod = REPO_ROOT / ".claude" / "logs" / "hook-fires.jsonl"
        if not prod.exists():
            self.skipTest(
                "SKIPPED (not passed): no production beacon log on this machine, so the "
                "no-leak property could not be observed."
            )
        text = prod.read_text(encoding="utf-8", errors="replace")
        self.assertNotIn(
            FIXTURE_SID, text,
            "synthetic live-fire session id leaked into the production beacon log — "
            "every fire in this module must be redirected via WORKFLOW_LOG_DIR (rule #21)",
        )


if __name__ == "__main__":
    unittest.main()
