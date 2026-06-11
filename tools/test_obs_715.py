"""
Synthetic fixture tests for the runtime_observer slice-2 evaluators.
Run via: python3 tools/test_obs_715.py
Uses WORKFLOW_LOG_DIR sandbox -- never touches production logs (rule #21).
"""
import os, sys, json, tempfile, pathlib, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "dashboard"))

WIN_START = "2026-01-01T00:00:00Z"
WIN_END   = "2026-01-02T00:00:00Z"
BASE_DT   = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

def ts(offset_s: int) -> str:
    t = BASE_DT + datetime.timedelta(seconds=offset_s)
    return t.isoformat().replace("+00:00", "Z")

def mk_trail(start=WIN_START, end=WIN_END):
    return {"prd_created_at": start, "prd_closed_at": end, "prd_number": 999}

def mk_ev(event: str, **kw):
    return {"v": 2, "session_id": "real-session-001",
            "ts": kw.pop("ts", ts(60)), "event": event, **kw}

def make_sandbox(events: list) -> pathlib.Path:
    d = tempfile.mkdtemp(prefix="obs-test-")
    lp = pathlib.Path(d) / "workflow-events.jsonl"
    lp.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return lp

# Import fresh each time (module may already be loaded)
import importlib
import runtime_observer as _ro
importlib.reload(_ro)
observe = _ro.observe

PASS = []
FAIL = []

def check(label: str, got: str, expect: str):
    ok = got == expect
    mark = "OK" if ok else "FAIL"
    print(f"  [{mark}] {label}: {got!r} (expect {expect!r})")
    if ok:
        PASS.append(label)
    else:
        FAIL.append(f"{label}: got {got!r}")


