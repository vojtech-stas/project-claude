"""
dashboard/health.py — health check helpers + /api/health TTL cache.

Exports:
    check_docs1_adr_index_forward() -> dict
    check_docs2_adr_index_reverse() -> dict
    check_docs3_claude_md_agents() -> dict
    check_docs4_claude_md_skills() -> dict
    check_docs5_n3_literal() -> dict
    check_docs6_glossary_md_refs() -> dict
    check_docs7_adr_citations() -> dict
    check_docs8_supersession_notes() -> dict
    check_docs9_glossary_cap() -> dict
    check_docs10_backlog_surfacing() -> dict
    audit_subagents() -> dict
    audit_meta() -> dict
    cascade_finder_summary() -> dict
    check_capture_slo() -> dict          (slice #767: capture liveness SLO)
    check_hook_integrity() -> dict       (slice #767: hook attempt-vs-ok ratio)
    check_isolation_group() -> dict      (slice #767: worktree orphan/drift check)
    serve_health() -> dict          (TTL-cached; <200ms on second call)
    _health_background() -> None    (background thread target)
    _health_cache, _health_lock, _health_computing, _HEALTH_TTL

Import direction: server <- health (this module must NOT import server).
"""

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — health.py lives at <repo>/dashboard/health.py
# ---------------------------------------------------------------------------
_HEALTH_REPO_ROOT = Path(__file__).resolve().parent.parent

# SKILL.md paths for parsing check rationale + mechanic text (slice #629).
_AUDIT_META_SKILL = _HEALTH_REPO_ROOT / ".claude" / "skills" / "audit-meta" / "SKILL.md"
_AUDIT_SUBAGENTS_SKILL = _HEALTH_REPO_ROOT / ".claude" / "skills" / "audit-subagents" / "SKILL.md"

# Known critics — mirrors server.py KNOWN_CRITICS (CHECK 7 regexes server.py SOURCE).
_KNOWN_CRITICS = {
    "reviewer",
    "prd-critic",
    "adr-critic",
    "slicer-critic",
    "glossary-critic",
    "backlog-critic",
    "codebase-critic",
}

# ---------------------------------------------------------------------------
# /api/health TTL cache — health checks can take 1-2 s on cold start.
# Background-thread + TTL, mirroring live.py's _live_progress_background pattern.
# ---------------------------------------------------------------------------
_health_cache: dict = {}       # {"data": {...}, "ts": float}
_health_computing: bool = False
_health_lock = threading.Lock()
_HEALTH_TTL = 30               # seconds — balance freshness vs. latency


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _skill_md_for_check(check_id: str) -> Path:
    """Return the SKILL.md path that defines the given check ID."""
    if check_id.startswith("AS-") or check_id.startswith("as-"):
        return _AUDIT_SUBAGENTS_SKILL
    return _AUDIT_META_SKILL


def _parse_skill_rationale(check_id: str) -> tuple:
    """Parse purpose (Rationale) and command (Mechanic) for a check from its SKILL.md.

    Pins the parse to the ``### <check_id> —`` heading (§6 trap) to avoid
    picking up prose mentions of the same ID elsewhere in the file.

    Returns:
        (purpose: str, command: str)
        On no match: purpose = "rationale unavailable — see SKILL.md", command = "".
    """
    skill_path = _skill_md_for_check(check_id)
    try:
        text = skill_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ("rationale unavailable — see SKILL.md", "")

    # Find the heading line: "### <check_id> — ..."
    heading_pattern = re.compile(
        r'^###\s+' + re.escape(check_id) + r'\s+—',
        re.MULTILINE,
    )
    m = heading_pattern.search(text)
    if not m:
        return ("rationale unavailable — see SKILL.md", "")

    # Slice from the heading to the next "### " heading (or end of file).
    section_start = m.start()
    next_heading = re.search(r'^###\s+', text[m.end():], re.MULTILINE)
    section_end = m.end() + next_heading.start() if next_heading else len(text)
    section = text[section_start:section_end]

    # Extract **Rationale:** block
    rationale_m = re.search(r'\*\*Rationale:\*\*\s*(.+?)(?=\n\n|\n\*\*|\n---|\Z)',
                             section, re.DOTALL)
    purpose = rationale_m.group(1).strip() if rationale_m else "rationale unavailable — see SKILL.md"
    purpose = re.sub(r'\s*\n\s*', ' ', purpose).strip()

    # Extract **Mechanic:** block
    mechanic_m = re.search(r'\*\*Mechanic:\*\*\s*(.*?)(?=\n\n\*\*|\n\n###|\n---|\Z)',
                            section, re.DOTALL)
    command = mechanic_m.group(1).strip() if mechanic_m else ""
    command = re.sub(r'^```[a-z]*\n?', '', command)
    command = re.sub(r'\n?```$', '', command)
    command = command.strip()

    return (purpose, command)


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _grep_count(pattern: str, text: str, flags=re.MULTILINE) -> int:
    return len(re.findall(pattern, text, flags))


