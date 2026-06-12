#!/usr/bin/env python3
"""tools/run_evals.py — eval runner for critic golden-set fixtures (ADR-0067 D5).

Invokes `claude -p --system-prompt-file <critic-prompt> <artifact>` for each
fixture case in tests/evals/<critic>/, parses the CRITIC trailer VERDICT, and
writes tests/evals/results.json.

Usage:
  python tools/run_evals.py [--critic CRITIC] [--subset N] [--holdout] [--verbose]

  --critic CRITIC   run only this critic (reviewer|prd-critic|slicer-critic);
                    default: all three
  --subset N        run at most N non-holdout cases per critic (for smoke-test)
  --holdout         include holdout cases in the run
  --verbose         print per-case output

This tool is NOT a CI stage — it is invoked on demand only (ADR-0067 D5).
Fixture data NEVER enters .claude/logs/* (rule #21).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_EVALS_DIR = _REPO_ROOT / "tests" / "evals"
_RESULTS_FILE = _EVALS_DIR / "results.json"
_AGENTS_DIR = _REPO_ROOT / ".claude" / "agents"

_KNOWN_EVAL_CRITICS = ["reviewer", "prd-critic", "slicer-critic"]

_CRITIC_PROMPT_MAP = {
    "reviewer":       _AGENTS_DIR / "reviewer.md",
    "prd-critic":     _AGENTS_DIR / "prd-critic.md",
    "slicer-critic":  _AGENTS_DIR / "slicer-critic.md",
}

# ---------------------------------------------------------------------------
# Verdict parser
# ---------------------------------------------------------------------------

_FENCED_BLOCK_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_VERDICT_RE = re.compile(r"^\s*VERDICT\s*:\s*(\S+)", re.MULTILINE)


def parse_verdict(output: str) -> str:
    """Return APPROVE, BLOCK, or UNPARSEABLE. Never guesses.

    Scans every fenced code block in the output for a VERDICT: line.
    Returns the first valid verdict found, or UNPARSEABLE if none.
    """
    for m in _FENCED_BLOCK_RE.finditer(output):
        block_text = m.group(1)
        vm = _VERDICT_RE.search(block_text)
        if vm:
            raw = vm.group(1).strip().upper().rstrip(".,;:")
            if raw in ("APPROVE", "BLOCK"):
                return raw
            return "UNPARSEABLE"
    return "UNPARSEABLE"


# ---------------------------------------------------------------------------
# Case runner
# ---------------------------------------------------------------------------

def run_case(
    prompt_path: Path,
    artifact_path: Path,
    timeout: int = 180,
    verbose: bool = False,
) -> dict:
    """Run one eval case.  Returns a dict with keys: verdict, duration_s, error."""
    artifact_text = artifact_path.read_text(encoding="utf-8", errors="replace")

    # Build user message — no triple-backtick sequences so parser stays clean
    user_msg = (
        "BLIND-REVIEW EVAL FIXTURE\n\n"
        "This is a self-contained eval artifact for golden-set testing (ADR-0067 D5).\n"
        "All PR body, diff summary, commit history, and analysis notes are provided "
        "inline below. You do NOT need to run gh or git commands — all materials are "
        "present. Apply your full rubric to the materials provided and emit your "
        "standard CRITIC trailer fenced code block at the end of your response "
        "(VERDICT / REASON / ROUND / CRITIC fields required).\n\n"
        "---\n\n"
        + artifact_text
    )

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            ["claude", "-p", "--system-prompt-file", str(prompt_path), user_msg],
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        duration_s = round(time.monotonic() - t0, 1)
        output = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
        if verbose:
            print(f"    stdout ({len(output)} chars): {output[:300]!r}")
            if stderr:
                print(f"    stderr: {stderr[:200]!r}")
        verdict = parse_verdict(output)
        return {"verdict": verdict, "duration_s": duration_s, "error": None}
    except subprocess.TimeoutExpired:
        duration_s = round(time.monotonic() - t0, 1)
        return {"verdict": "UNPARSEABLE", "duration_s": duration_s, "error": "timeout"}
    except Exception as exc:
        duration_s = round(time.monotonic() - t0, 1)
        return {"verdict": "UNPARSEABLE", "duration_s": duration_s, "error": str(exc)}


# ---------------------------------------------------------------------------
# Manifest loader
# ---------------------------------------------------------------------------

def load_manifest(critic: str) -> list[dict]:
    """Load manifest.json for a critic.  Returns list of case dicts."""
    manifest_path = _EVALS_DIR / critic / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"manifest must be a JSON array: {manifest_path}")
    return data


# ---------------------------------------------------------------------------
# Per-critic runner
# ---------------------------------------------------------------------------

def run_critic(
    critic: str,
    subset: int | None = None,
    include_holdout: bool = False,
    verbose: bool = False,
) -> dict:
    """Run evals for one critic.  Returns a critic-level result dict."""
    prompt_path = _CRITIC_PROMPT_MAP[critic]
    if not prompt_path.exists():
        return {
            "critic": critic,
            "error": f"prompt not found: {prompt_path}",
            "cases": [],
            "pass_rate": None,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    cases = load_manifest(critic)
    if not include_holdout:
        cases = [c for c in cases if not c.get("holdout", False)]
    if subset is not None:
        cases = cases[:subset]

    print(f"[eval] {critic}: running {len(cases)} cases", flush=True)

    case_results = []
    passed = 0
    failed = 0

    for case in cases:
        case_id = case.get("id", "unknown")
        expected = case.get("expected_verdict", "BLOCK").upper()
        artifact_rel = case.get("artifact", "")
        artifact_path = _EVALS_DIR / critic / artifact_rel

        print(f"  case {case_id} (expected={expected}) ... ", end="", flush=True)

        if not artifact_path.exists():
            verdict_result = {
                "id": case_id,
                "expected": expected,
                "got": "UNPARSEABLE",
                "pass": False,
                "duration_s": 0,
                "error": f"artifact not found: {artifact_path}",
            }
            print(f"ERROR: {verdict_result['error']}")
            case_results.append(verdict_result)
            failed += 1
            continue

        run_result = run_case(prompt_path, artifact_path, verbose=verbose)
        got = run_result["verdict"]
        passed_case = got == expected
        if passed_case:
            passed += 1
        else:
            failed += 1

        verdict_result = {
            "id": case_id,
            "expected": expected,
            "got": got,
            "pass": passed_case,
            "duration_s": run_result["duration_s"],
            "error": run_result["error"],
        }
        status = "PASS" if passed_case else f"FAIL (got {got})"
        if run_result["error"]:
            status = f"ERROR: {run_result['error']}"
        print(status, flush=True)
        case_results.append(verdict_result)

    total = len(case_results)
    pass_rate = round(passed / total, 4) if total > 0 else None

    return {
        "critic": critic,
        "error": None,
        "cases": case_results,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Results persistence
# ---------------------------------------------------------------------------

def load_results() -> dict:
    """Load existing results.json or return empty dict."""
    if _RESULTS_FILE.exists():
        try:
            return json.loads(_RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_results(results: dict) -> None:
    """Persist results dict to results.json."""
    _RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_FILE.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[eval] results written to {_RESULTS_FILE}", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run critic eval golden-set fixtures (ADR-0067 D5)."
    )
    parser.add_argument(
        "--critic",
        choices=_KNOWN_EVAL_CRITICS,
        default=None,
        help="critic to evaluate (default: all)",
    )
    parser.add_argument(
        "--subset",
        type=int,
        default=None,
        metavar="N",
        help="run at most N non-holdout cases per critic",
    )
    parser.add_argument(
        "--holdout",
        action="store_true",
        help="include holdout cases",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print raw model output excerpts",
    )
    args = parser.parse_args()

    critics_to_run = [args.critic] if args.critic else _KNOWN_EVAL_CRITICS

    existing_results = load_results()

    any_fail = False
    for critic in critics_to_run:
        critic_result = run_critic(
            critic,
            subset=args.subset,
            include_holdout=args.holdout,
            verbose=args.verbose,
        )
        existing_results[critic] = critic_result
        if critic_result.get("pass_rate") is not None and critic_result["pass_rate"] < 1.0:
            any_fail = True

    save_results(existing_results)

    # Print summary
    print("\n[eval] summary:")
    for critic in critics_to_run:
        r = existing_results.get(critic, {})
        if r.get("error"):
            print(f"  {critic}: ERROR — {r['error']}")
        elif r.get("pass_rate") is None:
            print(f"  {critic}: no cases run")
        else:
            print(
                f"  {critic}: {r['passed']}/{r['total']} passed "
                f"(pass_rate={r['pass_rate']:.2%})"
            )

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
