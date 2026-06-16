"""
Regression tests for issue #861 — measurement/rule-layer honesty (4 fixes).

Tests FAIL before the fixes and PASS after (ADR-0067 D2 test-first ordering):

  Fix 1: health_summary aggregation in _build_status():
    - Correct PASS/WARN/FAIL tally from a synthetic /api/health-shaped payload.
    - Computing-sentinel returns nulls, not silent 0s.

  Fix 2: DOCS-8 supersession annotations (decisions/README.md).
    - check_docs8_supersession_notes() returns PASS after adding annotations
      for ADR-0006 (superseded by ADR-0009) and ADR-0020 (superseded by ADR-0025).

  Fix 3: R-SENSITIVE-DETECTOR text is updated to reflect advisory-interim status.
    - Detail string references advisory/ADR-0071 D3 rescoping.

  Fix 4: HOOK-INTEGRITY rolling window semantics.
    - FAIL on a recent-missing-ok fixture (genuine drift).
    - N/A / no-count on a no-recent fixture (dark hooks are HOOK-LIVENESS's job).
    - Must NOT produce permanent FAIL from pre-fix historical beacons.

Runner: stdlib unittest + pytest compatible.
  python -m pytest tests/test_measurement_honesty_861.py -v
"""

import json
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
HEALTH_PY = REPO_ROOT / "dashboard" / "health.py"
SERVER_PY = REPO_ROOT / "dashboard" / "server.py"
DECISIONS_README = REPO_ROOT / "decisions" / "README.md"


def _run_dashboard_script(script: str, timeout: int = 30) -> "subprocess.CompletedProcess":
    """Run a Python snippet with dashboard/ on sys.path; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT / "dashboard"),
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Fix 1 — health_summary tally from synthetic payload
# ---------------------------------------------------------------------------

class TestHealthSummaryAggregation(unittest.TestCase):
    """The _build_status() health_summary must correctly tally PASS/WARN/FAIL
    from the real /api/health payload structure (groups with 'checks' lists).
    """

    def test_health_summary_tally_synthetic_payload(self):
        """Synthetic payload with known counts must produce exact tally.

        Payload structure mirrors the real /api/health response:
          - auditMeta: {"checks": [3 PASS, 1 WARN]}
          - substrateMeta: {"checks": [1 FAIL, 1 WARN, 2 PASS]}
          - verificationIntegrity: {"checks": [2 PASS]}
          - registryIntegrity: {"checks": []}
          - hygieneIntegrity: {"checks": []}
          - auditSubagents: per-agent dicts — NOT a top-level checks list; skip
          - cascadeFinder: {"available": True, "detail": "..."} — no checks; skip
        Expected: pass=7 (3+2+2), warn=2 (1+1), fail=1
        """
        script = r"""
import sys, json
from pathlib import Path
_repo = str(Path(__file__).parent.parent) if '__file__' in dir() else '.'
sys.path.insert(0, _repo + '/dashboard')
import server
import health as _health_mod

synthetic_payload = {
    "auditMeta": {"checks": [
        {"id": "DOCS-1", "result": "PASS"},
        {"id": "DOCS-2", "result": "PASS"},
        {"id": "DOCS-3", "result": "PASS"},
        {"id": "DOCS-4", "result": "WARN"},
    ]},
    "substrateMeta": {"checks": [
        {"id": "HOOK-INTEGRITY", "result": "FAIL"},
        {"id": "HOOK-LIVENESS", "result": "WARN"},
        {"id": "ISOLATION-GROUP", "result": "PASS"},
        {"id": "RULE-COVERAGE", "result": "PASS"},
    ]},
    "verificationIntegrity": {"checks": [
        {"id": "BLIND-DISPATCH", "result": "PASS"},
        {"id": "MERGE-INTEGRITY", "result": "PASS"},
    ]},
    "registryIntegrity": {"checks": []},
    "hygieneIntegrity": {"checks": []},
    "auditSubagents": {
        "reviewer": {"type": "critic", "checks": [{"id": "AS-CRIT-1", "result": "PASS"}]}
    },
    "cascadeFinder": {"available": True, "detail": "ok"},
}

