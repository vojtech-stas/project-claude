"""
dashboard/collector.py — GitHub artifact trail collector (ADR-0053 D1/D4).

Stdlib-only; shells to `gh` CLI like dashboard/server.py's workitems fetcher.
Reconstructs a complete PRD run trail from GitHub artifacts:
  PRD issue → sub-issues (slices) → PRs (via closingIssuesReferences) →
  PR comments (reviewer verdicts) → merge events + timestamps.

Cache: .claude/logs/trail-cache/prd-<n>.json
  - Closed PRD (closedAt non-null) → cache forever (immutable run)
  - Open PRD → cache for TTL_OPEN_S seconds

Retry: 0s / 2s / 8s backoff on 401/5xx/timeout.
  Sustained failure → collector_status: "auth_dead"

CLI: python dashboard/collector.py --prd N [--compare]
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent
_CACHE_DIR = _REPO_ROOT / ".claude" / "logs" / "trail-cache"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TTL_OPEN_S = 60          # seconds before an open-PRD cache entry is stale
RETRY_DELAYS = [0, 2, 8]  # seconds between retry attempts

# GraphQL query — one batched call per PRD (design-verified ~0.8s/PRD)
_GQL_QUERY = """\
query($n:Int!){
  repository(owner:"vojtech-stas",name:"project-claude"){
    issue(number:$n){
      title
      createdAt
      closedAt
      labels(first:10){nodes{name}}
      comments(first:50){nodes{body createdAt author{login}}}
      subIssues(first:30){
        nodes{
          number
          title
          createdAt
          closedAt
          labels(first:10){nodes{name}}
          comments(first:30){nodes{body createdAt}}
          timelineItems(itemTypes:[CLOSED_EVENT,LABELED_EVENT],first:20){
            nodes{
              __typename
              ... on ClosedEvent{
                createdAt
                closer{
                  __typename
                  ... on PullRequest{number}
                  ... on Commit{abbreviatedOid}
                }
              }
              ... on LabeledEvent{label{name} createdAt}
            }
          }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# CRITIC trailer parse helpers
# ---------------------------------------------------------------------------
_VERDICT_RE = re.compile(
    r'```[^\n]*\n(.*?)```',
    re.DOTALL,
)
_VERDICT_FIELD_RE = re.compile(r'^VERDICT:\s*(APPROVE|BLOCK)\b', re.MULTILINE | re.IGNORECASE)
_ROUND_FIELD_RE = re.compile(r'^ROUND:\s*(\d+)\b', re.MULTILINE)


def _parse_verdict_comment(body: str) -> dict | None:
    """Extract VERDICT/ROUND from a reviewer comment body.

    Returns {"verdict": "APPROVE"|"BLOCK", "round": int|None, "round_inferred": bool}
    or None if no VERDICT field found.

    Tolerant: accepts VERDICT in a fenced block OR bare in the comment body.
    Missing ROUND → None (caller infers from position).
    """
    # Try fenced blocks first (canonical trailer format)
    for block_m in _VERDICT_RE.finditer(body):
        block = block_m.group(1)
        vm = _VERDICT_FIELD_RE.search(block)
        if vm:
            verdict = vm.group(1).upper()
            rm = _ROUND_FIELD_RE.search(block)
            return {
                "verdict": verdict,
                "round": int(rm.group(1)) if rm else None,
                "round_inferred": rm is None,
            }
    # Fallback: bare VERDICT in body (e.g. older format)
    vm = _VERDICT_FIELD_RE.search(body)
    if vm:
        verdict = vm.group(1).upper()
        rm = _ROUND_FIELD_RE.search(body)
        return {
            "verdict": verdict,
            "round": int(rm.group(1)) if rm else None,
            "round_inferred": rm is None,
        }
    return None


def _infer_rounds(verdicts: list[dict]) -> list[dict]:
    """Fill in inferred round numbers for verdicts missing explicit ROUND."""
    result = []
    inferred_counter = 1
    for v in verdicts:
        v = dict(v)
        if v.get("round") is None:
            v["round"] = inferred_counter
            v["round_inferred"] = True
        else:
            inferred_counter = v["round"]
        inferred_counter += 1
        result.append(v)
    return result


# ---------------------------------------------------------------------------
# gh CLI runner with retry
# ---------------------------------------------------------------------------
def _run_gh(args: list[str], timeout: int = 30) -> tuple[str | None, str]:
    """Run a gh command; return (stdout, error_class).

    error_class: "" (success) | "transient" | "auth_dead" | "timeout"

    Retry schedule: RETRY_DELAYS (0s, 2s, 8s).
    auth_dead: all retries exhausted with non-zero exit.
    """
    last_error = "unknown"
    for i, delay in enumerate(RETRY_DELAYS):
        if delay > 0:
            time.sleep(delay)
        try:
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(_REPO_ROOT),
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return result.stdout, ("transient" if i > 0 else "")
            # Non-zero exit — check stderr for auth issues
            stderr = result.stderr.lower()
            if "401" in stderr or "authentication" in stderr or "not logged in" in stderr:
                last_error = "auth_dead"
            else:
                last_error = "transient"
        except subprocess.TimeoutExpired:
            last_error = "timeout"
        except FileNotFoundError:
            return None, "auth_dead"  # gh not installed
        except Exception as e:
            last_error = f"transient:{e}"
    return None, last_error


def _gh_graphql(query: str, variables: dict, timeout: int = 30) -> tuple[dict | None, str]:
    """Run a GraphQL query via gh api graphql. Returns (data_dict, error_class)."""
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        args += ["-F", f"{k}={v}"]
    stdout, err = _run_gh(args, timeout=timeout)
    if stdout is None:
        return None, err
    try:
        obj = json.loads(stdout)
    except Exception:
        return None, "transient:bad_json"
    if "errors" in obj:
        return None, f"transient:graphql_errors:{obj['errors']}"
    return obj.get("data"), ""


def _gh_pr_view(pr_number: int, timeout: int = 20) -> tuple[dict | None, str]:
    """Fetch PR details via gh pr view. Returns (pr_dict, error_class)."""
    args = [
        "pr", "view", str(pr_number),
        "--json",
        "number,createdAt,mergedAt,headRefName,body,comments,closingIssuesReferences",
    ]
    stdout, err = _run_gh(args, timeout=timeout)
    if stdout is None:
        return None, err
    try:
        return json.loads(stdout), ""
    except Exception:
        return None, "transient:bad_json"


# ---------------------------------------------------------------------------
# Trail building
# ---------------------------------------------------------------------------
def _build_slice_trail(slice_node: dict, prd_number: int) -> dict:
    """Build the slice portion of the trail from the GraphQL sub-issue node."""
    slice_num = slice_node["number"]
    slice_title = slice_node.get("title", "")
    created_at = slice_node.get("createdAt", "")
    closed_at = slice_node.get("closedAt")
    labels = [n["name"] for n in (slice_node.get("labels") or {}).get("nodes", [])]

    # Find closing PR via ClosedEvent.closer
    closing_pr_number = None
    closed_event_at = None
    timeline_nodes = (slice_node.get("timelineItems") or {}).get("nodes", [])
    for event in timeline_nodes:
        if event.get("__typename") == "ClosedEvent":
            closer = event.get("closer") or {}
            if closer.get("__typename") == "PullRequest":
                closing_pr_number = closer.get("number")
                closed_event_at = event.get("createdAt")
                break

    return {
        "number": slice_num,
        "title": slice_title,
        "prd_number": prd_number,
        "labels": labels,
        "created_at": created_at,
        "closed_at": closed_at,
        "closed_event_at": closed_event_at,
        "closing_pr_number": closing_pr_number,
        # Raw comments kept for debugging; verdict parsing happens in PR fetch
        "comment_count": len((slice_node.get("comments") or {}).get("nodes", [])),
    }


def _build_pr_trail(pr_number: int) -> tuple[dict | None, str]:
    """Fetch and parse a PR's trail data. Returns (pr_trail, error_class)."""
    pr_data, err = _gh_pr_view(pr_number)
    if pr_data is None:
        return None, err

    # Parse reviewer verdicts from comments
    raw_comments = pr_data.get("comments") or []
    verdicts: list[dict] = []
    for comment in raw_comments:
        body = comment.get("body", "")
        parsed = _parse_verdict_comment(body)
        if parsed is not None:
            parsed["created_at"] = comment.get("createdAt", "")
            verdicts.append(parsed)

    # Infer round numbers for verdicts missing explicit ROUND
    verdicts = _infer_rounds(verdicts)

    # Determine labels (PR body contains Closes #N but we use closingIssuesReferences)
    closing_issues = [
        i.get("number") for i in (pr_data.get("closingIssuesReferences") or [])
        if i.get("number")
    ]

    # Parse trivial label from PR labels if present (PR JSON doesn't include labels
    # via this endpoint — check body for trivial mention as heuristic)
    body = pr_data.get("body", "")
    is_trivial = bool(re.search(r'\btrivial\b', body, re.IGNORECASE))

    merged_at = pr_data.get("mergedAt")
    last_verdict = verdicts[-1] if verdicts else None
    reviewed_before_merge = (
        last_verdict is not None
        and last_verdict["verdict"] == "APPROVE"
        and merged_at is not None
    )

    return {
        "number": pr_number,
        "created_at": pr_data.get("createdAt", ""),
        "merged_at": merged_at,
        "head_ref": pr_data.get("headRefName", ""),
        "closing_issues": closing_issues,
        "verdicts": verdicts,
        "verdict_count": len(verdicts),
        "last_verdict": last_verdict,
        "reviewed_before_merge": reviewed_before_merge,
        "is_trivial": is_trivial,
        "body_excerpt": body[:200],
    }, ""


def collect_trail(prd_number: int) -> dict:
    """Collect the full trail for a PRD. Returns a trail dict.

    Shape:
        {
          "prd_number": N,
          "prd_title": str,
          "prd_created_at": str,
          "prd_closed_at": str|None,
          "prd_labels": [str,...],
          "slices": [{...}, ...],
          "prs": {<pr_number>: {...}, ...},
          "collector_status": "" | "transient" | "auth_dead",
          "wall_time_s": float|None,   # prd closed_at - created_at
        }
    """
    # Step 1: GraphQL batch query
    gql_data, err = _gh_graphql(_GQL_QUERY, {"n": prd_number})
    if gql_data is None:
        return {
            "prd_number": prd_number,
            "collector_status": err,
            "error": f"GraphQL fetch failed: {err}",
        }

    issue = (gql_data.get("repository") or {}).get("issue") or {}
    if not issue:
        return {
            "prd_number": prd_number,
            "collector_status": "transient:no_issue",
            "error": f"Issue #{prd_number} not found",
        }

    prd_title = issue.get("title", "")
    prd_created_at = issue.get("createdAt", "")
    prd_closed_at = issue.get("closedAt")
    prd_labels = [n["name"] for n in (issue.get("labels") or {}).get("nodes", [])]

    # Step 2: Build slice trail entries
    sub_issues_nodes = (issue.get("subIssues") or {}).get("nodes", [])
    slices = []
    candidate_pr_numbers: set[int] = set()
    for node in sub_issues_nodes:
        st = _build_slice_trail(node, prd_number)
        slices.append(st)
        if st["closing_pr_number"]:
            candidate_pr_numbers.add(st["closing_pr_number"])

    # Step 3: Fetch each candidate PR
    prs: dict[int, dict] = {}
    overall_pr_err = ""
    for pr_num in sorted(candidate_pr_numbers):
        pr_trail, pr_err = _build_pr_trail(pr_num)
        if pr_trail is not None:
            prs[pr_num] = pr_trail
        else:
            overall_pr_err = pr_err

    # Step 4: Compute wall time
    wall_time_s = None
    if prd_created_at and prd_closed_at:
        try:
            from datetime import datetime, timezone

            def _parse_dt(s):
                # GitHub uses Z suffix (UTC)
                s = s.replace("Z", "+00:00")
                return datetime.fromisoformat(s)

            t0 = _parse_dt(prd_created_at)
            t1 = _parse_dt(prd_closed_at)
            wall_time_s = (t1 - t0).total_seconds()
        except Exception:
            pass

    collector_status = overall_pr_err or ""

    return {
        "prd_number": prd_number,
        "prd_title": prd_title,
        "prd_created_at": prd_created_at,
        "prd_closed_at": prd_closed_at,
        "prd_labels": prd_labels,
        "slices": slices,
        "prs": {str(k): v for k, v in prs.items()},
        "collector_status": collector_status,
        "wall_time_s": wall_time_s,
    }


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------
def _cache_path(prd_number: int) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"prd-{prd_number}.json"


def _load_cache(prd_number: int) -> dict | None:
    """Return cached trail or None if missing/stale."""
    path = _cache_path(prd_number)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    cached_closed_at = data.get("closed_at")
    # Closed PRD → cache forever
    if cached_closed_at:
        return data.get("trail")

    # Open PRD → check TTL
    fetched_at = data.get("fetched_at", 0)
    if (time.time() - fetched_at) < TTL_OPEN_S:
        return data.get("trail")
    return None


def _save_cache(prd_number: int, trail: dict) -> None:
    """Persist trail to cache file."""
    path = _cache_path(prd_number)
    wrapper = {
        "fetched_at": time.time(),
        "closed_at": trail.get("prd_closed_at"),
        "trail": trail,
    }
    try:
        path.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
    except Exception:
        pass  # cache write failure is non-fatal


def get_trail(prd_number: int, force_refresh: bool = False) -> dict:
    """Get trail for a PRD (cache-first).

    Returns the trail dict. Never raises.
    On persistent failure: returns a trail with collector_status != "".
    """
    if not force_refresh:
        cached = _load_cache(prd_number)
        if cached is not None:
            cached["_from_cache"] = True
            return cached

    trail = collect_trail(prd_number)
    # Only cache if the call itself succeeded (even partial)
    if "error" not in trail or trail.get("prd_title"):
        _save_cache(prd_number, trail)
    return trail


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _format_duration(s: float) -> str:
    if s < 60:
        return f"{s:.0f}s"
    m = int(s) // 60
    sec = int(s) % 60
    if m < 60:
        return f"{m}m{sec:02d}s"
    h = m // 60
    m2 = m % 60
    return f"{h}h{m2:02d}m{sec:02d}s"


def _cli_print_trail(trail: dict, compare: bool = False) -> None:
    """Print a human-readable trail summary to stdout."""
    if "error" in trail and not trail.get("prd_title"):
        print(f"ERROR: {trail['error']}")
        print(f"collector_status: {trail.get('collector_status', 'unknown')}")
        return

    from_cache = trail.get("_from_cache", False)
    cache_note = " [CACHE HIT]" if from_cache else ""
    print(f"PRD #{trail['prd_number']}: {trail['prd_title']}{cache_note}")
    print(f"  created_at: {trail.get('prd_created_at', 'n/a')}")
    print(f"  closed_at:  {trail.get('prd_closed_at', 'open')}")
    wt = trail.get("wall_time_s")
    if wt is not None:
        print(f"  wall_time:  {_format_duration(wt)}")
    print(f"  labels:     {', '.join(trail.get('prd_labels', []))}")
    print(f"  slices:     {len(trail.get('slices', []))}")
    slices = trail.get("slices", [])
    for sl in slices:
        pr_num = sl.get("closing_pr_number")
        pr_note = f" -> PR #{pr_num}" if pr_num else " (no closing PR found)"
        print(f"    slice #{sl['number']}: {sl['title'][:60]}{pr_note}")
    print(f"  PRs:        {len(trail.get('prs', {}))}")
    prs = trail.get("prs", {})
    for pr_key, pr in sorted(prs.items(), key=lambda x: int(x[0])):
        verdicts = pr.get("verdicts", [])
        verdict_summary = []
        for v in verdicts:
            r = v.get("round", "?")
            vt = v.get("verdict", "?")
            ri = " (inferred)" if v.get("round_inferred") else ""
            verdict_summary.append(f"R{r}:{vt}{ri}")
        v_str = ", ".join(verdict_summary) if verdict_summary else "no verdicts"
        merged = pr.get("merged_at", "not merged")
        trivial = " [trivial]" if pr.get("is_trivial") else ""
        print(
            f"    PR #{pr['number']}: "
            f"verdicts=[{v_str}] merged={merged}{trivial}"
        )
    if trail.get("collector_status"):
        print(f"  collector_status: {trail['collector_status']}")

    if compare:
        _cli_compare(trail)


def _cli_compare(trail: dict) -> None:
    """Run comparison engine and print results."""
    # Import comparison module (same directory)
    _insert_dashboard_path()
    from comparison import compare, get_spec_for_compare  # noqa: PLC0415
    spec = get_spec_for_compare()
    report = compare(spec, trail)
    print("\n--- Comparison report ---")
    print(f"  run_pass: {report['run_pass']}")
    edges = report.get("edges", {})
    for edge_id, edge_report in sorted(edges.items()):
        state = edge_report.get("state", "?")
        detail = edge_report.get("detail", "")
        detail_str = f" ({detail})" if detail else ""
        print(f"  {edge_id}: {state}{detail_str}")
    violations = report.get("violations", [])
    if violations:
        print(f"  violations ({len(violations)}):")
        for v in violations:
            print(f"    - {v['type']}: {v['detail']}")
    else:
        print("  violations: none")


def _insert_dashboard_path() -> None:
    """Ensure dashboard/ is on sys.path for sibling imports."""
    dashboard_dir = str(Path(__file__).resolve().parent)
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)


if __name__ == "__main__":
    import argparse

    _insert_dashboard_path()

    parser = argparse.ArgumentParser(
        description="Collect GitHub artifact trail for a PRD"
    )
    parser.add_argument("--prd", type=int, required=True, help="PRD issue number")
    parser.add_argument(
        "--compare", action="store_true", help="Run comparison engine after collecting"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Force refresh (ignore cache)"
    )
    args = parser.parse_args()

    trail = get_trail(args.prd, force_refresh=args.refresh)
    _cli_print_trail(trail, compare=args.compare)

    # Exit 0 if collection succeeded; 1 if auth_dead
    status = trail.get("collector_status", "")
    if status == "auth_dead":
        print("\nERROR: gh authentication failed. Run: gh auth status", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)
