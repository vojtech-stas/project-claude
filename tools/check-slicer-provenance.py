#!/usr/bin/env python3
"""
tools/check-slicer-provenance.py — slicer-provenance guard (PRD #919 slice #922).

Verifies that every OPEN GitHub issue labeled `slice` carries the canonical
`Slicer-provenance:` trailer in its body, indicating it was created via the
`/to-issues` slicer + slicer-critic pipeline rather than hand-crafted directly
via `gh issue create`.

A missing trailer means the slice bypassed the slicer, violating rule #16 and
the prescribed linear flow (grill-heavy → /to-prd → /to-issues → /ship).

Exit codes:
  0 — all open slice issues have the provenance trailer (or gh unavailable)
  1 — one or more open slice issues are missing the trailer

Usage:
  python3 tools/check-slicer-provenance.py

CI integration: tools/ci-checks.sh CHECK 19 calls this script directly.

Soft-degrade: if `gh` is missing, unauthenticated, or returns an error,
prints a clear skip message and exits 0 (does NOT fail CI in environments
where gh is unavailable, e.g. forks without GH_TOKEN).
"""

import json
import subprocess
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Windows cp1252 fix (#1050): force stdout/stderr to utf-8 at startup.
#
# On native Windows, sys.stdout/sys.stderr default to the console's
# codepage (typically cp1252), not utf-8. This script prints `gh` issue
# body content that routinely contains non-cp1252 glyphs (em-dashes, curly
# quotes, emoji), so an unguarded print() raises UnicodeEncodeError.
# reconfigure() is available on TextIOWrapper since Python 3.7; guard with
# hasattr for non-TextIOWrapper streams (e.g. when stdout is already
# replaced by a test harness or CI redirector). Deliberately NOT relying
# on an external PYTHONIOENCODING env var — the fix must be self-contained
# in this module. Same bug class + same treatment as #834 (run_evals.py).
# ---------------------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def body_has_provenance(body: str) -> bool:
    """Return True if body contains a Slicer-provenance: trailer.

    The check is case-insensitive and line-anchored: the trailer must start
    a line (possibly after leading whitespace, to tolerate minor indentation).
    This is a pure, unit-testable function — no I/O.

    Examples of matching lines:
      Slicer-provenance: slicer-critic-APPROVED decomposition of PRD #N (round R).
      slicer-provenance: anything
    """
    if not body:
        return False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("slicer-provenance:"):
            return True
    return False


def _fetch_open_slices() -> Optional[list[dict]]:
    """Run `gh issue list --label slice --state open --json number,body`.

    Returns:
      A list of issue dicts (keys: number, body) on success.
      None if gh is unavailable, unauthenticated, or errors.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", "slice",
                "--state", "open",
                "--json", "number,body",
                "--limit", "200",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except FileNotFoundError:
        # gh binary not installed
        print("SKIP: slicer-provenance check — gh not found (soft-degrade)")
        return None
    except subprocess.TimeoutExpired:
        print("SKIP: slicer-provenance check — gh timed out (soft-degrade)")
        return None
    except Exception as e:
        print(f"SKIP: slicer-provenance check — gh error: {e} (soft-degrade)")
        return None

    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        if (
            "not logged" in stderr_lower
            or "authentication" in stderr_lower
            or "unauthorized" in stderr_lower
            or "gh_token" in stderr_lower
            or "token" in stderr_lower
        ):
            print(
                "SKIP: slicer-provenance check — gh unauthenticated "
                "(no GH_TOKEN in CI) (soft-degrade)"
            )
        else:
            print(
                f"SKIP: slicer-provenance check — gh exited {result.returncode}: "
                f"{result.stderr.strip()[:120]} (soft-degrade)"
            )
        return None

    stdout = result.stdout.strip()
    if not stdout:
        # No issues returned; treat as empty list (all pass vacuously)
        return []

    try:
        issues = json.loads(stdout)
    except json.JSONDecodeError:
        print(
            "SKIP: slicer-provenance check — gh returned non-JSON output "
            "(soft-degrade)"
        )
        return None

    return issues


def main() -> int:
    """Main entry point. Returns exit code (0=pass, 1=fail)."""
    issues = _fetch_open_slices()

    if issues is None:
        # Soft-degrade path — skip message already printed
        return 0

    if not issues:
        print("PASS: slicer-provenance — no open slice issues found")
        return 0

    missing = [
        issue["number"]
        for issue in issues
        if not body_has_provenance(issue.get("body") or "")
    ]

    if missing:
        numbers = ", ".join(f"#{n}" for n in sorted(missing))
        print(
            f"FAIL: slicer-provenance — {len(missing)} open slice issue(s) "
            f"lack the Slicer-provenance: trailer: {numbers}",
            file=sys.stderr,
        )
        print(
            "These slices appear to have been created outside the /to-issues "
            "slicer pipeline (rule #16 violation).",
            file=sys.stderr,
        )
        return 1

    print(
        f"PASS: slicer-provenance — all {len(issues)} open slice issue(s) "
        "carry the Slicer-provenance: trailer"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
