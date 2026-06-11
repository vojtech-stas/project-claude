"""
dashboard/runtime_observer.py — runtime observation layer (ADR-0055).

Reads the v2 workflow-events.jsonl within a PRD's time window and evaluates
ALL 26 runtime-tier evaluators across six classes:

Slice 1 (shipped):
  user→skill class (6): E-USER-SHIP, E-USER-BUILD, E-USER-GLOSSARY,
    E-USER-AUDITMETA, E-USER-AUDITSUBAGENTS, E-USER-PTB

Slice 2 (this file extends):
  skill-sequence class (4): E-BUILD-SHIP, E-SHIP-TOPRD, E-PRDISSUE-TOISSUES,
    E-TOISSUES-SLICER
  critic-dispatch class (6): E-TOPRD-PRDCRITIC, E-TOPRD-ADRCRITIC,
    E-GLOSSARY-CRITIC, E-PTB-BACKLOGCRITIC, E-MERGE-CODEBASECRITIC,
    E-SHIP-CODEBASECRITIC-BG
  sequence-ordering class (2): E-SLICER-SLICERCRITIC, E-SLICERCRITIC-BLOCK
  verdict-return class (4): E-QAPLAN-QATESTER, E-QATESTER-VERDICT,
    E-MERGE-QAPLAN, E-MERGE-QAREVIEW
  bash-evidence class (1): E-CAPTURED-PTB
  conditional-advisory class (3): E-AUDITMETA-REVIEWER,
    E-AUDITSUBAGENTS-REVIEWER, E-CODEBASECRITIC-REVIEWER

Plus: explicit `unmeasurable` state for E-USER-GRILLME + E-GRILLME-SHIP
     (both declared unmeasurable-by-design in SPEC; handled in observe()).

Design constraints (ADR-0055):
  - D1: four second-class states: runtime-confirmed / runtime-unobserved /
         not-observable / not-exercised (+ unmeasurable-by-design)
  - D2: run_pass is NEVER touched; this module never imports server
  - D3: window = PRD created_at → closed_at|now; fixture sids excluded (rule #21)
       sequence predicates: same-window ordering by ts; same-session preferred
       but cross-session dispatches are the norm (DO NOT require critic's
       agent_start to share a session with the generator's agent_complete).
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
    r"^(demo|test|verify|fixture|manual|sess-|sample-session-id$)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# All 26 runtime-tier edge ids covered by the observer
# ---------------------------------------------------------------------------
COVERED_EDGE_IDS = [
    # user→skill class (slice 1)
    "E-USER-SHIP",
    "E-USER-BUILD",
    "E-USER-GLOSSARY",
    "E-USER-AUDITMETA",
    "E-USER-AUDITSUBAGENTS",
    "E-USER-PTB",
    # skill-sequence class (slice 2)
    "E-BUILD-SHIP",
    "E-SHIP-TOPRD",
    "E-PRDISSUE-TOISSUES",
    "E-TOISSUES-SLICER",
    # critic-dispatch class (slice 2)
    "E-TOPRD-PRDCRITIC",
    "E-TOPRD-ADRCRITIC",
    "E-GLOSSARY-CRITIC",
    "E-PTB-BACKLOGCRITIC",
    "E-MERGE-CODEBASECRITIC",
    "E-SHIP-CODEBASECRITIC-BG",
    # sequence-ordering class (slice 2)
    "E-SLICER-SLICERCRITIC",
    "E-SLICERCRITIC-BLOCK",
    # verdict-return class (slice 2)
    "E-QAPLAN-QATESTER",
    "E-QATESTER-VERDICT",
    "E-MERGE-QAPLAN",
    "E-MERGE-QAREVIEW",
    # bash-evidence class (slice 2)
    "E-CAPTURED-PTB",
    # conditional-advisory class (slice 2)
    "E-AUDITMETA-REVIEWER",
    "E-AUDITSUBAGENTS-REVIEWER",
    "E-CODEBASECRITIC-REVIEWER",
]

# Unmeasurable edges — declared in SPEC as evidence=unmeasurable; never observable.
# Their state is "unmeasurable" (not "not-evaluated") to close the dark-edge class.
UNMEASURABLE_EDGE_IDS = [
    "E-USER-GRILLME",
    "E-GRILLME-SHIP",
]

# Map edge id → (skill_name, slash_command) for user→skill edges
_EDGE_SKILL: dict[str, tuple[str, str]] = {
    "E-USER-SHIP":           ("ship",             "/ship"),
    "E-USER-BUILD":          ("build",            "/build"),
    "E-USER-GLOSSARY":       ("glossary",         "/glossary"),
    "E-USER-AUDITMETA":      ("audit-meta",       "/audit-meta"),
    "E-USER-AUDITSUBAGENTS": ("audit-subagents",  "/audit-subagents"),
    "E-USER-PTB":            ("promote-to-backlog", "/promote-to-backlog"),
}

# Verdict regex — matches VERDICT:\s*BLOCK in agent_complete tail
_VERDICT_BLOCK_RE = re.compile(r"VERDICT:\s*BLOCK", re.IGNORECASE)
# PRODUCTION_VERIFY regex — matches PRODUCTION_VERIFY: in agent_complete tail
_PRODUCTION_VERIFY_RE = re.compile(r"PRODUCTION_VERIFY\s*:", re.IGNORECASE)
# bash --label captured pattern
_LABEL_CAPTURED_RE = re.compile(r"--label\s+captured", re.IGNORECASE)


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


def _ev_ref(ev: dict) -> dict:
    """Return a compact evidence reference for an event (ts, event, session_id, ...)."""
    return {
        "ts": ev.get("ts"),
        "event": ev.get("event"),
        "session_id": ev.get("session_id"),
    }


# ---------------------------------------------------------------------------
# Core: build event index over the PRD window (one pass, ADR-0055 D4)
# ---------------------------------------------------------------------------

def _build_window_index(
    win_start: float,
    win_end: float,
    log_path: Path,
) -> tuple[bool, dict]:
    """Scan the log once; return (capture_live, index).

    capture_live: True iff at least one v2 non-fixture event falls in the window.

    index shape (all lists are in ascending ts order):
        {
          "skill_invoke":   {skill_name: [event, ...]},
          "user_prompt":    [event, ...],
          "agent_start":    {subagent_type: [event, ...]},   # keyed by subagent_type
          "agent_complete": {subagent_type: [event, ...]},   # keyed by subagent_type
          "bash_complete":  [event, ...],
          "all_events":     [event, ...],  # all window events, time-ordered
        }

    One forward pass; O(window_events).
    Returns (False, {}) if log does not exist or is empty.
    """
    if not log_path.exists():
        return False, {}

    skill_invoke_idx: dict[str, list] = {}
    user_prompt_list: list = []
    agent_start_idx: dict[str, list] = {}
    agent_complete_idx: dict[str, list] = {}
    bash_complete_list: list = []
    all_events: list = []
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
                all_events.append(obj)

                if evt == "skill_invoke":
                    skill = obj.get("skill", "")
                    if skill:
                        skill_invoke_idx.setdefault(skill, []).append(obj)
                elif evt == "user_prompt":
                    user_prompt_list.append(obj)
                elif evt == "agent_start":
                    stype = obj.get("subagent_type", "")
                    if stype:
                        agent_start_idx.setdefault(stype, []).append(obj)
                    # Also index by "agent_start" key for unlabeled lookups
                    agent_start_idx.setdefault("__all__", []).append(obj)
                elif evt == "agent_complete":
                    stype = obj.get("subagent_type", "")
                    if stype:
                        agent_complete_idx.setdefault(stype, []).append(obj)
                    agent_complete_idx.setdefault("__all__", []).append(obj)
                elif evt == "bash_complete":
                    bash_complete_list.append(obj)
    except Exception:
        return False, {}

    return any_event_in_window, {
        "skill_invoke": skill_invoke_idx,
        "user_prompt": user_prompt_list,
        "agent_start": agent_start_idx,
        "agent_complete": agent_complete_idx,
        "bash_complete": bash_complete_list,
        "all_events": all_events,
    }


# ---------------------------------------------------------------------------
# Per-edge evaluators — grouped by class
# Each returns (state, detail, evidence_dict | None)
# ---------------------------------------------------------------------------

# ---- user→skill class (slice 1 logic, preserved) ---------------------------

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
    return "not-exercised", (
        f"capture live in window but no skill_invoke(skill={skill_name}) "
        f"or user_prompt(/{slash_cmd.lstrip('/')}) found"
    ), None


# ---- skill-sequence class --------------------------------------------------

def _eval_skill_sequence(
    from_skill: str,
    to_target: str,
    to_target_type: str,  # "skill" | "agent_start"
    index: dict,
    capture_live: bool,
    required: str = "always",
) -> tuple[str, str, dict | None]:
    """Evaluator for skill→skill or skill→agent_start sequences.

    Predicate: to_target event appears after from_skill's skill_invoke event,
    within the same window (same-session preferred; cross-session allowed per D3).
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    # Find from_skill invocations
    from_events = index.get("skill_invoke", {}).get(from_skill, [])
    if not from_events:
        if required == "always":
            return "runtime-unobserved", (
                f"capture live but no skill_invoke(skill={from_skill}) found"
            ), None
        return "not-exercised", (
            f"capture live but no skill_invoke(skill={from_skill}) — conditional edge not triggered"
        ), None

    # The earliest from_skill invocation
    from_ev = from_events[0]
    from_ts = _parse_ts(from_ev.get("ts", "")) or 0.0

    # Find to_target after from_ts
    if to_target_type == "skill":
        to_events = index.get("skill_invoke", {}).get(to_target, [])
    else:  # agent_start
        to_events = index.get("agent_start", {}).get(to_target, [])
        if not to_events:
            # Also check __all__ agent_start events and filter by input
            to_events = []

    # Find earliest to_target event AFTER from_ts
    matching = [e for e in to_events if (_parse_ts(e.get("ts", "")) or 0.0) > from_ts]
    if matching:
        ev = matching[0]
        detail = (
            f"{from_skill} → {to_target} sequence: "
            f"{to_target_type}({to_target}) at {ev.get('ts','?')} "
            f"after {from_ev.get('ts','?')}"
        )
        evidence = _ev_ref(ev)
        evidence["from_ts"] = from_ev.get("ts")
        evidence["from_skill"] = from_skill
        return "runtime-confirmed", detail, evidence

    if required == "always":
        return "runtime-unobserved", (
            f"capture live; skill_invoke({from_skill}) found at {from_ev.get('ts','?')} "
            f"but no subsequent {to_target_type}({to_target}) in window"
        ), None
    return "not-exercised", (
        f"capture live; skill_invoke({from_skill}) found but no "
        f"{to_target_type}({to_target}) after it — conditional edge"
    ), None