_orig = _health_mod.serve_health
_health_mod.serve_health = lambda: (synthetic_payload, False)
try:
    result = server._build_status()
    summary = result.get("health_summary", {})
    print(json.dumps(summary))
finally:
    _health_mod.serve_health = _orig
""".replace("__file__", "'placeholder'")
        # Build the actual script with the correct path
        actual_script = f"""
import sys, json
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
import server

synthetic_payload = {{
    "auditMeta": {{"checks": [
        {{"id": "DOCS-1", "result": "PASS"}},
        {{"id": "DOCS-2", "result": "PASS"}},
        {{"id": "DOCS-3", "result": "PASS"}},
        {{"id": "DOCS-4", "result": "WARN"}},
    ]}},
    "substrateMeta": {{"checks": [
        {{"id": "HOOK-INTEGRITY", "result": "FAIL"}},
        {{"id": "HOOK-LIVENESS", "result": "WARN"}},
        {{"id": "ISOLATION-GROUP", "result": "PASS"}},
        {{"id": "RULE-COVERAGE", "result": "PASS"}},
    ]}},
    "verificationIntegrity": {{"checks": [
        {{"id": "BLIND-DISPATCH", "result": "PASS"}},
        {{"id": "MERGE-INTEGRITY", "result": "PASS"}},
    ]}},
    "registryIntegrity": {{"checks": []}},
    "hygieneIntegrity": {{"checks": []}},
    "auditSubagents": {{
        "reviewer": {{"type": "critic", "checks": [{{"id": "AS-CRIT-1", "result": "PASS"}}]}}
    }},
    "cascadeFinder": {{"available": True, "detail": "ok"}},
}}

# Patch the module-level alias used by _build_status (imported as _serve_health_cached)
_orig = server._serve_health_cached
server._serve_health_cached = lambda: (synthetic_payload, False)
try:
    result = server._build_status()
    summary = result.get("health_summary", {{}})
    print(json.dumps(summary))
finally:
    server._serve_health_cached = _orig
"""
        proc = _run_dashboard_script(actual_script, timeout=60)
        self.assertEqual(0, proc.returncode, f"script failed: {proc.stderr[:300]}")
        counts = json.loads(proc.stdout.strip())
        self.assertEqual(7, counts.get("pass"), f"expected 7 pass, got {counts}")
        self.assertEqual(2, counts.get("warn"), f"expected 2 warn, got {counts}")
        self.assertEqual(1, counts.get("fail"), f"expected 1 fail, got {counts}")

    def test_health_summary_computing_sentinel_returns_nulls(self):
        """When serve_health returns {status: computing}, health_summary must use None.

        The fix: detect the computing sentinel and return null for each field
        rather than silently reporting 0/0/0 (which falsely implies 0 checks ran).
        """
        script = f"""
import sys, json
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
import server
import health as _health_mod

_orig = _health_mod.serve_health
_health_mod.serve_health = lambda: ({{"status": "computing"}}, True)
try:
    result = server._build_status()
    summary = result.get("health_summary", {{}})
    print(json.dumps(summary))
finally:
    _health_mod.serve_health = _orig
"""
        proc = _run_dashboard_script(script, timeout=60)
        self.assertEqual(0, proc.returncode, f"script failed: {proc.stderr[:300]}")
        summary = json.loads(proc.stdout.strip())
        # When computing, all fields must be None (not 0)
        for key in ("pass", "warn", "fail"):
            self.assertIsNone(
                summary.get(key),
                msg=(
                    f"health_summary.{key} must be null (not 0) when health is still computing; "
                    f"got {summary.get(key)!r}. Reporting 0/0/0 is dishonest."
                ),
            )

    def test_health_summary_from_real_payload_nonzero(self):
        """Real health payload must yield nonzero total check count.

        Waits for background thread, then tallies. Skipped if still computing after 20s.
        """
        script = f"""
import sys, json, threading
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
import health as _health_mod

_health_mod._health_computing = True
t = threading.Thread(target=_health_mod._health_background, daemon=True)
t.start()
t.join(timeout=20)