# ============================================================
# CLASS 1: skill-sequence
# ============================================================
print("\n=== CLASS 1: skill-sequence ===")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="build", ts=ts(100)),
    mk_ev("skill_invoke", skill="ship",  ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-BUILD-SHIP confirmed", r["runtime_edges"]["E-BUILD-SHIP"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="ship",   ts=ts(100)),
    mk_ev("skill_invoke", skill="to-prd", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-SHIP-TOPRD confirmed", r["runtime_edges"]["E-SHIP-TOPRD"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="to-prd",    ts=ts(100)),
    mk_ev("skill_invoke", skill="to-issues", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-PRDISSUE-TOISSUES confirmed", r["runtime_edges"]["E-PRDISSUE-TOISSUES"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="to-issues", ts=ts(100)),
    mk_ev("agent_start", subagent_type="slicer", input="decompose PRD", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-TOISSUES-SLICER confirmed", r["runtime_edges"]["E-TOISSUES-SLICER"]["state"], "runtime-confirmed")

# Ordering: skill BEFORE agent_start must be enforced
lp = make_sandbox([
    mk_ev("agent_start", subagent_type="slicer", input="decompose PRD", ts=ts(100)),
    mk_ev("skill_invoke", skill="to-issues", ts=ts(200)),  # skill comes AFTER
])
r = observe(mk_trail(), log_path=lp)
check("E-TOISSUES-SLICER ordering (no match before)", r["runtime_edges"]["E-TOISSUES-SLICER"]["state"], "runtime-unobserved")


# ============================================================
# CLASS 2: critic-dispatch
# ============================================================
print("\n=== CLASS 2: critic-dispatch ===")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="to-prd", ts=ts(100)),
    mk_ev("agent_start", subagent_type="prd-critic", input="review", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-TOPRD-PRDCRITIC confirmed", r["runtime_edges"]["E-TOPRD-PRDCRITIC"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="to-prd", ts=ts(100)),
    mk_ev("agent_start", subagent_type="adr-critic", input="review adr", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-TOPRD-ADRCRITIC confirmed", r["runtime_edges"]["E-TOPRD-ADRCRITIC"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="glossary", ts=ts(100)),
    mk_ev("agent_start", subagent_type="glossary-critic", input="review", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-GLOSSARY-CRITIC confirmed", r["runtime_edges"]["E-GLOSSARY-CRITIC"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="promote-to-backlog", ts=ts(100)),
    mk_ev("agent_start", subagent_type="backlog-critic", input="review", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-PTB-BACKLOGCRITIC confirmed", r["runtime_edges"]["E-PTB-BACKLOGCRITIC"]["state"], "runtime-confirmed")

# E-MERGE-CODEBASECRITIC: per-PRD mode (no WHOLE_REPO in input)
lp = make_sandbox([
    mk_ev("agent_start", subagent_type="codebase-critic", input="review per-prd cumulative", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-MERGE-CODEBASECRITIC confirmed", r["runtime_edges"]["E-MERGE-CODEBASECRITIC"]["state"], "runtime-confirmed")

# E-SHIP-CODEBASECRITIC-BG: whole-repo bg mode (WHOLE_REPO in input)
lp = make_sandbox([
    mk_ev("agent_start", subagent_type="codebase-critic", input="WHOLE_REPO: true scan", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-SHIP-CODEBASECRITIC-BG confirmed", r["runtime_edges"]["E-SHIP-CODEBASECRITIC-BG"]["state"], "runtime-confirmed")

# Verify: per-PRD sees WHOLE_REPO event as not-exercised (not matching per-prd)
check("E-MERGE-CODEBASECRITIC not-exercised when only BG present",
      r["runtime_edges"]["E-MERGE-CODEBASECRITIC"]["state"], "not-exercised")

# Verify: BG sees per-PRD event as not-exercised
lp = make_sandbox([
    mk_ev("agent_start", subagent_type="codebase-critic", input="review per-prd", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-SHIP-CODEBASECRITIC-BG not-exercised when only per-PRD present",
      r["runtime_edges"]["E-SHIP-CODEBASECRITIC-BG"]["state"], "not-exercised")


# ============================================================
# CLASS 3: sequence-ordering incl. BLOCK tail
# ============================================================
print("\n=== CLASS 3: sequence-ordering ===")

lp = make_sandbox([
    mk_ev("agent_complete", subagent_type="slicer", tail="RESULT: SUCCESS", ts=ts(100)),
    mk_ev("agent_start", subagent_type="slicer-critic", input="review", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-SLICER-SLICERCRITIC confirmed", r["runtime_edges"]["E-SLICER-SLICERCRITIC"]["state"], "runtime-confirmed")

# Cross-session: different session_id but slicer-critic starts after slicer complete
# Using valid non-fixture sids (the sess- prefix is reserved for fixtures)
lp = make_sandbox([
    {"v": 2, "session_id": "ab12cd34-aaaa-bbbb-cccc-000000000001", "ts": ts(100),
     "event": "agent_complete", "subagent_type": "slicer", "tail": "RESULT: SUCCESS"},
    {"v": 2, "session_id": "ab12cd34-aaaa-bbbb-cccc-000000000002", "ts": ts(200),
     "event": "agent_start", "subagent_type": "slicer-critic", "input": "review decomposition"},
])
r = observe(mk_trail(), log_path=lp)
check("E-SLICER-SLICERCRITIC cross-session", r["runtime_edges"]["E-SLICER-SLICERCRITIC"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("agent_complete", subagent_type="slicer-critic",
          tail="VERDICT: BLOCK\nfailed INVEST check", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-SLICERCRITIC-BLOCK confirmed", r["runtime_edges"]["E-SLICERCRITIC-BLOCK"]["state"], "runtime-confirmed")

# No BLOCK in tail -> not-exercised
lp = make_sandbox([
    mk_ev("agent_complete", subagent_type="slicer-critic",
          tail="VERDICT: APPROVE\nlooked good", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-SLICERCRITIC-BLOCK not-exercised (APPROVE)", r["runtime_edges"]["E-SLICERCRITIC-BLOCK"]["state"], "not-exercised")


# ============================================================
# CLASS 4: verdict-return incl. PRODUCTION_VERIFY
# ============================================================
print("\n=== CLASS 4: verdict-return ===")

# qa-tester exact subagent_type
lp = make_sandbox([
    mk_ev("skill_invoke", skill="qa-plan", ts=ts(100)),
    mk_ev("agent_start", subagent_type="qa-tester", input="run qa", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-QAPLAN-QATESTER (qa-tester type)", r["runtime_edges"]["E-QAPLAN-QATESTER"]["state"], "runtime-confirmed")

# general-purpose but input names qa-tester
lp = make_sandbox([
    mk_ev("skill_invoke", skill="qa-plan", ts=ts(100)),
    mk_ev("agent_start", subagent_type="general-purpose",
          input="dispatch qa-tester for production verify", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-QAPLAN-QATESTER (general-purpose+hint)", r["runtime_edges"]["E-QAPLAN-QATESTER"]["state"], "runtime-confirmed")

# qa-plan found but no qa-tester start -> runtime-unobserved (not finding)
lp = make_sandbox([
    mk_ev("skill_invoke", skill="qa-plan", ts=ts(100)),
    mk_ev("agent_start", subagent_type="reviewer", input="review pr", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-QAPLAN-QATESTER unobserved (qa-plan but no tester)", r["runtime_edges"]["E-QAPLAN-QATESTER"]["state"], "runtime-unobserved")

# E-QATESTER-VERDICT: tail contains PRODUCTION_VERIFY:
lp = make_sandbox([
    mk_ev("agent_complete", subagent_type="qa-tester",
          tail="PRODUCTION_VERIFY: PASS\ndetails", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-QATESTER-VERDICT confirmed", r["runtime_edges"]["E-QATESTER-VERDICT"]["state"], "runtime-confirmed")

# E-MERGE-QAPLAN
lp = make_sandbox([mk_ev("skill_invoke", skill="qa-plan", ts=ts(100))])
r = observe(mk_trail(), log_path=lp)
check("E-MERGE-QAPLAN confirmed", r["runtime_edges"]["E-MERGE-QAPLAN"]["state"], "runtime-confirmed")

# E-MERGE-QAREVIEW
lp = make_sandbox([mk_ev("skill_invoke", skill="qa-review", ts=ts(100))])
r = observe(mk_trail(), log_path=lp)
check("E-MERGE-QAREVIEW confirmed", r["runtime_edges"]["E-MERGE-QAREVIEW"]["state"], "runtime-confirmed")


# ============================================================
# CLASS 5: bash-evidence
# ============================================================
print("\n=== CLASS 5: bash-evidence ===")

lp = make_sandbox([
    mk_ev("bash_complete", command="gh issue create --label captured --title test", ts=ts(100)),
    mk_ev("skill_invoke", skill="promote-to-backlog", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-CAPTURED-PTB confirmed", r["runtime_edges"]["E-CAPTURED-PTB"]["state"], "runtime-confirmed")

# bash with --label captured but no ptb -> not-exercised
lp = make_sandbox([
    mk_ev("bash_complete", command="gh issue create --label captured --title test", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-CAPTURED-PTB bash-only (no ptb)", r["runtime_edges"]["E-CAPTURED-PTB"]["state"], "not-exercised")

# no bash at all -> not-exercised
lp = make_sandbox([mk_ev("skill_invoke", skill="build", ts=ts(100))])
r = observe(mk_trail(), log_path=lp)
check("E-CAPTURED-PTB no bash at all", r["runtime_edges"]["E-CAPTURED-PTB"]["state"], "not-exercised")


# ============================================================
# CLASS 6: conditional-advisory
# ============================================================
print("\n=== CLASS 6: conditional-advisory ===")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="audit-meta", ts=ts(100)),
    mk_ev("agent_start", subagent_type="reviewer", input="review pr", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-AUDITMETA-REVIEWER confirmed", r["runtime_edges"]["E-AUDITMETA-REVIEWER"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("skill_invoke", skill="audit-subagents", ts=ts(100)),
    mk_ev("agent_start", subagent_type="reviewer", input="review", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-AUDITSUBAGENTS-REVIEWER confirmed", r["runtime_edges"]["E-AUDITSUBAGENTS-REVIEWER"]["state"], "runtime-confirmed")

lp = make_sandbox([
    mk_ev("agent_complete", subagent_type="codebase-critic",
          tail="VERDICT: APPROVE cumulative", ts=ts(100)),
    mk_ev("agent_start", subagent_type="reviewer", input="review", ts=ts(200)),
])
r = observe(mk_trail(), log_path=lp)
check("E-CODEBASECRITIC-REVIEWER confirmed", r["runtime_edges"]["E-CODEBASECRITIC-REVIEWER"]["state"], "runtime-confirmed")

# audit-meta exists but reviewer not dispatched -> not-exercised
lp = make_sandbox([
    mk_ev("skill_invoke", skill="audit-meta", ts=ts(100)),
])
r = observe(mk_trail(), log_path=lp)
check("E-AUDITMETA-REVIEWER not-exercised (no reviewer)", r["runtime_edges"]["E-AUDITMETA-REVIEWER"]["state"], "not-exercised")


# ============================================================
# Dead-window sweep — ALL 26 runtime -> not-observable, 2 unmeasurable
# ============================================================
print("\n=== Dead-window sweep ===")
lp = make_sandbox([])
r_dead = observe(mk_trail(), log_path=lp)
not_obs = [eid for eid, e in r_dead["runtime_edges"].items() if e["state"] == "not-observable"]
unmeas  = [eid for eid, e in r_dead["runtime_edges"].items() if e["state"] == "unmeasurable"]
other   = [eid for eid, e in r_dead["runtime_edges"].items()
           if e["state"] not in ("not-observable", "unmeasurable")]
check("dead-window: 26 not-observable", str(len(not_obs)), "26")
check("dead-window: 2 unmeasurable",    str(len(unmeas)), "2")
check("dead-window: 0 other",           str(len(other)), "0")
check("dead-window: capture_liveness=False", str(r_dead["capture_liveness"]), "False")

# ============================================================
# Unmeasurable edges always stay unmeasurable regardless of events
# ============================================================
print("\n=== Unmeasurable edges ===")
lp = make_sandbox([mk_ev("skill_invoke", skill="build", ts=ts(100))])
r = observe(mk_trail(), log_path=lp)
from runtime_observer import UNMEASURABLE_EDGE_IDS
for eid in UNMEASURABLE_EDGE_IDS:
    st = r["runtime_edges"][eid]["state"]
    check(f"{eid} unmeasurable", st, "unmeasurable")


# ============================================================
# coverage_strip via compare()
# ============================================================
print("\n=== coverage_strip via compare() ===")
from pipeline_spec import get_spec
from comparison import compare
spec = get_spec()
lp = make_sandbox([mk_ev("skill_invoke", skill="build", ts=ts(100))])

# Minimal trail for a closed PRD
trail = {
    "prd_number": 999,
    "prd_created_at": WIN_START,
    "prd_closed_at": WIN_END,
    "slices": [],
    "prs": {},
    "prd_verdicts": [],
}

os.environ["WORKFLOW_LOG_DIR"] = str(lp.parent)
try:
    report = compare(spec, trail)
finally:
    os.environ["WORKFLOW_LOG_DIR"] = ""

cs = report.get("coverage_strip", {})
print(f"  total_declared: {cs.get('total_declared')} (expect 45)")
print(f"  github: {cs.get('github')} (expect 17)")
print(f"  runtime: {cs.get('runtime')} (expect 26)")
print(f"  unmeasurable_by_design: {cs.get('unmeasurable_by_design')} (expect 2)")
print(f"  not_evaluated: {cs.get('not_evaluated')} (expect 0)")
print(f"  zero_not_evaluated: {cs.get('zero_not_evaluated')} (expect True)")

check("coverage_strip total_declared=45", str(cs.get("total_declared")), "45")
check("coverage_strip github=17",         str(cs.get("github")), "17")
check("coverage_strip runtime=26",        str(cs.get("runtime")), "26")
check("coverage_strip unmeasurable=2",    str(cs.get("unmeasurable_by_design")), "2")
check("coverage_strip not_evaluated=0",   str(cs.get("not_evaluated")), "0")
check("coverage_strip zero_not_evaluated=True", str(cs.get("zero_not_evaluated")), "True")

# Verify run_pass is NOT affected by runtime states (ADR-0055 D2)
# All github always-edges should fail -> run_pass=False but runtime doesn't change that
run_pass = report.get("run_pass")
# We're not checking run_pass=True (no github evidence), just that it's a bool
check("run_pass is bool", str(isinstance(run_pass, bool)), "True")
print(f"  run_pass={run_pass} (not affected by runtime states per ADR-0055 D2)")

# Verify no not-evaluated edges in merged report
not_eval = [eid for eid, info in report["edges"].items() if info.get("state") == "not-evaluated"]
check("zero not-evaluated in merged report", str(len(not_eval)), "0")

# ============================================================
print("\n" + "="*60)
print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
if FAIL:
    print("FAILURES:")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("All tests passed.")
    sys.exit(0)