# ---- critic-dispatch class -------------------------------------------------

def _eval_agent_start_after_skill(
    from_skill: str,
    subagent_type: str,
    index: dict,
    capture_live: bool,
    required: str = "always",
    input_hint: str = "",
) -> tuple[str, str, dict | None]:
    """Sequence: skill_invoke(from_skill) → agent_start(subagent_type) after it.

    Cross-session dispatches are the norm (agent dispatches run in their own
    context) — only window+order is required (ADR-0055 D3).
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    from_events = index.get("skill_invoke", {}).get(from_skill, [])
    if not from_events:
        if required == "always":
            return "runtime-unobserved", (
                f"capture live but no skill_invoke(skill={from_skill}) found"
            ), None
        return "not-exercised", (
            f"capture live but no skill_invoke(skill={from_skill}) — "
            f"conditional edge not triggered"
        ), None

    from_ev = from_events[0]
    from_ts = _parse_ts(from_ev.get("ts", "")) or 0.0

    # Direct subagent_type match after from_ts
    for ev in index.get("agent_start", {}).get(subagent_type, []):
        if (_parse_ts(ev.get("ts", "")) or 0.0) > from_ts:
            detail = (
                f"skill({from_skill}) → agent_start(subagent_type={subagent_type}) "
                f"at {ev.get('ts','?')}"
            )
            evidence = _ev_ref(ev)
            evidence["from_skill_ts"] = from_ev.get("ts")
            evidence["subagent_type"] = subagent_type
            return "runtime-confirmed", detail, evidence

    # input_hint fallback: any agent_start after from_ts with hint in input
    if input_hint:
        hint_lower = input_hint.lower()
        for ev in index.get("agent_start", {}).get("__all__", []):
            ev_ts = _parse_ts(ev.get("ts", "")) or 0.0
            if ev_ts <= from_ts:
                continue
            inp = str(ev.get("input", "")).lower()
            if hint_lower in inp:
                detail = (
                    f"skill({from_skill}) → agent_start(input~={input_hint!r}) "
                    f"at {ev.get('ts','?')} (subagent_type={ev.get('subagent_type','?')})"
                )
                evidence = _ev_ref(ev)
                evidence["from_skill_ts"] = from_ev.get("ts")
                evidence["subagent_type"] = ev.get("subagent_type")
                evidence["matched_hint"] = input_hint
                return "runtime-confirmed", detail, evidence

    if required == "always":
        return "runtime-unobserved", (
            f"capture live; skill_invoke({from_skill}) at {from_ev.get('ts','?')} "
            f"but no agent_start(subagent_type={subagent_type}) after it in window"
        ), None
    return "not-exercised", (
        f"capture live; skill_invoke({from_skill}) found but no "
        f"agent_start(subagent_type={subagent_type}) after it — conditional"
    ), None


# ---- sequence-ordering class -----------------------------------------------

def _eval_slicer_slicercritic(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-SLICER-SLICERCRITIC: slicer-critic agent_start after slicer agent_complete.

    Cross-session is the norm — only window+ordering required (ADR-0055 D3).
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    slicer_completes = index.get("agent_complete", {}).get("slicer", [])
    if not slicer_completes:
        return "runtime-unobserved", (
            "capture live but no agent_complete(subagent_type=slicer) found"
        ), None

    slicer_ts = _parse_ts(slicer_completes[0].get("ts", "")) or 0.0

    # slicer-critic agent_start after slicer agent_complete
    for ev in index.get("agent_start", {}).get("slicer-critic", []):
        ev_ts = _parse_ts(ev.get("ts", "")) or 0.0
        if ev_ts > slicer_ts:
            detail = (
                f"agent_complete(slicer) at {slicer_completes[0].get('ts','?')} → "
                f"agent_start(slicer-critic) at {ev.get('ts','?')}"
            )
            evidence = _ev_ref(ev)
            evidence["slicer_complete_ts"] = slicer_completes[0].get("ts")
            return "runtime-confirmed", detail, evidence

    return "runtime-unobserved", (
        f"capture live; agent_complete(slicer) at {slicer_completes[0].get('ts','?')} "
        f"but no subsequent agent_start(slicer-critic) found"
    ), None


def _eval_slicercritic_block(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-SLICERCRITIC-BLOCK: agent_complete for slicer-critic whose tail matches VERDICT:\\s*BLOCK."""
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    for ev in index.get("agent_complete", {}).get("slicer-critic", []):
        tail = ev.get("tail", "") or ""
        if _VERDICT_BLOCK_RE.search(tail):
            detail = (
                f"agent_complete(slicer-critic) VERDICT: BLOCK "
                f"at {ev.get('ts','?')} session={ev.get('session_id','?')[:8]}"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": "slicer-critic",
                "verdict": "BLOCK",
            }

    return "not-exercised", (
        "capture live but no agent_complete(slicer-critic) with VERDICT: BLOCK — "
        "slicer-critic did not BLOCK in this window (conditional)"
    ), None


