"""
dashboard/comparison.py — per-run comparison engine (ADR-0053 D3).

Pure function compare(SPEC, trail) → report.
No side effects; no I/O; no imports outside stdlib.

Edge states (per-edge):
  confirmed     — predicate evaluated True; carries counts/timestamps/rounds
  missing       — predicate evaluated False AND run demonstrably progressed
                  past the stage (not in-flight; provably skipped/failed)
  not-reached   — run is in-flight OR ended before this stage; NEVER red
  not-exercised — conditional edge whose condition never arose; NEVER red
  unexpected    — evidence in the trail that matches no declared edge

Violation detectors (first-class outputs):
  unreviewed_merge — merged PR with zero verdict comments and no trivial label
  no_closes_slice  — PR merged but no closingIssuesReferences pointing to a slice
  slice_no_pr      — slice issue closed without a known closing PR

Run PASS := every required:always github-tier edge on the traversed path is
            "confirmed" AND zero violations.
"""

from __future__ import annotations


def get_spec_for_compare() -> dict:
    """Import and return the spine spec (for use by CLI and server)."""
    import sys
    from pathlib import Path

    dashboard_dir = str(Path(__file__).resolve().parent)
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)
    from pipeline_spec import get_spec  # noqa: PLC0415
    return get_spec()


# ---------------------------------------------------------------------------
# Predicate evaluators — one per spine edge
# ---------------------------------------------------------------------------

def _eval_prd_has_slice(trail: dict) -> tuple[str, str]:
    """E-PRD-SLICE: PRD has ≥1 sub-issue (slice)."""
    slices = trail.get("slices", [])
    if slices:
        return "confirmed", f"{len(slices)} slice(s)"
    # If PRD is open and has no slices, it's not-reached (could be in-flight)
    if not trail.get("prd_closed_at"):
        return "not-reached", "PRD open, no slices yet"
    return "missing", "PRD closed with no sub-issues found"


def _eval_slice_closed_by_pr(trail: dict) -> tuple[str, str]:
    """E-SLICE-PR: ≥1 slice closed via closingIssuesReferences on a PR."""
    slices = trail.get("slices", [])
    if not slices:
        return "not-reached", "no slices"

    confirmed_count = sum(1 for s in slices if s.get("closing_pr_number"))
    total = len(slices)

    if confirmed_count == total:
        return "confirmed", f"{confirmed_count}/{total} slices have closing PR"
    if confirmed_count > 0:
        # Some slices have PRs — partially confirmed; count as confirmed if any
        # In-flight slices may still be open
        open_without_pr = [
            s for s in slices
            if not s.get("closing_pr_number") and not s.get("closed_at")
        ]
        if open_without_pr:
            return "confirmed", (
                f"{confirmed_count}/{total} slices have closing PR; "
                f"{len(open_without_pr)} open (in-flight)"
            )
        return "missing", (
            f"{confirmed_count}/{total} slices have closing PR; "
            f"{total - confirmed_count} closed without PR link"
        )
    # No slices have PRs
    if not trail.get("prd_closed_at"):
        return "not-reached", "PRD open, slices have no PR links yet"
    return "missing", "no slice-to-PR links found (closingIssuesReferences empty)"


def _eval_pr_has_verdict(trail: dict) -> tuple[str, str]:
    """E-PR-REVIEW: ≥1 PR has a reviewer verdict comment."""
    prs = trail.get("prs", {})
    if not prs:
        # No PRs fetched yet
        if not trail.get("prd_closed_at"):
            return "not-reached", "no PRs fetched; PRD in-flight"
        return "missing", "no PRs found in trail"

    with_verdicts = [
        pr for pr in prs.values() if pr.get("verdict_count", 0) > 0
    ]
    trivial_only = [
        pr for pr in prs.values()
        if pr.get("is_trivial") and pr.get("verdict_count", 0) == 0
    ]
    non_trivial_no_verdict = [
        pr for pr in prs.values()
        if not pr.get("is_trivial") and pr.get("verdict_count", 0) == 0
    ]

    total = len(prs)
    if with_verdicts or trivial_only:
        detail_parts = []
        if with_verdicts:
            detail_parts.append(f"{len(with_verdicts)}/{total} PRs have verdicts")
        if trivial_only:
            detail_parts.append(f"{len(trivial_only)} trivial-lane (no verdict needed)")
        return "confirmed", "; ".join(detail_parts)

    if non_trivial_no_verdict and not trail.get("prd_closed_at"):
        return "not-reached", f"{total} PR(s), no verdicts yet (in-flight)"
    return "missing", f"{total} non-trivial PR(s) with zero verdicts"


