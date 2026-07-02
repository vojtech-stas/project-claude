#!/usr/bin/env python3
"""
tools/check-slicer-provenance.py — slicer-provenance guard (PRD #919 slice #922).
Extended in slice #1067 to recognize the rule-#13 root-cause lane.

Verifies that every OPEN GitHub issue labeled `slice` carries the canonical
`Slicer-provenance:` trailer in its body, indicating it was created via the
`/to-issues` slicer + slicer-critic pipeline rather than hand-crafted directly
via `gh issue create` — UNLESS the slice carries the `root-cause` label, in
which case it belongs to the rule #13 lane (root-cause captures promoted
directly to fix-slices), which never passes through the slicer BY DESIGN
(rule #16 only governs PRD-decomposition slices). That narrow exemption is
the ONLY exemption — there is no blanket exemption for any other label.

A missing trailer on a non-root-cause (PRD-decomposition) slice means the
slice bypassed the slicer, violating rule #16 and the prescribed linear flow
(grill-heavy → /to-prd → /to-issues → /ship).

Exit codes:
  0 — all slicer-lane open slice issues have the provenance trailer, and all
      root-cause-lane slices are exempt (or gh unavailable)
  1 — one or more slicer-lane (non-root-cause) open slice issues are missing
      the trailer

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


def is_root_cause_exempt(labels: Optional[list]) -> bool:
    """Return True if the issue's labels grant the rule-#13 root-cause exemption.

    Narrow by design (issue #1067): ONLY the `root-cause` label exempts a
    slice from the Slicer-provenance requirement. No other label (e.g.
    `captured`) grants exemption, and PRD-decomposition slices (the plain
    `slice` label with no `root-cause`) keep the strict requirement.

    Pure, unit-testable — no I/O. Tolerates a falsy/None `labels` value.
    """
    if not labels:
        return False
    for label in labels:
        name = (label or {}).get("name", "")
        if name == "root-cause":
            return True
    return False


def classify_issues(issues: list[dict]) -> dict:
    """Classify issues into three lane buckets (pure, unit-testable — no I/O).

    Returns a dict with:
      slicer_ok         — slicer-lane issues (no root-cause label) that DO
                           carry the Slicer-provenance trailer
      root_cause_exempt — issues carrying the `root-cause` label (rule #13
                           lane); exempt from the trailer requirement
                           regardless of whether they happen to carry one
      missing           — slicer-lane issues (no root-cause label) that lack
                           the trailer; still flagged (PRD-decomposition
                           slices keep the strict requirement)

    An issue with no `labels` key at all defaults to the strict slicer lane
    (fail-safe: absence of label data must never silently exempt a slice).
    """
    slicer_ok: list[int] = []
    root_cause_exempt: list[int] = []
    missing: list[int] = []

    for issue in issues:
        number = issue["number"]
        body = issue.get("body") or ""
        labels = issue.get("labels")

        if is_root_cause_exempt(labels):
            root_cause_exempt.append(number)
        elif body_has_provenance(body):
            slicer_ok.append(number)
        else:
            missing.append(number)

    return {
        "slicer_ok": slicer_ok,
        "root_cause_exempt": root_cause_exempt,
        "missing": missing,
    }


def _fetch_open_slices() -> Optional[list[dict]]:
    """Run `gh issue list --label slice --state open --json number,body,labels`.

    Returns:
      A list of issue dicts (keys: number, body, labels) on success.
      None if gh is unavailable, unauthenticated, or errors.
    """
    try:
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--label", "slice",
                "--state", "open",
                "--json", "number,body,labels",
                "--limit", "200",
            ],
            capture_output=True,
            text=True,
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

    result = classify_issues(issues)
    slicer_ok = result["slicer_ok"]
    root_cause_exempt = result["root_cause_exempt"]
    missing = result["missing"]

    detail = (
        f"{len(slicer_ok)} slicer-lane ok, "
        f"{len(root_cause_exempt)} root-cause-lane exempt, "
        f"{len(missing)} MISSING"
    )

    if missing:
        numbers = ", ".join(f"#{n}" for n in sorted(missing))
        print(
            f"FAIL: slicer-provenance — {detail}: {numbers}",
            file=sys.stderr,
        )
        print(
            "These slices appear to have been created outside the /to-issues "
            "slicer pipeline (rule #16 violation) and do not carry the "
            "`root-cause` label (rule #13 lane exemption).",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: slicer-provenance — {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