# ---- verdict-return class --------------------------------------------------

def _eval_qaplan_qatester(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-QAPLAN-QATESTER: skill_invoke(qa-plan) then agent_start naming qa-tester.

    Predicate: skill_invoke(skill=qa-plan) exists, then agent_start whose input
    names 'qa-tester' OR subagent_type=='qa-tester'.
    If only subagent_type mismatch (no input naming), that is a FINDING per slice
    body — do NOT paper over it; return runtime-unobserved with the finding.
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    qa_plan_events = index.get("skill_invoke", {}).get("qa-plan", [])
    if not qa_plan_events:
        return "runtime-unobserved", (
            "capture live but no skill_invoke(skill=qa-plan) found"
        ), None

    qa_plan_ts = _parse_ts(qa_plan_events[0].get("ts", "")) or 0.0

    # Check for agent_start(subagent_type=qa-tester) after qa-plan
    for ev in index.get("agent_start", {}).get("qa-tester", []):
        ev_ts = _parse_ts(ev.get("ts", "")) or 0.0
        if ev_ts > qa_plan_ts:
            detail = (
                f"skill(qa-plan) → agent_start(subagent_type=qa-tester) "
                f"at {ev.get('ts','?')}"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": "qa-tester",
                "qa_plan_ts": qa_plan_events[0].get("ts"),
            }

    # Check for agent_start whose input names qa-tester (general-purpose dispatch)
    for ev in index.get("agent_start", {}).get("__all__", []):
        ev_ts = _parse_ts(ev.get("ts", "")) or 0.0
        if ev_ts <= qa_plan_ts:
            continue
        inp = str(ev.get("input", "")).lower()
        if "qa-tester" in inp:
            detail = (
                f"skill(qa-plan) → agent_start(input~='qa-tester') "
                f"at {ev.get('ts','?')} (subagent_type={ev.get('subagent_type','?')})"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": ev.get("subagent_type"),
                "qa_plan_ts": qa_plan_events[0].get("ts"),
                "matched_input_hint": "qa-tester",
            }

    # qa-plan found but no qa-tester start — runtime-unobserved (declared always)
    return "runtime-unobserved", (
        f"capture live; skill_invoke(qa-plan) at {qa_plan_events[0].get('ts','?')} "
        f"but no agent_start naming qa-tester in window — "
        f"FINDING: qa-plan dispatches qa-tester under different subagent_type?"
    ), None


def _eval_qatester_verdict(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-QATESTER-VERDICT: agent_complete whose tail contains PRODUCTION_VERIFY:."""
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    # Check qa-tester completes first
    for ev in index.get("agent_complete", {}).get("qa-tester", []):
        tail = ev.get("tail", "") or ""
        if _PRODUCTION_VERIFY_RE.search(tail):
            detail = (
                f"agent_complete(qa-tester) PRODUCTION_VERIFY: "
                f"at {ev.get('ts','?')} session={ev.get('session_id','?')[:8]}"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": "qa-tester",
                "verdict": "PRODUCTION_VERIFY",
            }

    # Also check general-purpose completes with PRODUCTION_VERIFY in tail
    for ev in index.get("agent_complete", {}).get("__all__", []):
        tail = ev.get("tail", "") or ""
        if _PRODUCTION_VERIFY_RE.search(tail):
            detail = (
                f"agent_complete(subagent_type={ev.get('subagent_type','?')}) "
                f"PRODUCTION_VERIFY: at {ev.get('ts','?')}"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": ev.get("subagent_type"),
                "verdict": "PRODUCTION_VERIFY",
            }

    return "runtime-unobserved", (
        "capture live but no agent_complete with PRODUCTION_VERIFY: in tail found"
    ), None


def _eval_merge_qaplan(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-MERGE-QAPLAN: skill_invoke(qa-plan) in the window (after a merge event).

    Predicate: skill_invoke(skill=qa-plan) exists in the window.
    The merge event itself is a github artifact; we only observe the skill dispatch.
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    events = index.get("skill_invoke", {}).get("qa-plan", [])
    if events:
        ev = events[0]
        detail = (
            f"skill_invoke(skill=qa-plan) at {ev.get('ts','?')} "
            f"session={ev.get('session_id','?')[:8]}"
        )
        return "runtime-confirmed", detail, {
            **_ev_ref(ev),
            "skill": "qa-plan",
        }
    return "runtime-unobserved", (
        "capture live but no skill_invoke(skill=qa-plan) found in window"
    ), None


def _eval_merge_qareview(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-MERGE-QAREVIEW: skill_invoke(qa-review) in the window (conditional)."""
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    events = index.get("skill_invoke", {}).get("qa-review", [])
    if events:
        ev = events[0]
        detail = (
            f"skill_invoke(skill=qa-review) at {ev.get('ts','?')} "
            f"session={ev.get('session_id','?')[:8]}"
        )
        return "runtime-confirmed", detail, {
            **_ev_ref(ev),
            "skill": "qa-review",
        }
    return "not-exercised", (
        "capture live but no skill_invoke(skill=qa-review) — "
        "qa-review clears needs-human-check residual (conditional)"
    ), None


# ---- bash-evidence class ---------------------------------------------------

def _eval_captured_ptb(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-CAPTURED-PTB: bash_complete with --label captured, then skill_invoke(promote-to-backlog).

    Predicate: bash_complete whose command contains --label captured, AND
    skill_invoke(skill=promote-to-backlog) after it.
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    # Find bash_complete with --label captured
    captured_bash_events = [
        ev for ev in index.get("bash_complete", [])
        if _LABEL_CAPTURED_RE.search(ev.get("command", "") or "")
    ]

    if not captured_bash_events:
        return "not-exercised", (
            "capture live but no bash_complete with --label captured found — "
            "conditional: no captured issue was created in this window"
        ), None

    bash_ts = _parse_ts(captured_bash_events[0].get("ts", "")) or 0.0
    ptb_events = index.get("skill_invoke", {}).get("promote-to-backlog", [])
    matching_ptb = [
        ev for ev in ptb_events
        if (_parse_ts(ev.get("ts", "")) or 0.0) > bash_ts
    ]

    if matching_ptb:
        ev = matching_ptb[0]
        detail = (
            f"bash(--label captured) at {captured_bash_events[0].get('ts','?')} → "
            f"skill_invoke(promote-to-backlog) at {ev.get('ts','?')}"
        )
        return "runtime-confirmed", detail, {
            **_ev_ref(ev),
            "bash_ts": captured_bash_events[0].get("ts"),
            "bash_command_prefix": (captured_bash_events[0].get("command") or "")[:80],
        }

    return "not-exercised", (
        f"bash(--label captured) at {captured_bash_events[0].get('ts','?')} found "
        f"but no subsequent skill_invoke(promote-to-backlog) — "
        f"user may have used autopilot without running ptb"
    ), None


# ---- conditional-advisory class --------------------------------------------

def _eval_advisory_to_reviewer(
    from_skill: str,
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """Generic evaluator for advisory→reviewer sequence edges.

    Predicate: skill_invoke(from_skill) found, then agent_start(reviewer) after it.
    Both are conditional (advisory skips happen often); use not-exercised when absent.
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    from_events = index.get("skill_invoke", {}).get(from_skill, [])
    if not from_events:
        return "not-exercised", (
            f"capture live but no skill_invoke(skill={from_skill}) — "
            f"advisory feed to reviewer (conditional)"
        ), None

    from_ts = _parse_ts(from_events[0].get("ts", "")) or 0.0

    for ev in index.get("agent_start", {}).get("reviewer", []):
        ev_ts = _parse_ts(ev.get("ts", "")) or 0.0
        if ev_ts > from_ts:
            detail = (
                f"skill({from_skill}) → agent_start(reviewer) at {ev.get('ts','?')} "
                f"session={ev.get('session_id','?')[:8]}"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "from_skill": from_skill,
                "from_ts": from_events[0].get("ts"),
            }

    return "not-exercised", (
        f"capture live; skill_invoke({from_skill}) at {from_events[0].get('ts','?')} "
        f"found but no agent_start(reviewer) after it — conditional advisory"
    ), None


def _eval_codebasecritic_reviewer(
    index: dict,
    capture_live: bool,
) -> tuple[str, str, dict | None]:
    """E-CODEBASECRITIC-REVIEWER: agent_complete(codebase-critic) then agent_start(reviewer).

    The codebase-critic per-PRD verdict feeds into the reviewer pass.
    """
    if not capture_live:
        return "not-observable", "no events in window — capture not live during this run", None

    cc_completes = index.get("agent_complete", {}).get("codebase-critic", [])
    if not cc_completes:
        return "not-exercised", (
            "capture live but no agent_complete(codebase-critic) found — "
            "codebase-critic per-PRD feed to reviewer (conditional)"
        ), None

    cc_ts = _parse_ts(cc_completes[0].get("ts", "")) or 0.0

    for ev in index.get("agent_start", {}).get("reviewer", []):
        ev_ts = _parse_ts(ev.get("ts", "")) or 0.0
        if ev_ts > cc_ts:
            detail = (
                f"agent_complete(codebase-critic) at {cc_completes[0].get('ts','?')} → "
                f"agent_start(reviewer) at {ev.get('ts','?')}"
            )
            return "runtime-confirmed", detail, {
                **_ev_ref(ev),
                "cc_complete_ts": cc_completes[0].get("ts"),
            }

    return "not-exercised", (
        f"capture live; agent_complete(codebase-critic) at {cc_completes[0].get('ts','?')} "
        f"found but no subsequent agent_start(reviewer) — conditional"
    ), None


# ---------------------------------------------------------------------------
# Dispatch table — maps edge_id → evaluator closure
# Built lazily in observe(); declared here for documentation.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def observe(
    trail: dict,
    log_path: Path | None = None,
) -> dict:
    """Evaluate all 26 runtime-tier edges + 2 unmeasurable edges for the given PRD trail.

    Args:
        trail: output of collector.get_trail() — needs prd_created_at, prd_closed_at
        log_path: override for the workflow-events.jsonl path (for sandbox testing)

    Returns dict with keys:
        runtime_edges: {edge_id: {state, detail, evidence, required}} — 28 entries
          (26 runtime + 2 unmeasurable-by-design)
        runtime_coverage: {confirmed, unobserved, not_observable, not_exercised,
                           unmeasurable}
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
        runtime_edges: dict = {}
        for eid in COVERED_EDGE_IDS:
            runtime_edges[eid] = {
                "state": "not-observable",
                "detail": "PRD has no created_at timestamp — window indeterminate",
                "evidence": "runtime",
                "required": "conditional",
            }
        for eid in UNMEASURABLE_EDGE_IDS:
            runtime_edges[eid] = {
                "state": "unmeasurable",
                "detail": "in-conversation handoff — cannot be captured by hook events by design",
                "evidence": "unmeasurable",
                "required": "conditional",
            }
        not_obs = len(COVERED_EDGE_IDS)
        return {
            "runtime_edges": runtime_edges,
            "runtime_coverage": {
                "confirmed": 0, "unobserved": 0,
                "not_observable": not_obs, "not_exercised": 0,
                "unmeasurable": len(UNMEASURABLE_EDGE_IDS),
            },
            "capture_liveness": False,
        }

    # One pass over the log window
    capture_live, index = _build_window_index(win_start, win_end, log_path)

    # ---------------------------------------------------------------------------
    # Evaluate all 26 runtime-tier edges
    # ---------------------------------------------------------------------------
    results: dict[str, tuple[str, str, dict | None]] = {}

    # -- user→skill class (slice 1) --
    for eid in ["E-USER-SHIP", "E-USER-BUILD", "E-USER-GLOSSARY",
                "E-USER-AUDITMETA", "E-USER-AUDITSUBAGENTS", "E-USER-PTB"]:
        skill_name, slash_cmd = _EDGE_SKILL[eid]
        results[eid] = _eval_user_skill_edge(eid, skill_name, slash_cmd, index, capture_live)

    # -- skill-sequence class --
    # E-BUILD-SHIP: skill_invoke(build) → skill_invoke(ship) (required:always)
    results["E-BUILD-SHIP"] = _eval_skill_sequence(
        "build", "ship", "skill", index, capture_live, required="always"
    )

    # E-SHIP-TOPRD: skill_invoke(ship) → skill_invoke(to-prd) (required:always)
    results["E-SHIP-TOPRD"] = _eval_skill_sequence(
        "ship", "to-prd", "skill", index, capture_live, required="always"
    )

    # E-PRDISSUE-TOISSUES: skill_invoke(to-prd) → skill_invoke(to-issues) (required:always)
    results["E-PRDISSUE-TOISSUES"] = _eval_skill_sequence(
        "to-prd", "to-issues", "skill", index, capture_live, required="always"
    )

    # E-TOISSUES-SLICER: skill_invoke(to-issues) → agent_start(slicer) (required:always)
    results["E-TOISSUES-SLICER"] = _eval_agent_start_after_skill(
        "to-issues", "slicer", index, capture_live, required="always"
    )

    # -- critic-dispatch class --
    # E-TOPRD-PRDCRITIC: skill_invoke(to-prd) → agent_start(prd-critic)
    results["E-TOPRD-PRDCRITIC"] = _eval_agent_start_after_skill(
        "to-prd", "prd-critic", index, capture_live, required="always"
    )

    # E-TOPRD-ADRCRITIC: skill_invoke(to-prd) → agent_start(adr-critic) (conditional)
    results["E-TOPRD-ADRCRITIC"] = _eval_agent_start_after_skill(
        "to-prd", "adr-critic", index, capture_live, required="conditional"
    )

    # E-GLOSSARY-CRITIC: skill_invoke(glossary) → agent_start(glossary-critic)
    results["E-GLOSSARY-CRITIC"] = _eval_agent_start_after_skill(
        "glossary", "glossary-critic", index, capture_live, required="always"
    )

    # E-PTB-BACKLOGCRITIC: skill_invoke(promote-to-backlog) → agent_start(backlog-critic)
    results["E-PTB-BACKLOGCRITIC"] = _eval_agent_start_after_skill(
        "promote-to-backlog", "backlog-critic", index, capture_live, required="always"
    )

    # E-MERGE-CODEBASECRITIC: agent_start(codebase-critic) in window
    # (per-PRD gate: /ship dispatches at last slice; input does NOT contain WHOLE_REPO)
    if not capture_live:
        results["E-MERGE-CODEBASECRITIC"] = (
            "not-observable", "no events in window — capture not live", None
        )
    else:
        cc_events = [
            ev for ev in index.get("agent_start", {}).get("codebase-critic", [])
            if "WHOLE_REPO" not in str(ev.get("input", ""))
        ]
        if cc_events:
            ev = cc_events[0]
            detail = (
                f"agent_start(codebase-critic, per-PRD mode) at {ev.get('ts','?')} "
                f"session={ev.get('session_id','?')[:8]}"
            )
            results["E-MERGE-CODEBASECRITIC"] = ("runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": "codebase-critic",
                "mode": "per-prd",
            })
        else:
            results["E-MERGE-CODEBASECRITIC"] = ("not-exercised", (
                "capture live but no agent_start(codebase-critic) without WHOLE_REPO "
                "— per-PRD codebase-critic gate (conditional)"
            ), None)

    # E-SHIP-CODEBASECRITIC-BG: agent_start(codebase-critic) with WHOLE_REPO in input
    if not capture_live:
        results["E-SHIP-CODEBASECRITIC-BG"] = (
            "not-observable", "no events in window — capture not live", None
        )
    else:
        bg_events = [
            ev for ev in index.get("agent_start", {}).get("codebase-critic", [])
            if "WHOLE_REPO" in str(ev.get("input", ""))
        ]
        if bg_events:
            ev = bg_events[0]
            detail = (
                f"agent_start(codebase-critic, WHOLE_REPO bg) at {ev.get('ts','?')} "
                f"session={ev.get('session_id','?')[:8]}"
            )
            results["E-SHIP-CODEBASECRITIC-BG"] = ("runtime-confirmed", detail, {
                **_ev_ref(ev),
                "subagent_type": "codebase-critic",
                "mode": "whole-repo-bg",
            })
        else:
            results["E-SHIP-CODEBASECRITIC-BG"] = ("not-exercised", (
                "capture live but no agent_start(codebase-critic) with WHOLE_REPO "
                "— whole-repo background mode (conditional)"
            ), None)

    # -- sequence-ordering class --
    results["E-SLICER-SLICERCRITIC"] = _eval_slicer_slicercritic(index, capture_live)
    results["E-SLICERCRITIC-BLOCK"] = _eval_slicercritic_block(index, capture_live)

    # -- verdict-return class --
    results["E-QAPLAN-QATESTER"] = _eval_qaplan_qatester(index, capture_live)
    results["E-QATESTER-VERDICT"] = _eval_qatester_verdict(index, capture_live)
    results["E-MERGE-QAPLAN"] = _eval_merge_qaplan(index, capture_live)
    results["E-MERGE-QAREVIEW"] = _eval_merge_qareview(index, capture_live)

    # -- bash-evidence class --
    results["E-CAPTURED-PTB"] = _eval_captured_ptb(index, capture_live)

    # -- conditional-advisory class --
    results["E-AUDITMETA-REVIEWER"] = _eval_advisory_to_reviewer(
        "audit-meta", index, capture_live
    )
    results["E-AUDITSUBAGENTS-REVIEWER"] = _eval_advisory_to_reviewer(
        "audit-subagents", index, capture_live
    )
    results["E-CODEBASECRITIC-REVIEWER"] = _eval_codebasecritic_reviewer(index, capture_live)

    # ---------------------------------------------------------------------------
    # Build runtime_edges dict from results
    # ---------------------------------------------------------------------------
    # Required mapping from SPEC (used for display; evaluators may override)
    _REQUIRED: dict[str, str] = {
        "E-USER-SHIP": "conditional", "E-USER-BUILD": "conditional",
        "E-USER-GLOSSARY": "conditional", "E-USER-AUDITMETA": "conditional",
        "E-USER-AUDITSUBAGENTS": "conditional", "E-USER-PTB": "conditional",
        "E-BUILD-SHIP": "always", "E-SHIP-TOPRD": "always",
        "E-PRDISSUE-TOISSUES": "always", "E-TOISSUES-SLICER": "always",
        "E-TOPRD-PRDCRITIC": "always", "E-TOPRD-ADRCRITIC": "conditional",
        "E-GLOSSARY-CRITIC": "always", "E-PTB-BACKLOGCRITIC": "always",
        "E-MERGE-CODEBASECRITIC": "conditional", "E-SHIP-CODEBASECRITIC-BG": "conditional",
        "E-SLICER-SLICERCRITIC": "always", "E-SLICERCRITIC-BLOCK": "conditional",
        "E-QAPLAN-QATESTER": "always", "E-QATESTER-VERDICT": "always",
        "E-MERGE-QAPLAN": "always", "E-MERGE-QAREVIEW": "conditional",
        "E-CAPTURED-PTB": "conditional",
        "E-AUDITMETA-REVIEWER": "conditional", "E-AUDITSUBAGENTS-REVIEWER": "conditional",
        "E-CODEBASECRITIC-REVIEWER": "conditional",
    }

    runtime_edges: dict = {}
    counts = {
        "confirmed": 0, "unobserved": 0,
        "not_observable": 0, "not_exercised": 0,
        "unmeasurable": 0,
    }

    for eid in COVERED_EDGE_IDS:
        state, detail, ev_evidence = results[eid]
        entry: dict = {
            "state": state,
            "detail": detail,
            "evidence": "runtime",
            "required": _REQUIRED.get(eid, "conditional"),
        }
        if ev_evidence:
            entry["event_evidence"] = ev_evidence

        if state == "runtime-confirmed":
            counts["confirmed"] += 1
        elif state == "runtime-unobserved":
            counts["unobserved"] += 1
        elif state == "not-observable":
            counts["not_observable"] += 1
        else:  # not-exercised
            counts["not_exercised"] += 1

        runtime_edges[eid] = entry

    # Unmeasurable edges — explicit state to close the dark-edge class
    for eid in UNMEASURABLE_EDGE_IDS:
        runtime_edges[eid] = {
            "state": "unmeasurable",
            "detail": "in-conversation handoff — cannot be captured by hook events by design",
            "evidence": "unmeasurable",
            "required": "conditional",
        }
        counts["unmeasurable"] += 1

    return {
        "runtime_edges": runtime_edges,
        "runtime_coverage": counts,
        "capture_liveness": capture_live,
    }