def _grep_fixed(literal: str, text: str) -> bool:
    return literal in text


# ---------------------------------------------------------------------------
# DOCS checks
# ---------------------------------------------------------------------------

def check_docs1_adr_index_forward() -> dict:
    """DOCS-1: every link in decisions/README.md resolves to an existing file."""
    readme = _HEALTH_REPO_ROOT / "decisions" / "README.md"
    if not readme.exists():
        return {"id": "DOCS-1", "result": "FAIL", "detail": "decisions/README.md missing"}
    text = _read_file(readme)
    refs = re.findall(r'\(?([0-9]{4}-[a-z0-9-]+\.md)\)?', text)
    missing = []
    for ref in set(refs):
        if not (_HEALTH_REPO_ROOT / "decisions" / ref).exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-1", "result": "FAIL", "detail": f"Dangling refs: {missing}"}
    return {"id": "DOCS-1", "result": "PASS", "detail": ""}


def check_docs2_adr_index_reverse() -> dict:
    """DOCS-2: every decisions/NNNN-*.md is in decisions/README.md."""
    readme = _HEALTH_REPO_ROOT / "decisions" / "README.md"
    decisions_dir = _HEALTH_REPO_ROOT / "decisions"
    if not readme.exists():
        return {"id": "DOCS-2", "result": "FAIL", "detail": "decisions/README.md missing"}
    text = _read_file(readme)
    missing = []
    for f in sorted(decisions_dir.glob("[0-9]*.md")):
        if f.name not in text:
            missing.append(f.name)
    if missing:
        return {"id": "DOCS-2", "result": "FAIL", "detail": f"Not indexed: {missing}"}
    return {"id": "DOCS-2", "result": "PASS", "detail": ""}


def check_docs3_claude_md_agents() -> dict:
    """DOCS-3: every .claude/agents/*.md ref in CLAUDE.md Map exists."""
    claude_md = _HEALTH_REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-3", "result": "FAIL", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    refs = re.findall(r'\.claude/agents/([a-z-]+\.md)', text)
    missing = []
    for ref in set(refs):
        if not (_HEALTH_REPO_ROOT / ".claude" / "agents" / ref).exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-3", "result": "FAIL", "detail": f"Missing agents: {missing}"}
    return {"id": "DOCS-3", "result": "PASS", "detail": ""}


def check_docs4_claude_md_skills() -> dict:
    """DOCS-4: every .claude/skills/*/SKILL.md ref in CLAUDE.md Map exists."""
    claude_md = _HEALTH_REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-4", "result": "FAIL", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    refs = re.findall(r'\.claude/skills/([a-z-]+)/SKILL\.md', text)
    missing = []
    for ref in set(refs):
        if not (_HEALTH_REPO_ROOT / ".claude" / "skills" / ref / "SKILL.md").exists():
            missing.append(ref)
    if missing:
        return {"id": "DOCS-4", "result": "FAIL", "detail": f"Missing skills: {missing}"}
    return {"id": "DOCS-4", "result": "PASS", "detail": ""}


