"""
dashboard/runtime_observer.py — runtime observation layer (ADR-0055).

Reads the v2 workflow-events.jsonl within a PRD's time window and evaluates
the SIX user→skill evaluators for slice 1:
  E-USER-SHIP, E-USER-BUILD, E-USER-GLOSSARY, E-USER-AUDITMETA,
  E-USER-AUDITSUBAGENTS, E-USER-PTB

Design constraints (ADR-0055):
  - D1: four second-class states: runtime-confirmed / runtime-unobserved /
         not-observable / not-exercised
  - D2: run_pass is NEVER touched; this module never imports server
  - D3: window = PRD created_at → closed_at|now; fixture sids excluded (rule #21)
  - D4: capture-liveness gate — no events in window → all edges not-observable
  - One pass over window events building an index; no per-edge log scans

Import direction: server <- comparison <- runtime_observer (never the reverse).
runtime_observer must NOT import server or comparison.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — mirror live.py's pattern
# ---------------------------------------------------------------------------
_OBSERVER_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LOG = _OBSERVER_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"

# Fixture-session guard — mirrors events.py FIXTURE_SID_RE (rule #21)
_FIXTURE_SID_RE = re.compile(
    r"^(demo|test|verify|fixture|manual|sess-)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# The 6 edge ids covered by this slice (user→skill class, ADR-0055 D1)
# ---------------------------------------------------------------------------
COVERED_EDGE_IDS = [
    "E-USER-SHIP",
    "E-USER-BUILD",
    "E-USER-GLOSSARY",
    "E-USER-AUDITMETA",
    "E-USER-AUDITSUBAGENTS",
    "E-USER-PTB",
]

# Map edge id → skill name as it appears in skill_invoke events and /slash commands.
# Predicate: any skill_invoke event with skill==X OR user_prompt whose prompt
# starts with the slash-command, within the run window.
_EDGE_SKILL: dict[str, tuple[str, str]] = {
    "E-USER-SHIP":           ("ship",             "/ship"),
    "E-USER-BUILD":          ("build",            "/build"),
    "E-USER-GLOSSARY":       ("glossary",         "/glossary"),
    "E-USER-AUDITMETA":      ("audit-meta",       "/audit-meta"),
    "E-USER-AUDITSUBAGENTS": ("audit-subagents",  "/audit-subagents"),
    "E-USER-PTB":            ("promote-to-backlog", "/promote-to-backlog"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_path() -> Path:
    """Return the workflow-events.jsonl path, honoring WORKFLOW_LOG_DIR sandbox."""
    override = os.environ.get("WORKFLOW_LOG_DIR", "")
    if override:
        return Path(override) / "workflow-events.jsonl"
    return _DEFAULT_LOG


def _parse_ts(ts_str: str) -> float | None:
    """Parse an ISO-8601 timestamp string to a UTC epoch float. Returns None on error."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _now_utc() -> float:
    """Return the current UTC epoch as a float."""
    return datetime.now(timezone.utc).timestamp()


def _is_valid_v2(obj: dict) -> bool:
    """Return True iff obj is a schema-v2 event with a real, non-fixture session_id."""
    if obj.get("v") != 2:
        return False
    sid = obj.get("session_id", "")
    if not sid:
        return False
    if _FIXTURE_SID_RE.match(sid):
        return False
    return True


# ---------------------------------------------------------------------------
# Core: build event index over the PRD window
# ---------------------------------------------------------------------------

def _build_window_index(
    win_start: float,
    win_end: float,
    log_path: Path,
) -> tuple[bool, dict]:
    """Scan the log once; return (capture_live, index).

    capture_live: True iff at least one v2 non-fixture event falls in the window.

    index shape:
        {
          "skill_invoke":   {skill_name: [event, ...]},
          "user_prompt":    [event, ...],   # only prompt events
        }

    One forward pass; O(window_events).
    Returns (False, {}) if log does not exist or is empty.
    """
    if not log_path.exists():
        return False, {}

    skill_invoke_idx: dict[str, list] = {}
    user_prompt_list: list = []
    any_event_in_window = False

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                if not _is_valid_v2(obj):
                    continue
                ts_epoch = _parse_ts(obj.get("ts", ""))
                if ts_epoch is None:
                    continue
                if ts_epoch < win_start or ts_epoch > win_end:
                    continue
                # Event is in the window
                any_event_in_window = True
                evt = obj.get("event", "")
                if evt == "skill_invoke":
                    skill = obj.get("skill", "")
                    if skill:
                        skill_invoke_idx.setdefault(skill, []).append(obj)
                elif evt == "user_prompt":
                    user_prompt_list.append(obj)
    except Exception:
        return False, {}

    return any_event_in_window, {
        "skill_invoke": skill_invoke_idx,
        "user_prompt": user_prompt_list,
    }


# ---------------------------------------------------------------------------
# Per-edge evaluators — all take (index, capture_live) and return (state, detail, evidence)
# ---------------------------------------------------------------------------