def _eval_reviewed_before_merge(trail: dict) -> tuple[str, str]:
    """E-REVIEW-MERGE: PRs merged after an APPROVE verdict."""
    prs = trail.get("prs", {})
    if not prs:
        if not trail.get("prd_closed_at"):
            return "not-reached", "no PRs; PRD in-flight"
        return "missing", "no PRs in trail"

    merged_prs = [pr for pr in prs.values() if pr.get("merged_at")]
    if not merged_prs:
        return "not-reached", "no PRs merged yet"

    approved_before_merge = [
        pr for pr in merged_prs if pr.get("reviewed_before_merge")
    ]
    trivial_merged = [
        pr for pr in merged_prs if pr.get("is_trivial")
    ]

    if len(approved_before_merge) + len(trivial_merged) == len(merged_prs):
        return "confirmed", (
            f"{len(approved_before_merge)} APPROVE-reviewed merge(s)"
            + (f"; {len(trivial_merged)} trivial-lane" if trivial_merged else "")
        )
    unreviewed = [
        pr for pr in merged_prs
        if not pr.get("reviewed_before_merge") and not pr.get("is_trivial")
    ]
    if approved_before_merge:
        return "confirmed", (
            f"{len(approved_before_merge)}/{len(merged_prs)} reviewed; "
            f"{len(unreviewed)} unreviewed (see violations)"
        )
    return "missing", f"{len(merged_prs)} merged PR(s) but none reviewed before merge"


def _eval_prd_closed(trail: dict) -> tuple[str, str]:
    """E-MERGE-CLOSE-PRD: PRD issue closed after all slices merged."""
    closed_at = trail.get("prd_closed_at")
    if closed_at:
        slices = trail.get("slices", [])
        prs = trail.get("prs", {})
        merged_prs = sum(1 for p in prs.values() if p.get("merged_at"))
        return "confirmed", (
            f"PRD closed at {closed_at}; "
            f"{merged_prs} PR(s) merged; {len(slices)} slice(s)"
        )
    return "not-reached", "PRD still open"


def _eval_block_loop(trail: dict) -> tuple[str, str]:
    """E-REVIEW-BLOCK: ≥1 PR has a BLOCK verdict (followed by revision)."""
    prs = trail.get("prs", {})
    block_count = 0
    for pr in prs.values():
        for v in pr.get("verdicts", []):
            if v.get("verdict") == "BLOCK":
                block_count += 1
                break
    if block_count > 0:
        return "confirmed", f"{block_count} PR(s) had BLOCK round(s)"
    return "not-exercised", "no BLOCK verdicts in this run"


def _eval_trivial_lane(trail: dict) -> tuple[str, str]:
    """E-TRIVIAL-LANE: ≥1 PR has trivial label."""
    prs = trail.get("prs", {})
    trivial_prs = [pr for pr in prs.values() if pr.get("is_trivial")]
    if trivial_prs:
        return "confirmed", f"{len(trivial_prs)} trivial-lane PR(s)"
    return "not-exercised", "no trivial-lane PRs in this run"


# Map edge id → evaluator
_EDGE_EVALUATORS = {
    "E-PRD-SLICE":      _eval_prd_has_slice,
    "E-SLICE-PR":       _eval_slice_closed_by_pr,
    "E-PR-REVIEW":      _eval_pr_has_verdict,
    "E-REVIEW-MERGE":   _eval_reviewed_before_merge,
    "E-MERGE-CLOSE-PRD": _eval_prd_closed,
    "E-REVIEW-BLOCK":   _eval_block_loop,
    "E-TRIVIAL-LANE":   _eval_trivial_lane,
}