data, _ = _health_mod.serve_health()
if data.get("status") == "computing":
    print(json.dumps({{"skip": True, "reason": "still computing after 20s"}}))
else:
    pass_count = 0
    warn_count = 0
    fail_count = 0
    for group_key, group_val in data.items():
        if not isinstance(group_val, dict):
            continue
        checks_list = group_val.get("checks", None)
        if isinstance(checks_list, list):
            for chk in checks_list:
                r = chk.get("result", "")
                if r == "PASS": pass_count += 1
                elif r == "WARN": warn_count += 1
                elif r == "FAIL": fail_count += 1
    print(json.dumps({{"pass": pass_count, "warn": warn_count, "fail": fail_count, "skip": False}}))
"""
        proc = _run_dashboard_script(script, timeout=45)
        self.assertEqual(0, proc.returncode, f"script failed: {proc.stderr[:300]}")
        result = json.loads(proc.stdout.strip())
        if result.get("skip"):
            self.skipTest(f"health still computing: {result.get('reason')}")
        total = result["pass"] + result["warn"] + result["fail"]
        self.assertGreater(
            total, 0,
            msg=f"Expected nonzero check count from real payload; got {result}.",
        )


# ---------------------------------------------------------------------------
# Fix 2 — DOCS-8 supersession annotations
# ---------------------------------------------------------------------------

class TestDocs8SupersessionAnnotations(unittest.TestCase):
    """decisions/README.md must have 'superseded by' annotations for:
      - ADR-0006 row (superseded by ADR-0009)
      - ADR-0020 row (superseded by ADR-0025)
    """

    def _run_docs8(self) -> dict:
        script = f"""
import sys, json
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
from health import check_docs8_supersession_notes
print(json.dumps(check_docs8_supersession_notes()))
"""
        proc = _run_dashboard_script(script)
        self.assertEqual(0, proc.returncode, f"check_docs8 script failed: {proc.stderr[:300]}")
        return json.loads(proc.stdout.strip())

    def test_docs8_passes_after_annotations(self):
        """check_docs8_supersession_notes() must return PASS after adding annotations."""
        result = self._run_docs8()
        self.assertEqual(
            "PASS",
            result.get("result"),
            msg=f"DOCS-8 is still WARN/FAIL. Detail: {result.get('detail')}",
        )

    def test_adr_0006_row_has_superseded_by(self):
        """ADR-0006 row in decisions/README.md must contain 'superseded by'."""
        text = DECISIONS_README.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "0006-" in line and line.startswith("|"):
                self.assertIn(
                    "superseded by",
                    line.lower(),
                    msg=(
                        f"ADR-0006 row in decisions/README.md missing 'superseded by' annotation.\n"
                        f"Row: {line}"
                    ),
                )
                return
        self.fail("ADR-0006 row not found in decisions/README.md")

    def test_adr_0020_row_has_superseded_by(self):
        """ADR-0020 row in decisions/README.md must contain 'superseded by'."""
        text = DECISIONS_README.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "0020-" in line and line.startswith("|"):
                self.assertIn(
                    "superseded by",
                    line.lower(),
                    msg=(
                        f"ADR-0020 row in decisions/README.md missing 'superseded by' annotation.\n"
                        f"Row: {line}"
                    ),
                )
                return
        self.fail("ADR-0020 row not found in decisions/README.md")


# ---------------------------------------------------------------------------
# Fix 3 — R-SENSITIVE-DETECTOR text reflects advisory-interim status
# ---------------------------------------------------------------------------

class TestRSensitiveDetectorText(unittest.TestCase):
    """check_r_sensitive_detector() detail must reference advisory/ADR-0071,
    not claim R-SENSITIVE is a hard-block gate (rescoped to advisory per ADR-0071 D3).
    """

    def _run_check(self) -> dict:
        script = f"""