def _eval_user_skill_edge(
    edge_id: str,
    skill_name: str,
    slash_cmd: str,
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """Generic evaluator for user→skill edges.

    Predicate: any skill_invoke(skill==skill_name) OR user_prompt starts with slash_cmd.
    Returns (state, detail, evidence_event|None).
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    # Check skill_invoke index
    skill_events = index.get("skill_invoke", {}).get(skill_name, [])
    if skill_events:
        ev = skill_events[0]
        detail = (
            f"skill_invoke(skill={skill_name}) at {ev.get('ts','?')} "
            f"session={ev.get('session_id','?')[:8]}"
        )
        return "runtime-confirmed", detail, {
            "ts": ev.get("ts"),
            "event": ev.get("event"),
            "session_id": ev.get("session_id"),
            "skill": ev.get("skill"),
        }

    # Check user_prompt with matching slash command prefix or shell-path invocation.
    # Matches:
    #   (a) prompt starts with slash_cmd e.g. "/audit-meta --structure"
    #   (b) first token ends with /<skill_name> or \<skill_name> (Windows path prefix
    #       e.g. "C:/Program Files/Git/audit-meta --structure")
    slash_lower = slash_cmd.lower()
    skill_lower = skill_name.lower()
    for ev in index.get("user_prompt", []):
        prompt = ev.get("prompt", "").strip()
        prompt_lower = prompt.lower()
        first_token = prompt_lower.split()[0] if prompt_lower.split() else ""
        matched = (
            prompt_lower.startswith(slash_lower)
            or first_token.endswith("/" + skill_lower)
            or first_token.endswith("\\" + skill_lower)
        )
        if matched:
            detail = (
                f"user_prompt invokes '{skill_name}' at {ev.get('ts','?')} "
                f"session={ev.get('session_id','?')[:8]}"
            )
            return "runtime-confirmed", detail, {
                "ts": ev.get("ts"),
                "event": ev.get("event"),
                "session_id": ev.get("session_id"),
                "prompt_prefix": prompt[:80],
            }

    # Capture was live but the event didn't happen
    # All 6 are conditional (not required:always) — use not-exercised rather than
    # runtime-unobserved (conditional edge whose trigger never arose)
    return "not-exercised", (
        f"capture live in window but no skill_invoke(skill={skill_name}) "
        f"or user_prompt(/{slash_cmd.lstrip('/')}) found"
    ), None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def observe(
    trail: dict,
    log_path: Path | None = None,
) -> dict:
    """Evaluate the 6 user→skill runtime edges for the given PRD trail.

    Args:
        trail: output of collector.get_trail() — needs prd_created_at, prd_closed_at
        log_path: override for the workflow-events.jsonl path (for sandbox testing)

    Returns dict with keys:
        runtime_edges: {edge_id: {state, detail, evidence, required}} — 6 entries
        runtime_coverage: {confirmed, unobserved, not_observable, not_exercised}
        capture_liveness: bool — True iff any event found in the window
    """
    if log_path is None:
        log_path = _log_path()

    # Determine run window
    win_start_str = trail.get("prd_created_at", "")
    win_end_str = trail.get("prd_closed_at", "")
    win_start = _parse_ts(win_start_str) or 0.0
    win_end = _parse_ts(win_end_str) if win_end_str else _now_utc()

    # Guard: degenerate window (PRD has no created_at)
    if win_start == 0.0:
        # Cannot determine window — all not-observable
        runtime_edges = {}
        for eid in COVERED_EDGE_IDS:
            runtime_edges[eid] = {
                "state": "not-observable",
                "detail": "PRD has no created_at timestamp — window indeterminate",
                "evidence": "runtime",
                "required": "conditional",
            }
        return {
            "runtime_edges": runtime_edges,
            "runtime_coverage": {
                "confirmed": 0,
                "unobserved": 0,
                "not_observable": len(COVERED_EDGE_IDS),
                "not_exercised": 0,
            },
            "capture_liveness": False,
        }

    # One pass over the log window
    capture_live, index = _build_window_index(win_start, win_end, log_path)

    # Evaluate each edge
    runtime_edges: dict[str, dict] = {}
    counts = {"confirmed": 0, "unobserved": 0, "not_observable": 0, "not_exercised": 0}

    for eid in COVERED_EDGE_IDS:
        skill_name, slash_cmd = _EDGE_SKILL[eid]
        state, detail, ev_evidence = _eval_user_skill_edge(
            eid, skill_name, slash_cmd, index, capture_live
        )

        if state == "runtime-confirmed":
            counts["confirmed"] += 1
        elif state == "runtime-unobserved":
            counts["unobserved"] += 1
        elif state == "not-observable":
            counts["not_observable"] += 1
        else:  # not-exercised
            counts["not_exercised"] += 1

        entry: dict = {
            "state": state,
            "detail": detail,
            "evidence": "runtime",
            "required": "conditional",
        }
        if ev_evidence:
            entry["event_evidence"] = ev_evidence
        runtime_edges[eid] = entry

    return {
        "runtime_edges": runtime_edges,
        "runtime_coverage": counts,
        "capture_liveness": capture_live,
    }