def check_docs5_n3_literal() -> dict:
    """DOCS-5: no bare N=3 in README.md without adjacent ADR-0013."""
    readme = _HEALTH_REPO_ROOT / "README.md"
    if not readme.exists():
        return {"id": "DOCS-5", "result": "PASS", "detail": "README.md missing (skip)"}
    lines = _read_file(readme).splitlines()
    offenders = []
    for i, line in enumerate(lines):
        if "N=3" in line:
            ctx_start = max(0, i - 2)
            ctx_end = min(len(lines), i + 3)
            ctx = "\n".join(lines[ctx_start:ctx_end])
            if "ADR-0013" not in ctx:
                offenders.append(f"L{i+1}: {line.strip()}")
    if offenders:
        return {"id": "DOCS-5", "result": "FAIL", "detail": f"Bare N=3: {offenders}"}
    return {"id": "DOCS-5", "result": "PASS", "detail": ""}


def check_docs6_glossary_md_refs() -> dict:
    """DOCS-6: no GLOSSARY.md refs outside the 2-file allowlist + decisions/."""
    allowlist = {
        ".claude/skills/audit-meta/SKILL.md",
        ".claude/skills/grill-me/SKILL.md",
    }
    offenders = []
    for md_file in _HEALTH_REPO_ROOT.rglob("*.md"):
        rel = str(md_file.relative_to(_HEALTH_REPO_ROOT)).replace("\\", "/")
        # Skip .git, worktrees, tool-results, decisions/, .claude/logs/
        if any(skip in rel for skip in [".git/", "worktrees/", "tool-results/", "decisions/", ".claude/logs/"]):
            continue
        if rel in allowlist:
            continue
        try:
            if "GLOSSARY.md" in md_file.read_text(encoding="utf-8", errors="replace"):
                offenders.append(rel)
        except Exception:
            pass
    if offenders:
        return {"id": "DOCS-6", "result": "FAIL", "detail": f"GLOSSARY.md refs: {offenders}"}
    return {"id": "DOCS-6", "result": "PASS", "detail": ""}


def check_docs7_adr_citations() -> dict:
    """DOCS-7: every [ADR-NNNN](decisions/NNNN-*.md) citation resolves."""
    fake_slugs = re.compile(
        r'decisions/00\d{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md'
    )
    offenders = []
    for md_file in _HEALTH_REPO_ROOT.rglob("*.md"):
        rel = str(md_file.relative_to(_HEALTH_REPO_ROOT)).replace("\\", "/")
        if ".git/" in rel or "worktrees/" in rel or ".claude/logs/" in rel:
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for target in re.findall(r'decisions/[0-9]{4}-[a-z0-9-]+\.md', text):
            if fake_slugs.match(target):
                continue
            if not (_HEALTH_REPO_ROOT / target).exists():
                offenders.append(f"{rel} -> {target}")
    if offenders:
        return {"id": "DOCS-7", "result": "FAIL", "detail": f"Dangling ADR citations: {offenders[:5]}"}
    return {"id": "DOCS-7", "result": "PASS", "detail": ""}


def check_docs8_supersession_notes() -> dict:
    """DOCS-8 (WARN): decisions/README.md Status column has superseded-by annotations (per-pair)."""
    readme = _HEALTH_REPO_ROOT / "decisions" / "README.md"
    if not readme.exists():
        return {"id": "DOCS-8", "result": "WARN", "detail": "decisions/README.md missing"}
    readme_lines = _read_file(readme).splitlines()
    missing_annotations = []
    decisions_dir = _HEALTH_REPO_ROOT / "decisions"
    for adr_file in sorted(decisions_dir.glob("[0-9]*.md")):
        try:
            adr_text = _read_file(adr_file)
            for match in re.finditer(r'^- \*\*Supersedes:\*\*\s*(.+)$', adr_text, re.MULTILINE):
                superseded_ref = match.group(1).strip()
                # Skip "Supersedes: none" — explicitly declares no supersession
                if re.match(r'none\.?\s', superseded_ref, re.IGNORECASE) or \
                        superseded_ref.lower().startswith('none'):
                    continue
                # Strip negated-prose clauses ("Does NOT supersede X") before
                # extracting IDs so negation doesn't produce false positives.
                # Example: "... Does NOT supersede ADR-0001 or ADR-0002 (frozen)"
                pos = re.search(r'\bdoes\s+not\s+supersede\b', superseded_ref, re.IGNORECASE)
                if pos:
                    superseded_ref = superseded_ref[:pos.start()]
                superseded_ids = re.findall(r'ADR-(\d{4})', superseded_ref)
                if not superseded_ids:
                    superseded_ids = re.findall(r'\b(\d{4})\b', superseded_ref)
                for sid in superseded_ids:
                    row_found = False
                    row_has_annotation = False
                    for line in readme_lines:
                        if line.startswith("|") and f"({sid}-" in line:
                            row_found = True
                            if "superseded by" in line.lower():
                                row_has_annotation = True
                            break
                    if row_found and not row_has_annotation:
                        missing_annotations.append(
                            f"{adr_file.name} supersedes ADR-{sid}: missing 'superseded by' in README row"
                        )
        except Exception:
            pass
    if missing_annotations:
        return {"id": "DOCS-8", "result": "WARN", "detail": f"Missing annotations: {missing_annotations[:3]}"}
    return {"id": "DOCS-8", "result": "PASS", "detail": ""}