import sys, json
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')
from health import check_r_sensitive_detector
print(json.dumps(check_r_sensitive_detector()))
"""
        proc = _run_dashboard_script(script, timeout=45)
        self.assertEqual(0, proc.returncode, f"check script failed: {proc.stderr[:300]}")
        return json.loads(proc.stdout.strip())

    def test_detail_mentions_advisory_or_adr_0071(self):
        """The detail string must mention 'advisory' or 'ADR-0071' to reflect rescoping."""
        result = self._run_check()
        detail = result.get("detail", "")
        self.assertTrue(
            "advisory" in detail.lower() or "adr-0071" in detail.lower(),
            msg=(
                f"R-SENSITIVE-DETECTOR detail must mention 'advisory' or 'ADR-0071' "
                f"(R-SENSITIVE was rescoped to advisory per ADR-0071 D3, slice #853). "
                f"Got: {detail!r}"
            ),
        )

    def test_detail_does_not_say_r_sensitive_active_without_advisory(self):
        """Detail must not say 'R-SENSITIVE ACTIVE (ADR-0064 D4)' without advisory qualifier."""
        result = self._run_check()
        detail = result.get("detail", "")
        import re
        old_pattern = re.compile(r'R-SENSITIVE ACTIVE \(ADR-0064 D4\)', re.IGNORECASE)
        if old_pattern.search(detail):
            # If the old exact pattern is present, it MUST also mention advisory
            self.assertTrue(
                "advisory" in detail.lower() or "adr-0071" in detail.lower(),
                msg=(
                    f"Detail says 'R-SENSITIVE ACTIVE (ADR-0064 D4)' without advisory qualifier. "
                    f"Update to reflect ADR-0071 D3 rescoping. Got: {detail!r}"
                ),
            )


# ---------------------------------------------------------------------------
# Fix 4 — HOOK-INTEGRITY rolling window semantics
# ---------------------------------------------------------------------------

class TestHookIntegrityRollingWindow(unittest.TestCase):
    """check_hook_integrity() must use a rolling-window view so old pre-fix
    beacons don't produce permanent FAIL.

    Semantics per slice #861:
    - hook with recent attempts but missing ok → FAIL (genuine drift)
    - hook with NO recent beacons → not a FAIL (dark-detection = HOOK-LIVENESS)
    - hooks with all ok matching attempts within window → PASS
    """

    # Named constant window — tests assert it exists in health.py
    WINDOW_DAYS = 7

    def _ts(self, days_ago: float = 0.0) -> str:
        """Return an ISO timestamp N days in the past (UTC)."""
        dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _run_check_with_fixture_entries(self, entries: list, window_days: int = 7) -> dict:
        """Run the HOOK-INTEGRITY check logic inline against a fixture entries list.

        This calls a small inline version of the check with the given entries,
        mirroring the logic after the rolling-window fix. We test the logic
        by calling a helper script that imports health.py and runs the internal
        logic with a patched log reader.
        """
        entries_json = json.dumps(entries)
        script = f"""
import sys, json, tempfile, os
from pathlib import Path
sys.path.insert(0, r'{REPO_ROOT / "dashboard"}')

# Write fixture to a temp file, then patch the log path in check_hook_integrity
import health as _health_mod
import tempfile

entries = {entries_json}