# ---------------------------------------------------------------------------
# Violation detectors
# ---------------------------------------------------------------------------

def _detect_unreviewed_merges(trail: dict) -> list[dict]:
    """Detect PRs that were merged without any verdict and are not trivial-lane."""
    violations = []
    prs = trail.get("prs", {})
    for pr in prs.values():
        if (
            pr.get("merged_at")
            and pr.get("verdict_count", 0) == 0
            and not pr.get("is_trivial")
        ):
            violations.append({
                "type": "unreviewed_merge",
                "pr_number": pr["number"],
                "merged_at": pr.get("merged_at", ""),
                "detail": (
                    f"PR #{pr['number']} merged at {pr.get('merged_at', '?')} "
                    f"with zero reviewer verdicts and no trivial label"
                ),
            })
    return violations


def _detect_no_closes_slice(trail: dict) -> list[dict]:
    """Detect PRs that have no closingIssuesReferences pointing to a slice."""
    violations = []
    prs = trail.get("prs", {})
    slice_numbers = {s["number"] for s in trail.get("slices", [])}
    for pr in prs.values():
        closing = set(pr.get("closing_issues", []))
        if not closing.intersection(slice_numbers) and pr.get("merged_at"):
            violations.append({
                "type": "no_closes_slice",
                "pr_number": pr["number"],
                "detail": (
                    f"PR #{pr['number']} merged but no closingIssuesReferences "
                    f"point to a slice in this PRD"
                ),
            })
    return violations


def _detect_slice_no_pr(trail: dict) -> list[dict]:
    """Detect slice issues closed without a known closing PR."""
    violations = []
    for sl in trail.get("slices", []):
        if sl.get("closed_at") and not sl.get("closing_pr_number"):
            violations.append({
                "type": "slice_no_pr",
                "slice_number": sl["number"],
                "detail": (
                    f"Slice #{sl['number']} closed at {sl.get('closed_at', '?')} "
                    f"but no closing PR found via closingIssuesReferences"
                ),
            })
    return violations


# ---------------------------------------------------------------------------
# Main compare function
# ---------------------------------------------------------------------------

def compare(spec: dict, trail: dict) -> dict:
    """Pure comparison function: evaluate spine predicates over the trail.

    Args:
        spec: output of pipeline_spec.get_spec()
        trail: output of collector.get_trail()

    Returns:
        {
          "prd_number": N,
          "run_pass": bool,
          "edges": {
              "E-*": {"state": str, "detail": str, "evidence": str, "required": str}
          },
          "violations": [{type, detail, ...}],
          "unexpected": [],    # currently empty (no unexpected-bucket logic in spine)
        }
    """
    edges_result: dict[str, dict] = {}
    spec_edges = spec.get("edges", [])

    for edge in spec_edges:
        eid = edge["id"]
        evaluator = _EDGE_EVALUATORS.get(eid)
        if evaluator is None:
            # No evaluator for this edge (future edge not yet implemented)
            state = "not-reached"
            detail = "no evaluator implemented yet"
        else:
            try:
                state, detail = evaluator(trail)
            except Exception as exc:
                state = "not-reached"
                detail = f"evaluator error: {exc}"

        edges_result[eid] = {
            "state": state,
            "detail": detail,
            "evidence": edge.get("evidence", "github"),
            "required": edge.get("required", "always"),
        }

    # Violation detection
    violations = (
        _detect_unreviewed_merges(trail)
        + _detect_no_closes_slice(trail)
        + _detect_slice_no_pr(trail)
    )

    # Run PASS: all required:always github-tier edges are "confirmed" AND no violations
    run_pass = (
        all(
            edges_result[e["id"]]["state"] == "confirmed"
            for e in spec_edges
            if e.get("required") == "always" and e.get("evidence") == "github"
        )
        and len(violations) == 0
    )

    return {
        "prd_number": trail.get("prd_number"),
        "run_pass": run_pass,
        "edges": edges_result,
        "violations": violations,
        "unexpected": [],
    }