def check_docs9_glossary_cap() -> dict:
    """DOCS-9 (WARN): CLAUDE.md glossary entry count <= 35."""
    claude_md = _HEALTH_REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "DOCS-9", "result": "WARN", "detail": "CLAUDE.md missing"}
    text = _read_file(claude_md)
    lines = text.splitlines()
    in_glossary = False
    count = 0
    for line in lines:
        # Match the actual H3 heading: "### Glossary (key terms)"
        if re.match(r'^### Glossary', line):
            in_glossary = True
            continue
        if in_glossary and re.match(r'^### ', line):
            break
        if in_glossary and re.match(r'^- \*\*', line):
            count += 1
    if count > 35:
        return {"id": "DOCS-9", "result": "WARN", "detail": f"Glossary has {count} entries (cap 35)"}
    return {"id": "DOCS-9", "result": "PASS", "detail": f"{count} entries"}


def check_docs10_backlog_surfacing() -> dict:
    """DOCS-10: no backlog-label surfacing idiom in agents/skills (except allowlist)."""
    allowlist = {"backlog-critic.md", "promote-to-backlog", "audit-meta/SKILL.md", "audit-subagents/SKILL.md"}
    pattern = re.compile(r'(`backlog`-labeled|--label backlog)')
    offenders = []
    for search_dir in [_HEALTH_REPO_ROOT / ".claude" / "agents", _HEALTH_REPO_ROOT / ".claude" / "skills"]:
        if not search_dir.exists():
            continue
        for md_file in search_dir.rglob("*.md"):
            rel = str(md_file.relative_to(_HEALTH_REPO_ROOT)).replace("\\", "/")
            if any(skip in rel for skip in allowlist):
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                if pattern.search(text):
                    offenders.append(rel)
            except Exception:
                pass
    if offenders:
        return {"id": "DOCS-10", "result": "FAIL", "detail": f"Backlog-label drift: {offenders}"}
    return {"id": "DOCS-10", "result": "PASS", "detail": ""}


# ---------------------------------------------------------------------------
# AS-* checks
# ---------------------------------------------------------------------------

def _check_as_all_1(path: Path) -> dict:
    """AS-ALL-1: frontmatter name/description/tools/model."""
    text = _read_file(path)
    count = len(re.findall(r'^(name|description|tools|model):', text, re.MULTILINE))
    result = "PASS" if count >= 4 else "FAIL"
    return {"id": "AS-ALL-1", "result": result, "detail": f"field count={count}"}