with tempfile.TemporaryDirectory() as tmp:
    # Create the expected dir structure: tmp/.claude/logs/hook-fires.jsonl
    logs_dir = Path(tmp) / ".claude" / "logs"
    logs_dir.mkdir(parents=True)
    log_path = logs_dir / "hook-fires.jsonl"
    with log_path.open("w") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\\n")

    # Patch the repo root used by check_hook_integrity
    _orig_root = _health_mod._HEALTH_REPO_ROOT
    _health_mod._HEALTH_REPO_ROOT = Path(tmp)
    try:
        result = _health_mod.check_hook_integrity()
        print(json.dumps(result))
    finally:
        _health_mod._HEALTH_REPO_ROOT = _orig_root
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT / "dashboard"),
            timeout=15,
        )
        if proc.returncode != 0:
            return {"error": proc.stderr[:300], "result": "ERROR"}
        return json.loads(proc.stdout.strip())

    def test_fail_on_recent_attempt_without_ok(self):
        """Recent attempt beacons with no matching ok → FAIL (genuine drift)."""
        entries = [
            {"ts": self._ts(0.1), "hook": "log-tool-event.sh", "status": "attempt"},
            {"ts": self._ts(0.2), "hook": "log-tool-event.sh", "status": "attempt"},
            # NO ok beacon → drift within window
        ]
        result = self._run_check_with_fixture_entries(entries)
        self.assertEqual(
            "FAIL",
            result.get("result"),
            msg=(
                f"Expected FAIL for hook with recent attempts but no ok beacon; "
                f"got {result.get('result')!r}. Detail: {result.get('detail')}"
            ),
        )

    def test_not_fail_on_only_old_beacons(self):
        """Old beacons outside rolling window must NOT produce FAIL.

        Dark-hook detection is HOOK-LIVENESS's job, not HOOK-INTEGRITY's.
        """
        old_days = self.WINDOW_DAYS + 2
        entries = [
            # Old attempts with no ok — but OUTSIDE the rolling window
            {"ts": self._ts(old_days), "hook": "log-tool-event.sh", "status": "attempt"},
            {"ts": self._ts(old_days + 0.1), "hook": "log-tool-event.sh", "status": "attempt"},
        ]
        result = self._run_check_with_fixture_entries(entries)
        self.assertNotEqual(
            "FAIL",
            result.get("result"),
            msg=(
                f"HOOK-INTEGRITY must NOT FAIL when all beacons are outside the rolling window "
                f"(>{self.WINDOW_DAYS} days old). Old beacons must not count. "
                f"Dark-hook detection = HOOK-LIVENESS. "
                f"Got: {result.get('result')!r}. Detail: {result.get('detail')}"
            ),
        )

    def test_pass_on_recent_ok_matches_attempt(self):
        """Recent attempts all have matching ok beacons → PASS."""
        entries = [
            {"ts": self._ts(0.1), "hook": "log-tool-event.sh", "status": "attempt"},
            {"ts": self._ts(0.1), "hook": "log-tool-event.sh", "status": "ok"},
            {"ts": self._ts(0.5), "hook": "log-tool-event.sh", "status": "attempt"},
            {"ts": self._ts(0.5), "hook": "log-tool-event.sh", "status": "ok"},
        ]
        result = self._run_check_with_fixture_entries(entries)
        self.assertEqual(
            "PASS",
            result.get("result"),
            msg=(
                f"Expected PASS when all recent attempts have matching ok beacons; "
                f"got {result.get('result')!r}. Detail: {result.get('detail')}"
            ),
        )

    def test_old_attempts_no_ok_plus_recent_ok_matches(self):
        """Old drift + recent clean should not produce FAIL from old history."""
        old_days = self.WINDOW_DAYS + 2
        entries = [
            # Old: attempt without ok (pre-fix history) — must be ignored
            {"ts": self._ts(old_days), "hook": "log-tool-event.sh", "status": "attempt"},
            # Recent: clean
            {"ts": self._ts(0.5), "hook": "log-tool-event.sh", "status": "attempt"},
            {"ts": self._ts(0.5), "hook": "log-tool-event.sh", "status": "ok"},
        ]
        result = self._run_check_with_fixture_entries(entries)
        self.assertEqual(
            "PASS",
            result.get("result"),
            msg=(
                f"Old drift outside window must NOT cause FAIL if recent window is clean; "
                f"got {result.get('result')!r}. Detail: {result.get('detail')}"
            ),
        )

    def test_window_constant_exists_in_health_py(self):
        """health.py must define a named constant for the HOOK-INTEGRITY window."""
        import re
        text = HEALTH_PY.read_text(encoding="utf-8")
        self.assertTrue(
            bool(re.search(r'_HOOK_INTEGRITY_WINDOW', text, re.IGNORECASE)),
            msg=(
                "health.py must define a named constant for the HOOK-INTEGRITY rolling window "
                "(e.g. _HOOK_INTEGRITY_WINDOW_DAYS = 7). This documents the semantic contract."
            ),
        )


if __name__ == "__main__":
    unittest.main()