def _check_as_all_2(path: Path) -> dict:
    """AS-ALL-2: Tool boundaries section heading."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*Tool boundaries', text, re.MULTILINE))
    return {"id": "AS-ALL-2", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_all_3(path: Path) -> dict:
    """AS-ALL-3: cross-reference section heading."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*.*(References|Related|See also|Cross-refs)', text,
                        re.MULTILINE | re.IGNORECASE))
    return {"id": "AS-ALL-3", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_all_4(path: Path) -> dict:
    """AS-ALL-4: no backlog-label surfacing idiom (backlog-critic excluded)."""
    if path.name == "backlog-critic.md":
        return {"id": "AS-ALL-4", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    has_drift = bool(re.search(r'(`backlog`-labeled|--label backlog)', text))
    return {"id": "AS-ALL-4", "result": "FAIL" if has_drift else "PASS", "detail": ""}


def _check_as_all_5(path: Path) -> dict:
    """AS-ALL-5: Mandatory reading order OR When invoked section."""
    text = _read_file(path)
    ok = bool(re.search(r'^#+\s*(Mandatory reading order|When invoked)', text, re.MULTILINE))
    return {"id": "AS-ALL-5", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_1(path: Path) -> dict:
    """AS-CRIT-1: Default conservative literal."""
    ok = "Default conservative" in _read_file(path)
    return {"id": "AS-CRIT-1", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_2(path: Path) -> dict:
    """AS-CRIT-2: paranoid OR Adversarial mindset (backlog-critic excluded)."""
    if path.name == "backlog-critic.md":
        return {"id": "AS-CRIT-2", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    ok = bool(re.search(r'(paranoid|Adversarial mindset)', text))
    return {"id": "AS-CRIT-2", "result": "PASS" if ok else "FAIL", "detail": ""}


def _check_as_crit_3(path: Path) -> dict:
    """AS-CRIT-3: VERDICT, REASON, ROUND documented in critic body.

    Aligned with tools/ci-checks.sh CHECK 10: bare-string grep (no colon
    required) so fenced-block examples AND backtick-quoted key names both pass.
    backlog-critic omits ROUND by design (fires once; no multi-round loop) —
    its ROUND check is N/A, matching its documented Output format section.
    """
    text = _read_file(path)
    has_verdict = "VERDICT" in text
    has_reason = "REASON" in text
    # backlog-critic documents "ROUND: is omitted" by design — N/A for ROUND
    if path.name == "backlog-critic.md":
        ok = has_verdict and has_reason
        if ok:
            return {"id": "AS-CRIT-3", "result": "PASS",
                    "detail": "ROUND N/A (single-fire; no multi-round loop)"}
        missing = [k for k, v in [("VERDICT", has_verdict), ("REASON", has_reason)] if not v]
        return {"id": "AS-CRIT-3", "result": "FAIL",
                "detail": f"missing: {', '.join(missing)}"}
    has_round = "ROUND" in text
    ok = has_verdict and has_reason and has_round
    missing = [k for k, v in [("VERDICT", has_verdict), ("REASON", has_reason),
                               ("ROUND", has_round)] if not v]
    return {"id": "AS-CRIT-3", "result": "PASS" if ok else "FAIL",
            "detail": "" if ok else f"missing: {', '.join(missing)}"}


def _check_as_crit_4(path: Path) -> dict:
    """AS-CRIT-4: documentation-contract check.

    Verifies the critic documents its verdict-body output contract by delegation:
    (a) an Output-format section heading is present AND
    (b) an ADR-0005 citation is present.
    Both required; any absent → FAIL.
    """
    text = _read_file(path)
    has_output_format = bool(re.search(r'^#+\s*Output format', text, re.MULTILINE))
    has_adr0005 = "ADR-0005" in text
    ok = has_output_format and has_adr0005
    missing = []
    if not has_output_format:
        missing.append("Output format heading")
    if not has_adr0005:
        missing.append("ADR-0005 citation")
    return {"id": "AS-CRIT-4", "result": "PASS" if ok else "FAIL",
            "detail": "" if ok else f"missing: {', '.join(missing)}"}


def _check_as_gen_1(path: Path) -> dict:
    """AS-GEN-1: RESULT: REASON: ARTIFACTS: in generator body."""
    text = _read_file(path)
    ok = "RESULT:" in text and "REASON:" in text and "ARTIFACTS:" in text
    return {"id": "AS-GEN-1", "result": "PASS" if ok else "FAIL", "detail": ""}


def _is_critic(stem: str, path: Path) -> bool:
    return stem in _KNOWN_CRITICS or stem == "reviewer" or stem.endswith("-critic")


def _enrich_checks(checks: list) -> list:
    """Add purpose + command fields to each check dict from the SKILL.md (slice #629).

    Mutates each dict in-place and returns the list for convenience.
    purpose / command are sourced from the SKILL.md rationale/mechanic blocks
    so CHECK 9 stays green (no hand-authored copies in dashboard source).
    """
    for c in checks:
        check_id = c.get("id", "")
        if check_id:
            purpose, command = _parse_skill_rationale(check_id)
        else:
            purpose, command = ("rationale unavailable — see SKILL.md", "")
        c["purpose"] = purpose
        c["command"] = command
    return checks


def audit_subagents() -> dict:
    agents_dir = _HEALTH_REPO_ROOT / ".claude" / "agents"
    results = {}
    if not agents_dir.exists():
        return results
    for agent_md in sorted(agents_dir.glob("*.md")):
        stem = agent_md.stem
        is_crit = _is_critic(stem, agent_md)
        checks = [
            _check_as_all_1(agent_md),
            _check_as_all_2(agent_md),
            _check_as_all_3(agent_md),
            _check_as_all_4(agent_md),
            _check_as_all_5(agent_md),
        ]
        if is_crit:
            checks += [
                _check_as_crit_1(agent_md),
                _check_as_crit_2(agent_md),
                _check_as_crit_3(agent_md),
                _check_as_crit_4(agent_md),
            ]
        else:
            checks.append(_check_as_gen_1(agent_md))
        results[stem] = {
            "type": "critic" if is_crit else "generator",
            "checks": _enrich_checks(checks),
        }
    return results


def audit_meta() -> dict:
    checks = [
        check_docs1_adr_index_forward(),
        check_docs2_adr_index_reverse(),
        check_docs3_claude_md_agents(),
        check_docs4_claude_md_skills(),
        check_docs5_n3_literal(),
        check_docs6_glossary_md_refs(),
        check_docs7_adr_citations(),
        check_docs8_supersession_notes(),
        check_docs9_glossary_cap(),
        check_docs10_backlog_surfacing(),
    ]
    return {"checks": _enrich_checks(checks)}


def cascade_finder_summary() -> dict:
    cascade_script = _HEALTH_REPO_ROOT / "tools" / "cascade-finder.py"
    if not cascade_script.exists():
        return {"available": False, "detail": "tools/cascade-finder.py not found"}
    try:
        subprocess.run(
            [sys.executable, str(cascade_script), "--help"],
            capture_output=True, text=True, timeout=10, cwd=str(_HEALTH_REPO_ROOT),
        )
        return {"available": True, "detail": "cascade-finder.py present; use /api/architecture edges for data"}
    except Exception as e:
        return {"available": False, "detail": str(e)}


# ---------------------------------------------------------------------------
# Substrate health checks (slice #767)
# ---------------------------------------------------------------------------

# Boundary-only event types that do NOT count as "live" capture (PRD #763 §2 cr.7)
_BOUNDARY_EVENTS = frozenset({"session_start", "session_stop"})

# Window size for capture SLO: last N sessions with any event in workflow-events.jsonl
_CAPTURE_SLO_WINDOW = 20

# ADR-0042: bootstrap cutoff for merged_without_ci — PRs merged before this PR are
# grandfathered (CI gate did not exist yet).  PR #711 was the first one under ADR-0042.
_CI_GATE_BOOTSTRAP_PR = 711


def check_capture_slo() -> dict:
    """CAPTURE-SLO: sessions with ≥1 non-boundary event / total, last N sessions.

    Reads workflow-events.jsonl (read-only).  Red when fewer than 50% of sessions
    in the last _CAPTURE_SLO_WINDOW have a non-boundary event (i.e. hooks are mostly dead).

    Returns per-session liveness detail.
    """
    events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    if not events_log.exists():
        return {
            "id": "CAPTURE-SLO",
            "result": "WARN",
            "detail": "workflow-events.jsonl not found",
        }

    try:
        import json as _json
        sessions: dict[str, set] = {}  # session_id → set of non-boundary event types
        with events_log.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = _json.loads(raw)
                except Exception:
                    continue
                sid = obj.get("session_id", "")
                ev = obj.get("event", "")
                if not sid:
                    continue
                if sid not in sessions:
                    sessions[sid] = set()
                if ev and ev not in _BOUNDARY_EVENTS:
                    sessions[sid].add(ev)
    except Exception as exc:
        return {"id": "CAPTURE-SLO", "result": "WARN",
                "detail": f"read error: {exc}"}

    if not sessions:
        return {"id": "CAPTURE-SLO", "result": "WARN",
                "detail": "no sessions found in workflow-events.jsonl"}

    # Take the last N sessions (by insertion order in dict — Python 3.7+)
    window = list(sessions.items())[-_CAPTURE_SLO_WINDOW:]
    total = len(window)
    live_count = sum(1 for _sid, evs in window if evs)
    boundary_only = total - live_count
    ratio = live_count / total if total > 0 else 0.0

    # Per-session liveness summary (most recent first, capped at 10 for detail string)
    per_session_notes = []
    for sid, evs in reversed(window[-10:]):
        tag = "live" if evs else "boundary-only"
        per_session_notes.append(f"{sid[:8]}:{tag}")

    detail = (
        f"{live_count}/{total} live in last {_CAPTURE_SLO_WINDOW}-session window "
        f"(SLO {ratio*100:.0f}%) | "
        + ", ".join(per_session_notes)
    )

    # Red when <50% live
    result = "PASS" if ratio >= 0.50 else "FAIL"
    return {"id": "CAPTURE-SLO", "result": result, "detail": detail}


def check_hook_integrity() -> dict:
    """HOOK-INTEGRITY: attempt-vs-ok beacon ratio per hook + ERROR beacon count.

    Reads hook-fires.jsonl (read-only).  Red when any hook's ok rate < attempt rate
    (i.e. some attempts never produced an ok) or when ERROR beacons are present.
    """
    fires_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "hook-fires.jsonl"
    if not fires_log.exists():
        return {
            "id": "HOOK-INTEGRITY",
            "result": "WARN",
            "detail": "hook-fires.jsonl not found",
        }

    try:
        import json as _json
        attempts: dict[str, int] = {}
        oks: dict[str, int] = {}
        error_count = 0
        with fires_log.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = _json.loads(raw)
                except Exception:
                    continue
                hook = obj.get("hook", "")
                status = obj.get("status", "")
                if not hook:
                    continue
                if status == "attempt":
                    attempts[hook] = attempts.get(hook, 0) + 1
                elif status == "ok":
                    oks[hook] = oks.get(hook, 0) + 1
                elif status == "ERROR" or status == "error":
                    error_count += 1
    except Exception as exc:
        return {"id": "HOOK-INTEGRITY", "result": "WARN",
                "detail": f"read error: {exc}"}

    # Compute per-hook ratios (only hooks that have attempt beacons)
    drift_hooks = []
    ratio_parts = []
    for hook, att in sorted(attempts.items()):
        ok = oks.get(hook, 0)
        ratio_parts.append(f"{hook}:{ok}/{att}")
        if ok < att:
            drift_hooks.append(f"{hook}({ok}/{att})")

    detail_parts = []
    if ratio_parts:
        detail_parts.append("ratios: " + ", ".join(ratio_parts))
    if error_count:
        detail_parts.append(f"ERROR beacons: {error_count}")
    if drift_hooks:
        detail_parts.append(f"drift: {', '.join(drift_hooks)}")

    detail = " | ".join(detail_parts) if detail_parts else "no attempt beacons found"
    result = "FAIL" if (drift_hooks or error_count > 0) else "PASS"
    return {"id": "HOOK-INTEGRITY", "result": result, "detail": detail}


def check_isolation_group() -> dict:
    """ISOLATION-GROUP: orphaned worktree dirs, prune drift, escaped dispatches.

    Checks:
    1. Dirs under .claude/worktrees/ that are NOT registered in `git worktree list`
       (orphaned — agent-* dirs left behind after the worktree was removed).
    2. Worktrees that are 0-ahead + clean relative to origin/main (prune drift —
       they could be pruned).

    Read-only: never removes anything; only reports.
    """
    worktrees_dir = _HEALTH_REPO_ROOT / ".claude" / "worktrees"
    if not worktrees_dir.exists():
        return {
            "id": "ISOLATION-GROUP",
            "result": "PASS",
            "detail": ".claude/worktrees/ does not exist (no dispatches yet)",
        }

    # Get registered worktrees from git
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        registered_paths: set[str] = set()
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("worktree "):
                    wt_path = line[len("worktree "):].strip()
                    registered_paths.add(wt_path.lower())
    except Exception as exc:
        return {"id": "ISOLATION-GROUP", "result": "WARN",
                "detail": f"git worktree list failed: {exc}"}

    # Scan dirs under .claude/worktrees/
    orphaned = []
    prune_drift = []
    try:
        dirs = sorted(d for d in worktrees_dir.iterdir() if d.is_dir())
    except Exception as exc:
        return {"id": "ISOLATION-GROUP", "result": "WARN",
                "detail": f"scan failed: {exc}"}

    for d in dirs:
        path_lower = str(d).lower()
        registered = any(
            path_lower == rp or path_lower.rstrip("/\\") == rp.rstrip("/\\")
            for rp in registered_paths
        )
        if not registered:
            orphaned.append(d.name)
            continue

        # Check prune-drift: 0-ahead and clean
        try:
            ahead = subprocess.run(
                ["git", "rev-list", "--count", "origin/main..HEAD"],
                capture_output=True, text=True, timeout=8, cwd=str(d),
            )
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=8, cwd=str(d),
            )
            if (ahead.returncode == 0 and ahead.stdout.strip() == "0"
                    and status.returncode == 0 and not status.stdout.strip()):
                prune_drift.append(d.name)
        except Exception:
            pass  # skip drift check for this worktree; not an error

    parts = []
    if orphaned:
        parts.append(f"orphaned: {', '.join(orphaned[:5])}")
    if prune_drift:
        parts.append(f"prune-drift: {', '.join(prune_drift[:5])}")

    # Escaped-dispatch note (informational only; not computable from logs alone)
    total_dirs = len(dirs)
    parts.append(f"dirs: {total_dirs}, registered: {len(registered_paths)}")

    result = "FAIL" if orphaned else "WARN" if prune_drift else "PASS"
    detail = " | ".join(parts) if parts else f"dirs: {total_dirs}"
    return {"id": "ISOLATION-GROUP", "result": result, "detail": detail}


def _build_health_data() -> dict:
    """Build the full /api/health payload synchronously.

    Called from the background thread; never from an HTTP handler.
    """
    return {
        "auditMeta": audit_meta(),
        "auditSubagents": audit_subagents(),
        "cascadeFinder": cascade_finder_summary(),
        "substrateMeta": {
            "checks": [
                check_capture_slo(),
                check_hook_integrity(),
                check_isolation_group(),
            ]
        },
    }


def _health_background() -> None:
    """Compute health data in a background thread and cache the result."""
    global _health_computing
    try:
        result = _build_health_data()
        with _health_lock:
            _health_cache["data"] = result
            _health_cache["ts"] = time.time()
    except Exception as e:
        with _health_lock:
            _health_cache["data"] = {
                "error": str(e),
                "auditMeta": {"checks": []},
                "auditSubagents": {},
                "cascadeFinder": {"available": False, "detail": f"error: {e}"},
                "substrateMeta": {"checks": []},
            }
            _health_cache["ts"] = time.time()
    finally:
        with _health_lock:
            _health_computing = False


def serve_health() -> tuple:
    """Return (payload_dict, is_fresh: bool).

    Stale-while-revalidate: if a previous payload exists, return it immediately
    (with "refreshing":true while a rebuild is in flight).
    {"status":"computing"} only when no payload has ever been built.
    Kicks off a background thread on cache miss or TTL expiry.
    Returns (data_dict, started_background: bool).
    """
    import threading as _threading
    global _health_computing
    with _health_lock:
        cached = _health_cache.get("data")
        now = time.time()
        ts = _health_cache.get("ts", 0)
        expired = (now - ts) >= _HEALTH_TTL
        if cached is not None and not expired:
            return cached, False
        if cached is not None and expired:
            payload = dict(cached)
            payload["refreshing"] = True
            if not _health_computing:
                _health_computing = True
                t = _threading.Thread(target=_health_background, daemon=True)
                t.start()
            return payload, False
        # No payload yet — bootstrap case
        if _health_computing:
            return {"status": "computing"}, True
        _health_computing = True
    t = _threading.Thread(target=_health_background, daemon=True)
    t.start()
    return {"status": "computing"}, True
