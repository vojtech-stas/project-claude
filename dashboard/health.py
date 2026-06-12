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
    check_docs11_dead_citations() -> dict  (slice #796/ADR-0064 D2: dead-citation check)
    check_r_sensitive_detector() -> dict   (slice #796/ADR-0064 D4: enforcement-path PR advisory)
    audit_subagents() -> dict
    audit_meta() -> dict
    cascade_finder_summary() -> dict
    check_capture_slo() -> dict          (slice #767: capture liveness SLO)
    check_hook_integrity() -> dict       (slice #767: hook attempt-vs-ok ratio)
    check_isolation_group() -> dict      (slice #767: worktree orphan/drift check)
    check_rule_coverage() -> dict        (slice #768/ADR-0056 D3: rule coverage ratio)
    check_spec_coverage() -> dict        (slice #798/ADR-0066 D2: per-PRD criterion coverage)
    check_blind_dispatch_rate() -> dict  (slice #783/ADR-0060 D1: BLIND-REVIEW prefix rate)
    check_residual_ratio() -> dict       (slice #797/ADR-0066 D1: JUDGMENT+EXTRACT_FAILED / total QA-plan rows)
    check_proof_presence() -> dict       (slice #783/ADR-0061 D1: route+proof-token per merged PR)
    check_merge_integrity() -> dict      (slice #783/ADR-0062 D1: BEHIND encountered/recovered)
    check_capture_shape() -> dict        (slice #783/ADR-0063 D2: 3-heading regex over root-cause issues)
    check_green_main() -> dict           (slice #783/ADR-0062 D3: last main_green sha + lag + age)
    serve_health() -> dict          (TTL-cached; <200ms on second call)
    _health_background() -> None    (background thread target)
    _health_cache, _health_lock, _health_computing, _HEALTH_TTL

Import direction: server <- health (this module must NOT import server).
"""

import os
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
# DOCS-11 — dead-citation check (ADR-0064 D2)
# ---------------------------------------------------------------------------

# Seeded allowlist: frozenset of (relative_path_posix, adr_number_str) pairs
# that are intentional/historical citations; the superseder need not appear
# on the same line.  Each entry is documented below with a one-line reason.
_DOCS11_ALLOWLIST: frozenset = frozenset({
    # prd-critic.md: "per ADR-0031 D10" appears inside a rubric example string
    # demonstrating how a PRD author would cite an ADR in a non-goal entry.
    # This is illustrative/historical text, not live authority governing behavior.
    (".claude/agents/prd-critic.md", "0031"),
    # slicer-critic.md: "ADR-0031 — T3 thin-prompt migration" in the References
    # section is a historical migration provenance note.  slicer-critic is owned
    # by slices 3–5 of PRD #794; edits are deferred to avoid cross-slice conflicts.
    (".claude/agents/slicer-critic.md", "0031"),
})


def _fully_superseded_adrs() -> dict:
    """Return {adr_number_str: superseding_adr_str} for fully-superseded ADRs.

    Parses decisions/README.md index table rows.  An ADR qualifies when its
    Status column contains "superseded entirely" or "Superseded in full"
    (case-insensitive), indicating the entire ADR (all Decisions) is superseded.
    Returns an empty dict if the file is missing or unparseable.
    """
    readme = _HEALTH_REPO_ROOT / "decisions" / "README.md"
    result: dict = {}
    try:
        text = readme.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return result
    row_pat = re.compile(
        r'^\|\s*\[?(\d{4})\]?[^|]*\|[^|]+\|\s*(.*?)\s*\|?\s*$',
        re.MULTILINE,
    )
    superseded_pat = re.compile(
        r'(?:superseded entirely|Superseded in full)\s+by\s+\[?ADR-(0\d{3})\]?',
        re.IGNORECASE,
    )
    for m in row_pat.finditer(text):
        adr_num = m.group(1)
        status = m.group(2)
        sm = superseded_pat.search(status)
        if sm:
            result[adr_num] = sm.group(1)  # superseding ADR number (4-digit str)
    return result


_SUPERSEDED_ADRS: dict = _fully_superseded_adrs()


def check_docs11_dead_citations() -> dict:
    """DOCS-11: no dead citations of fully-superseded ADRs in .claude/ runtime prompts.

    Implements ADR-0064 D2.

    Scans .claude/agents/*.md, .claude/skills/*/SKILL.md, and .claude/settings.json
    for citations of ADR numbers that are fully superseded in decisions/README.md
    (status contains "superseded entirely" or "Superseded in full"), unless:
      (a) the citing line also names the superseding ADR, OR
      (b) the (file, adr_number) pair appears in _DOCS11_ALLOWLIST.

    Reports offenders as "file:line cites ADR-NNNN (superseded by ADR-MMMM)".
    PASS when offender list is empty.
    """
    if not _SUPERSEDED_ADRS:
        return {
            "id": "DOCS-11",
            "result": "WARN",
            "detail": "could not parse superseded ADRs from decisions/README.md",
        }

    offenders = []
    search_roots = [
        _HEALTH_REPO_ROOT / ".claude" / "agents",
        _HEALTH_REPO_ROOT / ".claude" / "skills",
    ]
    settings_file = _HEALTH_REPO_ROOT / ".claude" / "settings.json"
    files_to_scan: list = []
    for root in search_roots:
        if root.exists():
            files_to_scan.extend(sorted(root.rglob("*.md")))
    if settings_file.exists():
        files_to_scan.append(settings_file)

    for file_path in files_to_scan:
        rel = str(file_path.relative_to(_HEALTH_REPO_ROOT)).replace("\\", "/")
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            all_adrs_on_line = set(re.findall(r'ADR-(\d{4})', line))
            for dead_num, superseder_num in _SUPERSEDED_ADRS.items():
                if dead_num not in all_adrs_on_line:
                    continue
                if (rel, dead_num) in _DOCS11_ALLOWLIST:
                    continue
                if superseder_num in all_adrs_on_line:
                    continue
                offenders.append(
                    f"{rel}:{lineno} cites ADR-{dead_num} "
                    f"(superseded by ADR-{superseder_num})"
                )

    if offenders:
        return {
            "id": "DOCS-11",
            "result": "FAIL",
            "detail": f"{len(offenders)} dead citation(s): {offenders[:5]}",
            "offenders": offenders,
        }
    return {
        "id": "DOCS-11",
        "result": "PASS",
        "detail": (
            f"no dead citations; "
            f"{len(_SUPERSEDED_ADRS)} fully-superseded ADRs checked"
        ),
    }


# ---------------------------------------------------------------------------
# R-SENSITIVE-DETECTOR — enforcement-path PR advisory detector (ADR-0064 D4)
# ---------------------------------------------------------------------------

# Enforcement-layer paths per ADR-0064 D4.
_ENFORCEMENT_PATHS: tuple = (
    ".github/workflows/",
    ".claude/settings.json",
    ".claude/hooks/",
    "tools/ci-checks.sh",
    ".githooks/",
)

# Bootstrap window: PRs at or below this number are grandfathered.
# R-SENSITIVE rule + detector ship in wave-3 (PR ~#800); earlier PRs are exempt.
_R_SENSITIVE_BOOTSTRAP_PR = 800

# Scan window: look at the last N merged PRs to bound the check cost.
_R_SENSITIVE_WINDOW = 20

# ACK signal: label name or body keyword indicating a human acknowledged the PR.
_ACK_LABEL = "human-ack"


def check_r_sensitive_detector() -> dict:
    """R-SENSITIVE-DETECTOR: enforcement-path merged PRs without human-ack (advisory).

    Implements ADR-0064 D4 — ADVISORY ONLY.  R-SENSITIVE activation is deferred
    until the workflow-v2 wave-4 closing slice merges; until then this detector
    counts violations but result is always WARN (never FAIL).

    Scans the last _R_SENSITIVE_WINDOW merged PRs (post-bootstrap) for PRs that
    touched at least one enforcement-layer path and lacked a human-ack signal
    (label "human-ack" OR body containing "human-ack").
    """
    try:
        from collector import get_recent_merged_prs  # noqa: PLC0415
        prs = get_recent_merged_prs(limit=_R_SENSITIVE_WINDOW + 10)
    except Exception as e:
        return {
            "id": "R-SENSITIVE-DETECTOR",
            "result": "WARN",
            "detail": (
                f"ADVISORY (deferred activation per ADR-0064 D4); "
                f"could not fetch PRs: {e}"
            ),
        }

    def _is_enforcement(path: str) -> bool:
        for ep in _ENFORCEMENT_PATHS:
            if ep.endswith("/"):
                if path.startswith(ep):
                    return True
            else:
                if path == ep:
                    return True
        return False

    violations = []
    for pr in prs:
        pr_num = pr.get("number", 0)
        if pr_num <= _R_SENSITIVE_BOOTSTRAP_PR:
            continue  # grandfathered

        labels = [lb.get("name", "") for lb in pr.get("labels", [])]
        if _ACK_LABEL in labels:
            continue

        body = pr.get("body", "") or ""
        if _ACK_LABEL in body:
            continue

        files = [f.get("path", "") for f in pr.get("files", [])]
        if any(_is_enforcement(f) for f in files):
            violations.append(pr_num)

    count = len(violations)
    detail = (
        f"ADVISORY (activation deferred per ADR-0064 D4): "
        f"{count} enforcement-path PR(s) without human-ack in last "
        f"{_R_SENSITIVE_WINDOW} post-bootstrap merged PRs; "
        f"PRs: {violations[:10]}"
    )
    return {
        "id": "R-SENSITIVE-DETECTOR",
        "result": "WARN",
        "detail": detail,
        "violation_count": count,
        "violation_prs": violations[:10],
    }


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
        check_docs11_dead_citations(),
        check_r_sensitive_detector(),
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
                    # Normalize separators + case so forward-slash (git porcelain)
                    # and backslash (Path.iterdir on Windows) compare equal (B1).
                    registered_paths.add(
                        os.path.normcase(os.path.normpath(wt_path))
                    )
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
        # Normalize both sides: Path.iterdir yields backslash paths on Windows
        # while git porcelain yields forward slashes; normcase+normpath unifies both.
        path_norm = os.path.normcase(os.path.normpath(str(d)))
        registered = path_norm in registered_paths
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


def check_rule_coverage() -> dict:
    """RULE-COVERAGE (WARN): ratio of CLAUDE.md section-1 rules that name a check or are (advisory).

    Heuristic: scans for bold "rule #N" entries in section 1 (stops at the first H2
    after section 1's opening list).  A rule is considered "covered" when its text
    contains any of the coverage signals below, OR the entry carries the literal
    string "(advisory)".

    Coverage signals (simple substring search — honest heuristic, not exhaustive):
      - "CI grep", "ci-checks", "tools/ci-checks"
      - "hook validation", "pre-commit", ".claude/hooks"
      - "dashboard evaluator", "health check", "trail evaluator"
      - "output-contract", "trailer schema"
      - "reviewer rule", "R-", "AC-", "SC-", "PC-"  (named critic rubric rules)
      - "(Mechanized by", "(Enforced at", "(enforced by"

    Pre-existing rules (those numbered ≤22) are grandfathered per ADR-0008 D8
    (bootstrap-mode); they are reported in the ratio but not flagged as newly
    violating.  Only rules #23+ are flagged as unchecked-and-untagged.

    Always WARNs (never FAILs) until the wave-3 retrofit pass; per ADR-0056 D3.
    """
    claude_md = _HEALTH_REPO_ROOT / "CLAUDE.md"
    if not claude_md.exists():
        return {"id": "RULE-COVERAGE", "result": "WARN", "detail": "CLAUDE.md missing"}

    text = _read_file(claude_md)

    # Locate section 1: starts at "## 1." and ends at the next "## " heading.
    sec1_m = re.search(r'^## 1\.', text, re.MULTILINE)
    if not sec1_m:
        return {"id": "RULE-COVERAGE", "result": "WARN",
                "detail": "could not locate '## 1.' in CLAUDE.md"}
    next_h2 = re.search(r'^## [^1]', text[sec1_m.end():], re.MULTILINE)
    sec1_end = sec1_m.end() + next_h2.start() if next_h2 else len(text)
    section1 = text[sec1_m.start():sec1_end]

    # Coverage signals — one match anywhere in the rule's line-block is sufficient.
    _COVERAGE_SIGNALS = (
        "CI grep", "ci-checks", "tools/ci-checks",
        "hook validation", "pre-commit", ".claude/hooks",
        "dashboard evaluator", "health check", "trail evaluator",
        "output-contract", "trailer schema",
        "reviewer rule", "R-RULE", "(Mechanized by", "(Enforced at", "(enforced by",
    )
    # Named critic rubric patterns (R-XXX, AC-XXX, SC-XXX, PC-XXX) — minimum 2 uppercase letters
    _RUBRIC_PAT = re.compile(r'\b(R|AC|SC|PC)-[A-Z]{2,}')

    # Parse numbered rule entries.  Each entry may span multiple lines (sub-bullets).
    # Strategy: split on the rule-entry pattern and capture each block.
    rule_entry_pat = re.compile(
        r'^(?P<num>[0-9]+)\.\s+\*\*.*?rule\s+#(?P<rnum>[0-9]+)',
        re.MULTILINE,
    )

    # Collect (rule_number, full_block_text) pairs.
    matches = list(rule_entry_pat.finditer(section1))
    rules = []
    for i, m in enumerate(matches):
        block_start = m.start()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(section1)
        block = section1[block_start:block_end]
        rnum = int(m.group("rnum"))
        rules.append((rnum, block))

    total = len(rules)
    if total == 0:
        return {"id": "RULE-COVERAGE", "result": "WARN",
                "detail": "no numbered rules found in section 1"}

    covered_nums = []
    unchecked_grandfathered = []
    unchecked_new = []

    _BOOTSTRAP_CUTOFF = 22  # rules ≤22 are grandfathered per ADR-0008 D8

    for rnum, block in rules:
        is_advisory = "(advisory)" in block
        has_signal = any(sig in block for sig in _COVERAGE_SIGNALS)
        has_rubric = bool(_RUBRIC_PAT.search(block))
        covered = is_advisory or has_signal or has_rubric
        if covered:
            covered_nums.append(rnum)
        elif rnum <= _BOOTSTRAP_CUTOFF:
            unchecked_grandfathered.append(rnum)
        else:
            unchecked_new.append(rnum)

    covered_count = len(covered_nums)
    ratio_pct = int(covered_count * 100 / total)

    parts = [f"{covered_count}/{total} covered ({ratio_pct}%)"]
    if unchecked_grandfathered:
        parts.append(f"grandfathered-unchecked: {unchecked_grandfathered}")
    if unchecked_new:
        parts.append(f"NEW unchecked-untagged: {unchecked_new}")

    detail = " | ".join(str(p) for p in parts)
    # Always WARN per ADR-0056 D3 (retrofit cadence owns the FAILs)
    result = "WARN" if (unchecked_grandfathered or unchecked_new) else "PASS"
    return {"id": "RULE-COVERAGE", "result": result, "detail": detail}


# ---------------------------------------------------------------------------
# Spec-coverage check (slice #798 / ADR-0066 D2: SC-COVERAGE dashboard row)
# ---------------------------------------------------------------------------

def check_spec_coverage() -> dict:
    """SPEC-COVERAGE: per-PRD criterion coverage from Covers: §2 #n lines in slice bodies.

    Algorithm (per ADR-0066 D2):
    - For each open+closed PRD-labeled issue, parse the numbered criteria in §2.
    - Find all slice sub-issues (label: slice, body containing "PRD #<N>") and parse
      their "Covers: §2 #n[, #m]" lines.
    - Per-PRD coverage = |cited ∩ §2| / |§2|, with orphan/phantom counts.
    - PRDs with no Covers: lines on any slice (predating the convention) are placed
      in a grandfathered/no-data bucket per ADR-0004 D2 (bind-forward), NOT scored 0%.
    - API-unavailable: honest WARN rather than a silent failure.

    PASS when every post-convention PRD with ≥1 criteria has full coverage (ratio = 1.0).
    WARN when any post-convention PRD is partially covered, or when no PRDs are available.
    FAIL when any post-convention PRD has orphan criteria (criteria with no covering slice).
    """
    import json as _json
    import subprocess as _sp

    def _gh_issue_list(label: str, limit: int = 100) -> list:
        try:
            r = _sp.run(
                ["gh", "issue", "list", "--label", label,
                 "--state", "all", "--limit", str(limit),
                 "--json", "number,title,body"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
                cwd=str(_HEALTH_REPO_ROOT), stdin=_sp.DEVNULL,
            )
            if r.returncode == 0:
                return _json.loads(r.stdout)
        except Exception:
            pass
        return None  # None signals API failure; [] would mean empty list

    # --- 1. Fetch PRD issues ---
    prd_issues = _gh_issue_list("prd", limit=50)
    if prd_issues is None:
        return {"id": "SPEC-COVERAGE", "result": "WARN",
                "detail": "gh API unavailable — cannot compute coverage"}

    if not prd_issues:
        return {"id": "SPEC-COVERAGE", "result": "WARN",
                "detail": "no PRD-labeled issues found"}

    # --- 2. Fetch slice issues ---
    slice_issues = _gh_issue_list("slice", limit=200)
    if slice_issues is None:
        return {"id": "SPEC-COVERAGE", "result": "WARN",
                "detail": "gh API unavailable for slice issues"}

    # --- 3. Parse §2 criteria from each PRD ---
    _sec2_start = re.compile(r'^## 2\.', re.MULTILINE)
    _next_h2 = re.compile(r'^## [^2]', re.MULTILINE)
    _crit_num = re.compile(r'^(\d+)\.\s+\S', re.MULTILINE)

    def _parse_sec2_criteria(body: str) -> set:
        """Return the set of numbered criterion IDs from PRD §2."""
        if not body:
            return set()
        m = _sec2_start.search(body)
        if not m:
            return set()
        nh2 = _next_h2.search(body, m.end())
        end = m.end() + nh2.start() if nh2 else len(body)
        sec2 = body[m.start():end]
        return {int(n) for n in _crit_num.findall(sec2)}

    # --- 4. Build PRD → criteria map ---
    prd_criteria = {}
    for issue in prd_issues:
        n = issue["number"]
        criteria = _parse_sec2_criteria(issue.get("body") or "")
        prd_criteria[n] = criteria

    # --- 5. Build PRD → cited union from slice Covers: lines ---
    _parent_prd = re.compile(r'PRD\s+#(\d+)')
    _covers_line = re.compile(r'(?m)^Covers:\s+§2\s+(.*)')
    _covers_num = re.compile(r'#(\d+)')

    prd_cited = {n: set() for n in prd_criteria}
    prd_has_covers = {n: False for n in prd_criteria}

    for issue in slice_issues:
        body = issue.get("body") or ""
        # Find parent PRD
        pm = _parent_prd.search(body)
        if not pm:
            continue
        prd_num = int(pm.group(1))
        if prd_num not in prd_criteria:
            continue
        # Find Covers: line
        cm = _covers_line.search(body)
        if cm:
            prd_has_covers[prd_num] = True
            cited_nums = {int(x) for x in _covers_num.findall(cm.group(1))}
            prd_cited[prd_num] |= cited_nums

    # --- 6. Compute per-PRD coverage ---
    fully_covered = []
    partial = []     # (prd_num, orphans, phantoms)
    grandfathered = []

    for prd_num, criteria in prd_criteria.items():
        if not criteria:
            # PRD has no numbered §2 criteria — trivially covered
            fully_covered.append(prd_num)
            continue
        if not prd_has_covers[prd_num]:
            # No slice carries a Covers: line → grandfathered/no-data bucket
            grandfathered.append(prd_num)
            continue
        cited = prd_cited[prd_num]
        orphans = criteria - cited        # criteria with no covering slice
        phantoms = cited - criteria       # citations to nonexistent criteria
        if not orphans and not phantoms:
            fully_covered.append(prd_num)
        else:
            partial.append((prd_num, sorted(orphans), sorted(phantoms)))

    # --- 7. Build summary detail ---
    total_post_conv = len(fully_covered) + len(partial)
    parts = []
    if total_post_conv == 0 and grandfathered:
        parts.append(
            f"all {len(grandfathered)} PRDs grandfathered (no Covers: lines yet)"
        )
    else:
        parts.append(f"{len(fully_covered)}/{total_post_conv} fully covered")
    if partial:
        gap_descs = []
        for prd_num, orphans, phantoms in partial:
            desc = f"PRD#{prd_num}"
            if orphans:
                desc += f" orphans={orphans}"
            if phantoms:
                desc += f" phantoms={phantoms}"
            gap_descs.append(desc)
        parts.append("gaps: " + "; ".join(gap_descs))
    if grandfathered:
        parts.append(f"grandfathered (pre-convention): {sorted(grandfathered)}")

    detail = " | ".join(parts)

    if partial:
        result = "FAIL"
    elif total_post_conv == 0:
        result = "WARN"
    else:
        result = "PASS"

    return {
        "id": "SPEC-COVERAGE",
        "result": result,
        "detail": detail,
        "fully_covered": sorted(fully_covered),
        "partial": partial,
        "grandfathered": sorted(grandfathered),
    }


# ---------------------------------------------------------------------------
# Critic-health check (slice #779 / ADR-0059 D1 / ADR-0060 D4)
# ---------------------------------------------------------------------------

# Doubt-theater streak threshold: N consecutive first-round APPROVEs triggers amber badge.
# Documented here per slice #779 acceptance-criterion and PRD #778 §5 open question.
_DOUBT_THEATER_N = 10

# Window: last N closed PRDs whose trails are scanned for critic verdicts.
_CRITIC_HEALTH_PRD_WINDOW = 10


def check_critic_health() -> dict:
    """CRITIC-HEALTH: per-critic first-pass APPROVE rate + rounds histogram + doubt-theater streak.

    Reuses the collector's existing gh-fetch/caching seam (get_trail + get_closed_prd_numbers)
    to scan the last _CRITIC_HEALTH_PRD_WINDOW closed PRDs' comment trails.

    Per-critic metrics:
      - first_pass_approve_rate: fraction of final-APPROVE runs where round==1
      - rounds_histogram: {1: N, 2: N, ...} — max_round for each reviewed PR
      - doubt_theater_streak: consecutive first-round APPROVEs at the tail of the
        chronological verdict list (amber >= _DOUBT_THEATER_N, never auto-acted on)

    Pre-v2 verdicts (no CRITIC: field) → "unattributed" bucket.
    Honest design: with no merged post-v2 PRs yet, the unattributed bucket will
    hold all verdicts and named critics will show 0 verdicts — that is correct.

    Returns a substrate-compatible check dict with id="CRITIC-HEALTH" and a
    per-critic breakdown in the "critics" key for the dashboard card.
    """
    try:
        # Lazy import to avoid circular deps (collector imports nothing from health)
        _insert_dashboard_sys_path()
        from collector import get_closed_prd_numbers, get_trail  # noqa: PLC0415
        from collector import parse_critic_field  # noqa: PLC0415 (re-export)
    except Exception as exc:
        return {
            "id": "CRITIC-HEALTH",
            "result": "WARN",
            "detail": f"collector import failed: {exc}",
            "critics": {},
        }

    prd_numbers = get_closed_prd_numbers(_CRITIC_HEALTH_PRD_WINDOW)
    if not prd_numbers:
        return {
            "id": "CRITIC-HEALTH",
            "result": "WARN",
            "detail": "no closed PRDs found; trail empty",
            "critics": {},
        }

    # Collect all verdict records across the window.
    # Each record: {"critic": str|None, "verdict": "APPROVE"|"BLOCK",
    #               "round": int|None, "created_at": str}
    all_verdicts: list[dict] = []
    auth_dead = False

    for prd_num in prd_numbers:
        trail = get_trail(prd_num)
        if trail.get("collector_status") == "auth_dead":
            auth_dead = True
            continue
        for pr_trail in trail.get("prs", {}).values():
            for v in pr_trail.get("verdicts", []):
                all_verdicts.append(v)
        # Also include PRD-level verdicts (prd-critic, adr-critic rounds)
        for v in trail.get("prd_verdicts", []):
            all_verdicts.append(v)

    if not all_verdicts:
        detail = (
            f"0 verdicts across last {len(prd_numbers)} PRDs "
            f"(auth_dead={auth_dead}); pre-v2 history fully unattributed — expected"
        )
        return {
            "id": "CRITIC-HEALTH",
            "result": "PASS",
            "detail": detail,
            "critics": {"unattributed": {"verdict_count": 0, "first_pass_approve_rate": None,
                                          "rounds_histogram": {}, "doubt_theater_streak": 0}},
        }

    # Group verdicts by critic (None → "unattributed")
    # Per-PR "runs": group by a (prd, pr) key to compute max-round per PR.
    # We don't have that granularity in the flat list, so we approximate:
    # treat each sequence of verdicts per (prd, pr) as one run.
    # In the flat list we have them; just attribute each verdict individually.

    from collections import defaultdict  # noqa: PLC0415
    critic_verdicts: dict[str, list[dict]] = defaultdict(list)
    for v in all_verdicts:
        name = v.get("critic") or "unattributed"
        critic_verdicts[name].append(v)

    critics_out: dict[str, dict] = {}
    for name, verdicts in sorted(critic_verdicts.items()):
        total = len(verdicts)
        # First-pass APPROVE rate: fraction where round==1 and verdict==APPROVE
        r1_approves = sum(
            1 for v in verdicts
            if v.get("verdict") == "APPROVE" and v.get("round") == 1
        )
        # Final verdicts per run proxy: any APPROVE at any round
        approves = sum(1 for v in verdicts if v.get("verdict") == "APPROVE")
        first_pass_rate = round(r1_approves / total, 3) if total > 0 else None

        # Rounds histogram: {round_num: count}
        hist: dict[str, int] = {}
        for v in verdicts:
            r = v.get("round")
            key = str(r) if r is not None else "unknown"
            hist[key] = hist.get(key, 0) + 1

        # Doubt-theater streak: consecutive first-round APPROVEs at tail
        # (most recent last in the list, since they're in insertion order)
        streak = 0
        for v in reversed(verdicts):
            if v.get("verdict") == "APPROVE" and v.get("round") == 1:
                streak += 1
            else:
                break

        critics_out[name] = {
            "verdict_count": total,
            "approve_count": approves,
            "first_pass_approve_rate": first_pass_rate,
            "rounds_histogram": hist,
            "doubt_theater_streak": streak,
            "doubt_theater_amber": streak >= _DOUBT_THEATER_N,
        }

    # Overall result: PASS unless auth_dead or data quality issues
    result = "WARN" if auth_dead else "PASS"
    total_verdicts = len(all_verdicts)
    unattr = len(critic_verdicts.get("unattributed", []))
    named = total_verdicts - unattr
    detail = (
        f"{total_verdicts} verdicts across last {len(prd_numbers)} PRDs "
        f"({named} attributed, {unattr} unattributed); "
        f"doubt-theater threshold N={_DOUBT_THEATER_N}"
    )
    if auth_dead:
        detail += " | WARNING: some PRDs skipped (auth_dead)"

    return {
        "id": "CRITIC-HEALTH",
        "result": result,
        "detail": detail,
        "critics": critics_out,
    }


# ---------------------------------------------------------------------------
# Verification-integrity evaluators (slice #783 / ADR-0060/0061/0062/0063)
# ---------------------------------------------------------------------------

# ADR-0061 D1 route-table glob classes (changed-path → mandatory proof class).
# Used by check_proof_presence to classify PRs by their changed paths.
_ROUTE_TABLE = [
    # (glob_pattern, proof_class)
    ("dashboard/**", "browser"),
    ("*.html", "browser"),
    (".claude/hooks/**", "hook-fire"),
    (".claude/settings.json", "hook-fire"),
    ("tools/**", "command-run"),
    (".claude/skills/**", "command-run"),
    (".github/workflows/**", "command-run"),
    ("decisions/**", "static"),
    ("docs/**", "static"),
    ("*.md", "static"),
    ("CLAUDE.md", "static"),
    ("bootstrap.sh", "static"),
]

# Proof tokens per route class (ADR-0061 D1 / rule #20).
# These regexes are searched over the PR body + comment trail.
_PROOF_TOKENS: dict[str, list[str]] = {
    "browser":      [r'\.png\b', r'inner_text:', r'screenshot'],
    "hook-fire":    [r'exit=', r'hook-fire', r'HOOK-FIRE'],
    "command-run":  [r'exit=', r'exit code', r'exit\s*0'],
    "static":       [r'grep count=', r'grep -c', r'grep\s+\d+', r'count=\d'],
}

# Window for proof-presence: last N merged non-trivial PRs.
_PROOF_PRESENCE_WINDOW = 10

# Bootstrap cutoff for proof-presence: PRs before this are grandfathered.
# Bind-forward per ADR-0004 D2 — slice #783 is the implementing merge.
_PROOF_PRESENCE_BOOTSTRAP_PR = 788   # last merged PR before this slice


def _classify_route(changed_files: list[str]) -> set[str]:
    """Return the union of proof classes from changed-path globs (ADR-0061 D1)."""
    import fnmatch
    classes: set[str] = set()
    for f in changed_files:
        for pattern, cls in _ROUTE_TABLE:
            if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(f.split("/")[-1], pattern):
                classes.add(cls)
                break
    return classes


def _pr_has_proof_token(pr_body: str, comments: list[str], route_classes: set[str]) -> bool:
    """Return True if ANY comment or pr_body contains a proof token for ANY route class."""
    search_text = " ".join([pr_body] + comments)
    for cls in route_classes:
        tokens = _PROOF_TOKENS.get(cls, [])
        for tok in tokens:
            if re.search(tok, search_text, re.IGNORECASE):
                return True
    return False


def check_blind_dispatch_rate() -> dict:
    """BLIND-RATE: fraction of critic dispatches with ^BLIND-REVIEW prefix.

    Reads workflow-events.jsonl for agent_start events whose input begins with
    'BLIND-REVIEW'. Pre-migration denominator is honest: all agent_start events
    with a non-empty input are counted. Bind-forward per ADR-0060 D5 — pre-merge
    dispatches are grandfathered.

    Returns {"id": "BLIND-RATE", "result": ..., "detail": ...,
             "blind": N, "total": N, "rate": float}
    """
    import json as _json
    events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    if not events_log.exists():
        return {"id": "BLIND-RATE", "result": "WARN",
                "detail": "workflow-events.jsonl not found", "blind": 0, "total": 0, "rate": None}

    blind = 0
    total = 0
    try:
        with events_log.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = _json.loads(raw)
                except Exception:
                    continue
                if obj.get("event") != "agent_start":
                    continue
                inp = obj.get("input", "") or ""
                if not inp:
                    continue
                total += 1
                if inp.startswith("BLIND-REVIEW"):
                    blind += 1
    except Exception as exc:
        return {"id": "BLIND-RATE", "result": "WARN",
                "detail": f"read error: {exc}", "blind": 0, "total": 0, "rate": None}

    if total == 0:
        return {"id": "BLIND-RATE", "result": "WARN",
                "detail": "no agent_start events with input found (pre-migration — expected)",
                "blind": 0, "total": 0, "rate": None}

    rate = round(blind / total, 3)
    detail = (
        f"{blind}/{total} dispatches carry BLIND-REVIEW prefix "
        f"({rate*100:.0f}%) — pre-migration denominator; bind-forward ADR-0060 D5"
    )
    result = "PASS" if rate >= 1.0 else "WARN"
    return {"id": "BLIND-RATE", "result": result, "detail": detail,
            "blind": blind, "total": total, "rate": rate}


# Minimum QA-plan rows required before ratio is meaningful (honest guard).
# Rationale: a ratio from 1-2 rows (e.g. one plan with 2 criteria total) has
# +-50% sampling noise; the ADR-0066 D1 drop-criterion requires a stable signal.
# 5 rows chosen as a pragmatic floor: below this the check emits WARN/low-sample
# and reports the actual counts without a ratio verdict.
_RESIDUAL_RATIO_MIN_ROWS = 5

# Limit on closed PRDs scanned for QA-plan tables -- avoids excessive gh API calls.
_RESIDUAL_RATIO_PRD_WINDOW = 20


def check_residual_ratio() -> dict:
    """RESIDUAL-RATIO: (JUDGMENT + EXTRACT_FAILED) / total rows across QA-plan tables.

    Reads closed PRD issue comments for '## QA-plan' headings (the qa-plan
    skill persists its plan as a PRD comment per ADR-0020 D4).  Within each
    QA-plan table, scans the second column (the check column) for the literal
    strings 'JUDGMENT' and 'EXTRACT_FAILED'.

    Measurement per ADR-0066 D1 drop-criterion: if the ratio does not fall after
    PC-EARS adoption (this slice's merge), the rule is theater and should be
    dropped.  Bind-forward: only criteria authored post-merge are expected to be
    EARS-shaped; pre-merge plans are honestly included in the denominator.

    Minimum-sample guard: fewer than _RESIDUAL_RATIO_MIN_ROWS total criteria rows
    across all scanned plans -> WARN with 'low-sample' label and raw counts instead
    of a ratio.  This avoids a misleading 0%% or 100%% ratio from 1-2 data points.

    Returns {"id": "RESIDUAL-RATIO", "result": ..., "detail": ...,
             "judgment": N, "extract_failed": N, "total": N, "rate": float|None}
    """
    import json as _json
    import subprocess as _sp

    def _fetch_closed_prds(limit):
        try:
            r = _sp.run(
                ["gh", "issue", "list", "--label", "prd",
                 "--state", "closed", "--limit", str(limit),
                 "--json", "number"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
                cwd=str(_HEALTH_REPO_ROOT), stdin=_sp.DEVNULL,
            )
            if r.returncode == 0:
                return [item["number"] for item in _json.loads(r.stdout)]
        except Exception:
            pass
        return []

    def _fetch_comments(prd_num):
        try:
            r = _sp.run(
                ["gh", "issue", "view", str(prd_num),
                 "--json", "comments"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
                cwd=str(_HEALTH_REPO_ROOT), stdin=_sp.DEVNULL,
            )
            if r.returncode == 0:
                data = _json.loads(r.stdout)
                return [c.get("body", "") for c in data.get("comments", [])]
        except Exception:
            pass
        return []

    # Separator rows like "|---|---|" -- skip these
    _separator_re = re.compile(r'^\|\s*[-:]+\s*\|')

    judgment = 0
    extract_failed = 0
    total = 0
    prds_scanned = 0
    fetch_error = None

    prd_numbers = _fetch_closed_prds(_RESIDUAL_RATIO_PRD_WINDOW)
    if not prd_numbers:
        return {
            "id": "RESIDUAL-RATIO",
            "result": "WARN",
            "detail": (
                "no closed PRDs found -- cannot compute ratio; "
                "bind-forward ADR-0066 D1: ratio expected to fall after PC-EARS adoption"
            ),
            "judgment": 0, "extract_failed": 0, "total": 0, "rate": None,
        }

    for prd_num in prd_numbers:
        comments = _fetch_comments(prd_num)
        if not comments and fetch_error is None:
            fetch_error = "comment fetch failed for PRD #{} (auth or timeout)".format(prd_num)
        prd_has_plan = False
        for body in comments:
            if "## QA-plan" not in body:
                continue
            prd_has_plan = True
            # Parse the table rows within this comment.
            # Table format: | col1 | col2 | col3 |
            # Split on "|" gives: ["", col1, col2, col3, ""]
            # The second column (index 2) is the check/judgment column.
            for line in body.splitlines():
                if not line.startswith("|"):
                    continue
                if _separator_re.match(line):
                    continue
                # Skip the header row
                if "criterion #" in line.lower() or "bash check" in line.lower():
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 4:
                    continue
                check_col = parts[2]
                if not check_col:
                    continue
                total += 1
                if "EXTRACT_FAILED" in check_col:
                    extract_failed += 1
                elif "JUDGMENT" in check_col:
                    judgment += 1
        if prd_has_plan:
            prds_scanned += 1

    if total < _RESIDUAL_RATIO_MIN_ROWS:
        detail = (
            "low-sample: {} criteria rows across {} PRDs with QA-plans "
            "(min={}); judgment={}, extract_failed={}; "
            "ratio not computed -- insufficient data for ADR-0066 D1 drop-criterion signal"
        ).format(total, prds_scanned, _RESIDUAL_RATIO_MIN_ROWS, judgment, extract_failed)
        if fetch_error:
            detail += " | note: {}".format(fetch_error)
        return {
            "id": "RESIDUAL-RATIO",
            "result": "WARN",
            "detail": detail,
            "judgment": judgment, "extract_failed": extract_failed,
            "total": total, "rate": None,
        }

    residual = judgment + extract_failed
    rate = round(residual / total, 3) if total > 0 else None
    rate_pct = "{:.0f}%".format(rate * 100) if rate is not None else "?"
    detail = (
        "{}/{} residual rows ({}) "
        "[judgment={}, extract_failed={}] "
        "across {} PRDs with QA-plans "
        "(bind-forward ADR-0066 D1: ratio should fall after PC-EARS adoption)"
    ).format(residual, total, rate_pct, judgment, extract_failed, prds_scanned)
    if fetch_error:
        detail += " | note: {}".format(fetch_error)

    # WARN always (not FAIL) -- this is a measurement row, not a blocking check.
    # The drop-criterion is a human-reviewed decision, not an automated gate.
    result = "PASS" if rate is not None and rate < 0.30 else "WARN"
    return {
        "id": "RESIDUAL-RATIO",
        "result": result,
        "detail": detail,
        "judgment": judgment, "extract_failed": extract_failed,
        "total": total, "rate": rate,
    }


def check_proof_presence() -> dict:
    """PROOF-PRESENCE: per merged non-trivial PR: route + proof-token presence.

    Classifies each PR's changed files via ADR-0061 D1 route table; greps the
    PR body + comment trail for route-appropriate proof tokens. Computes per-PR
    and rolling rate. Grandfathers PRs <= _PROOF_PRESENCE_BOOTSTRAP_PR.

    Reuses collector's fetch caching (get_trail + get_recent_merged_prs).
    """
    try:
        _insert_dashboard_sys_path()
        from collector import get_recent_merged_prs  # noqa: PLC0415
        from collector import _run_gh  # noqa: PLC0415
    except Exception as exc:
        return {"id": "PROOF-PRESENCE", "result": "WARN",
                "detail": f"collector import failed: {exc}", "rate": None, "window": 0}

    import json as _json

    prs = get_recent_merged_prs(limit=_PROOF_PRESENCE_WINDOW + 5)
    # Filter trivial-lane PRs (heuristic: trivial in headRef or body)
    non_trivial = []
    for pr in prs:
        ref = pr.get("headRefName", "")
        labels = [lb.get("name", "") for lb in (pr.get("labels") or [])]
        if "trivial" in labels or ref.startswith("hotfix/"):
            continue
        if pr.get("number", 0) > _PROOF_PRESENCE_BOOTSTRAP_PR:
            non_trivial.append(pr)
        if len(non_trivial) >= _PROOF_PRESENCE_WINDOW:
            break

    if not non_trivial:
        return {"id": "PROOF-PRESENCE", "result": "WARN",
                "detail": f"no non-trivial merged PRs found above bootstrap threshold #{_PROOF_PRESENCE_BOOTSTRAP_PR}",
                "rate": None, "window": 0}

    with_proof = 0
    without_proof = []
    for pr in non_trivial:
        pr_num = pr.get("number", 0)
        # Fetch changed files
        stdout, _ = _run_gh(["pr", "view", str(pr_num), "--json",
                              "files,body,comments"], timeout=20)
        if stdout is None:
            # Cannot verify — count as present (honest: missing data != missing proof)
            with_proof += 1
            continue
        try:
            pr_data = _json.loads(stdout)
        except Exception:
            with_proof += 1
            continue
        changed_files = [f.get("path", "") for f in (pr_data.get("files") or [])]
        route_classes = _classify_route(changed_files)
        if not route_classes:
            # No recognized route → unclassifiable; skip (not a violation)
            with_proof += 1
            continue
        pr_body = pr_data.get("body", "") or ""
        comments = [c.get("body", "") for c in (pr_data.get("comments") or [])]
        has_proof = _pr_has_proof_token(pr_body, comments, route_classes)
        if has_proof:
            with_proof += 1
        else:
            without_proof.append(str(pr_num))

    total = len(non_trivial)
    rate = round(with_proof / total, 3) if total > 0 else None
    missing_str = ", ".join(without_proof) if without_proof else "none"
    detail = (
        f"{with_proof}/{total} non-trivial PRs have route-appropriate proof tokens "
        f"(bind-forward >#{ _PROOF_PRESENCE_BOOTSTRAP_PR}); missing: {missing_str}"
    )
    result = "PASS" if not without_proof else "WARN"
    return {"id": "PROOF-PRESENCE", "result": result, "detail": detail,
            "rate": rate, "window": total, "missing_prs": without_proof}


def check_merge_integrity() -> dict:
    """MERGE-INTEGRITY: BEHIND-encountered/recovered counters from PR comment trails.

    Scans the PR comment trails of recent closed PRDs for MERGE_STATUS lines
    containing 'behind-retried' (ADR-0062 D1). Honest zero when no data exists yet.
    """
    try:
        _insert_dashboard_sys_path()
        from collector import get_closed_prd_numbers, get_trail  # noqa: PLC0415
    except Exception as exc:
        return {"id": "MERGE-INTEGRITY", "result": "WARN",
                "detail": f"collector import failed: {exc}", "behind_total": 0}

    prd_numbers = get_closed_prd_numbers(10)
    behind_total = 0
    auth_dead = False
    _behind_re = re.compile(r'behind-retried:\s*(\d+)', re.IGNORECASE)

    for prd_num in prd_numbers:
        trail = get_trail(prd_num)
        if trail.get("collector_status") == "auth_dead":
            auth_dead = True
            continue
        for pr_trail in trail.get("prs", {}).values():
            for verdict in pr_trail.get("verdicts", []):
                # verdicts are parsed from comments; check raw too via any body field
                pass
            # Scan raw PR body excerpt for MERGE_STATUS
            body_exc = pr_trail.get("body_excerpt", "") or ""
            for m in _behind_re.finditer(body_exc):
                behind_total += int(m.group(1))
            for verdict in pr_trail.get("verdicts", []):
                # Verdicts don't carry raw body; best-effort via body_excerpt only
                pass

    detail = (
        f"behind-retried total: {behind_total} "
        f"(from last 10 closed PRDs; honest 0 if no BEHIND races recorded)"
    )
    if auth_dead:
        detail += " | WARNING: some PRDs skipped (auth_dead)"
    result = "WARN" if auth_dead else "PASS"
    return {"id": "MERGE-INTEGRITY", "result": result, "detail": detail,
            "behind_total": behind_total}


def check_capture_shape() -> dict:
    """CAPTURE-SHAPE: shape-conforming fraction of root-cause-labeled issue bodies.

    Checks:
    1. Fraction with all 3 headings: **Symptom:** / **Root cause:** / **Proposed:**
    2. Evidence-presence sub-metric: fraction of conforming issues with a fenced/quoted
       verbatim block in the Symptom section.
    3. Counter of 3-section-shaped captured issues missing the root-cause label
       (surfaced only, never auto-relabeled).

    Per ADR-0063 D1/D2/D3. Bind-forward: pre-ADR-0063 issues grandfathered.
    """
    import json as _json
    import subprocess as _sp

    _heading_re = re.compile(
        r'\*\*Symptom:\*\*.*?\*\*Root cause:\*\*.*?\*\*Proposed:\*\*',
        re.DOTALL,
    )
    _evidence_re = re.compile(r'```|\> ', re.MULTILINE)
    _symptom_block_re = re.compile(
        r'\*\*Symptom:\*\*(.*?)(?=\*\*Root cause:\*\*)', re.DOTALL
    )

    def _fetch_issues(label: str) -> list[dict]:
        try:
            result = _sp.run(
                ["gh", "issue", "list", "--label", label,
                 "--state", "all", "--limit", "50",
                 "--json", "number,body,labels"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
                cwd=str(_HEALTH_REPO_ROOT), stdin=_sp.DEVNULL,
            )
            if result.returncode == 0:
                return _json.loads(result.stdout)
        except Exception:
            pass
        return []

    # Step 1: Check root-cause labeled issues
    root_cause_issues = _fetch_issues("root-cause")
    total_rc = len(root_cause_issues)
    conforming = []
    non_conformers = []
    evidence_present = 0

    for issue in root_cause_issues:
        body = issue.get("body", "") or ""
        num = issue.get("number")
        if _heading_re.search(body):
            conforming.append(num)
            # Check evidence in Symptom section
            sym_m = _symptom_block_re.search(body)
            if sym_m and _evidence_re.search(sym_m.group(1)):
                evidence_present += 1
        else:
            non_conformers.append(num)

    conf_rate = round(len(conforming) / total_rc, 3) if total_rc > 0 else None
    evid_rate = round(evidence_present / len(conforming), 3) if conforming else None

    # Step 2: Unlabeled-candidate counter (captured issues with 3-section shape)
    captured_issues = _fetch_issues("captured")
    unlabeled_candidates = []
    rc_numbers = {i["number"] for i in root_cause_issues}
    for issue in captured_issues:
        if issue["number"] in rc_numbers:
            continue
        body = issue.get("body", "") or ""
        if _heading_re.search(body):
            unlabeled_candidates.append(issue["number"])

    parts = []
    if total_rc == 0:
        parts.append("no root-cause-labeled issues found (bind-forward ADR-0063 D1)")
    else:
        parts.append(f"{len(conforming)}/{total_rc} conforming ({conf_rate*100:.0f}%)")
        if non_conformers:
            parts.append(f"non-conformers: #{', #'.join(str(n) for n in non_conformers)}")
        evid_str = f"{evidence_present}/{len(conforming)}" if conforming else "0/0"
        evid_pct = f" ({evid_rate*100:.0f}%)" if evid_rate is not None else ""
        parts.append(f"evidence-presence: {evid_str}{evid_pct}")
    if unlabeled_candidates:
        parts.append(f"unlabeled-candidates (surfaced only): #{', #'.join(str(n) for n in unlabeled_candidates)}")

    result = "PASS" if (not non_conformers and total_rc > 0) else "WARN"
    return {
        "id": "CAPTURE-SHAPE",
        "result": result,
        "detail": " | ".join(parts),
        "total_root_cause": total_rc,
        "conforming_count": len(conforming),
        "evidence_count": evidence_present,
        "non_conformers": non_conformers,
        "unlabeled_candidates": unlabeled_candidates,
    }


def check_green_main() -> dict:
    """GREEN-MAIN: last main_green event sha + lag vs origin/main + age.

    Reads workflow-events.jsonl for the last 'main_green' event (ADR-0062 D3).
    lag = git rev-list <sha>..origin/main --count
    age = seconds since the event timestamp
    Red on lag > 0 or stale > 24h.
    """
    import json as _json
    events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    if not events_log.exists():
        return {"id": "GREEN-MAIN", "result": "WARN",
                "detail": "workflow-events.jsonl not found; no main_green events yet"}

    last_green: dict | None = None
    try:
        with events_log.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = _json.loads(raw)
                except Exception:
                    continue
                if obj.get("event") == "main_green":
                    last_green = obj
    except Exception as exc:
        return {"id": "GREEN-MAIN", "result": "WARN",
                "detail": f"read error: {exc}"}

    if last_green is None:
        return {"id": "GREEN-MAIN", "result": "WARN",
                "detail": "no main_green events found in workflow-events.jsonl"}

    sha = last_green.get("sha", "")
    ts_str = last_green.get("ts", "")

    # Compute lag: commits on origin/main since the green sha
    lag = -1
    try:
        r = subprocess.run(
            ["git", "rev-list", "--count", f"{sha}..origin/main"],
            capture_output=True, text=True, timeout=10, cwd=str(_HEALTH_REPO_ROOT),
        )
        if r.returncode == 0:
            lag = int(r.stdout.strip())
    except Exception:
        pass

    # Compute age in hours
    age_h: float | None = None
    try:
        from datetime import datetime, timezone
        ts = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc)
        age_h = round((now - dt).total_seconds() / 3600, 1)
    except Exception:
        pass

    sha_short = sha[:8] if sha else "?"
    age_str = f"{age_h}h ago" if age_h is not None else "age unknown"
    lag_str = str(lag) if lag >= 0 else "?"

    if lag > 0:
        result = "FAIL"
        detail = f"GREEN-MAIN lag={lag} commits behind; last green sha={sha_short} ({age_str})"
    elif age_h is not None and age_h > 24:
        result = "WARN"
        detail = f"GREEN-MAIN stale ({age_str}); lag=0; sha={sha_short}"
    else:
        result = "PASS"
        detail = f"sha={sha_short} lag=0 ({age_str})"

    return {"id": "GREEN-MAIN", "result": result, "detail": detail,
            "sha": sha, "lag": lag, "age_hours": age_h}


def check_silent_drift() -> dict:
    """SILENT-DRIFT: count PRDs whose body changed post-first-dispatch without an AMENDMENT comment.

    Algorithm (ADR-0066 D3):
    1. Fetch closed + open PRDs (label=prd) via gh issue list.
    2. For each PRD, determine whether a first implementer dispatch has occurred:
       look for the earliest PR comment whose body contains 'implementer' or
       check for any sub-issue (slice) with a closed PR linked via 'Closes #'.
       Heuristic: a PRD is "first-dispatched" when it has ≥1 slice-labeled sub-issue.
    3. For each first-dispatched PRD, check GitHub edit history via
       gh api repos/{owner}/{repo}/issues/{n} (the `updated_at` vs `created_at`
       difference is a proxy; authoritative edit history requires
       gh api /repos/{owner}/{repo}/issues/{n}/timeline which may need extra auth).
    4. Count PRDs where body may have drifted without a matching ## AMENDMENT comment.

    Honest grandfathering (ADR-0004 D2): PRDs created before this check's merge
    (first-merge commit of feat/799-amendment-protocol) cannot be retroactively
    audited — they land in a 'grandfathered' bucket and are excluded from the
    violation count.

    API availability note: GitHub's issue edit history endpoint
    (GET /repos/{owner}/{repo}/issues/{n}/timeline, event='edited') requires
    the `application/vnd.github+json` Accept header and returns edit events only
    when the edit occurred after the PR/issue was indexed. Rate limits and auth
    scope (requires `issues` scope) may block this. Graceful WARN fallback when
    the API is unavailable or rate-limited — the row will show WARN with a
    documented fallback rather than fabricating a value.

    Target: 0 violations (PASS). Any violations: WARN with count + PRD numbers.
    Grandfathered PRDs: always excluded (honest per bootstrap-mode ADR-0004 D2).
    """
    import json as _json
    import subprocess as _sp

    # --- Bootstrap cutoff: the merge commit of feat/799-amendment-protocol ---
    # PRDs created before this slice's merge cannot be audited via edit history
    # (the protocol binds forward from this merge per ADR-0066 D3 + ADR-0004 D2).
    # We use the slice issue number (799) as a proxy: PRDs with issue number < 799
    # are grandfathered. This is approximate but honest and conservative.
    _GRANDFATHERED_BELOW = 799

    def _gh_json(args: list, timeout: int = 20) -> list | dict | None:
        try:
            r = _sp.run(
                ["gh"] + args,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout,
                cwd=str(_HEALTH_REPO_ROOT), stdin=_sp.DEVNULL,
            )
            if r.returncode != 0:
                return None
            return _json.loads(r.stdout)
        except Exception:
            return None

    # --- Step 1: fetch PRDs ---
    prd_issues = _gh_json([
        "issue", "list", "--label", "prd",
        "--state", "all", "--limit", "50",
        "--json", "number,body,createdAt,updatedAt,comments",
    ])
    if prd_issues is None:
        return {
            "id": "SILENT-DRIFT",
            "result": "WARN",
            "detail": (
                "GitHub API unavailable (auth or rate-limit); "
                "edit-history check skipped. "
                "Fallback: run `gh issue list --label prd` manually and inspect "
                "body edit dates against AMENDMENT comments. "
                "Per ADR-0066 D3 honest-fallback design."
            ),
            "violations": 0,
            "grandfathered": 0,
            "api_available": False,
        }

    violations = []
    grandfathered = []
    auditable_prd_count = 0

    for prd in prd_issues:
        prd_num = prd.get("number", 0)
        created_at = prd.get("createdAt", "")
        updated_at = prd.get("updatedAt", "")
        comments = prd.get("comments", []) or []

        # Grandfathering: PRDs with number < bootstrap cutoff
        if prd_num < _GRANDFATHERED_BELOW:
            grandfathered.append(prd_num)
            continue

        # Check if PRD has been first-dispatched:
        # proxy = has any slice sub-issue (implementer dispatch creates at least 1 slice)
        # We check via sub-issues by looking for slice-labeled issues mentioning this PRD.
        # Simpler heuristic: if updatedAt != createdAt the body MAY have been edited.
        if created_at == updated_at:
            # No updates at all — cannot have drifted
            continue

        auditable_prd_count += 1

        # Check for AMENDMENT comments
        amendment_count = sum(
            1 for c in comments
            if (c.get("body") or "").strip().startswith("## AMENDMENT")
        )

        # Try to get edit history via timeline API
        timeline = _gh_json([
            "api", f"repos/{{owner}}/{{repo}}/issues/{prd_num}/timeline",
            "--paginate", "--jq", "[.[] | select(.event==\"edited\")]",
        ], timeout=15)

        if timeline is None:
            # API unavailable for this PRD — use updatedAt proxy
            # Conservative: if body may have been edited (updated_at != created_at)
            # and no AMENDMENT comment exists, flag as potential violation
            # but only WARN, never fabricate
            if amendment_count == 0:
                violations.append({
                    "prd": prd_num,
                    "reason": "body updated post-creation; no AMENDMENT comment; edit-history API unavailable (proxy only)",
                })
            continue

        # Timeline available — check for 'edited' events after first dispatch
        edit_events = timeline if isinstance(timeline, list) else []
        if edit_events and amendment_count == 0:
            violations.append({
                "prd": prd_num,
                "reason": f"{len(edit_events)} body edit event(s) detected; 0 AMENDMENT comments",
            })

    violation_nums = [v["prd"] for v in violations]
    gran_count = len(grandfathered)

    if not violations:
        detail = (
            f"0 violations ({auditable_prd_count} auditable post-bootstrap PRDs; "
            f"{gran_count} grandfathered pre-#{_GRANDFATHERED_BELOW})"
        )
        result = "PASS"
    else:
        viol_str = ", ".join(f"#{n}" for n in violation_nums)
        detail = (
            f"{len(violations)} violation(s): {viol_str} — "
            f"body updated without AMENDMENT comment "
            f"({auditable_prd_count} auditable; {gran_count} grandfathered pre-#{_GRANDFATHERED_BELOW})"
        )
        result = "WARN"

    return {
        "id": "SILENT-DRIFT",
        "result": result,
        "detail": detail,
        "violations": len(violations),
        "violation_prds": violation_nums,
        "grandfathered": gran_count,
        "api_available": True,
    }


# ---------------------------------------------------------------------------
# TESTS-COLLECTED — regression suite collected-count row (ADR-0067 D1)
# ---------------------------------------------------------------------------


def check_tests_collected() -> dict:
    """TESTS-COLLECTED: count of pytest-collected test items in tests/.

    Implements ADR-0067 D1 — the founding memory row: reports how many tests
    are collected in the tests/ suite. PASS when count > 0 (the suite exists
    and is non-empty). FAIL when tests/ exists but no tests are collected.
    WARN when tests/ does not exist or pytest is unavailable.

    Uses 'pytest --collect-only -q' which is fast (no test execution).
    Bind-forward per ADR-0004 D2: pre-suite repos honestly report WARN.
    """
    tests_dir = _HEALTH_REPO_ROOT / "tests"
    if not tests_dir.exists():
        return {
            "id": "TESTS-COLLECTED",
            "result": "WARN",
            "detail": "tests/ directory does not exist (pre-suite: bind-forward ADR-0067 D1)",
        }

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir),
             "--collect-only", "-q", "--no-header"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_HEALTH_REPO_ROOT),
        )
    except FileNotFoundError:
        return {
            "id": "TESTS-COLLECTED",
            "result": "WARN",
            "detail": "pytest not available; install pytest or use stdlib unittest",
        }
    except Exception as exc:
        return {
            "id": "TESTS-COLLECTED",
            "result": "WARN",
            "detail": f"pytest collect-only failed: {exc}",
        }

    # Parse collected count from pytest output.
    # pytest --collect-only -q emits lines like "<path>::<class>::<method>"
    # followed by a summary "N tests" or "no tests ran".
    output = (result.stdout or "") + (result.stderr or "")

    # Count lines that look like collected test IDs (contain "::")
    # This is more reliable than parsing the summary line.
    collected_lines = [
        line for line in output.splitlines()
        if "::" in line and not line.startswith("=") and not line.startswith("-")
    ]
    count = len(collected_lines)

    if count == 0:
        # Try parsing the summary line as a fallback
        import re as _re
        m = _re.search(r'(\d+)\s+(?:test|item)', output)
        if m:
            count = int(m.group(1))

    if count > 0:
        return {
            "id": "TESTS-COLLECTED",
            "result": "PASS",
            "detail": f"{count} test(s) collected in tests/ (ADR-0067 D1 founding memory row)",
            "count": count,
        }
    else:
        return {
            "id": "TESTS-COLLECTED",
            "result": "FAIL",
            "detail": (
                "tests/ exists but 0 tests collected — "
                "suite must stay non-empty per ADR-0067 D1"
            ),
            "count": 0,
        }


def _insert_dashboard_sys_path() -> None:
    """Ensure dashboard/ is on sys.path for sibling imports."""
    dashboard_dir = str(Path(__file__).resolve().parent)
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)


# ---------------------------------------------------------------------------
# Check registry (ADR-0064 D3) — single source of truth for all DOCS-* checks.
#
# Maps check-id string → zero-argument callable returning a dict with at
# minimum {"id": str, "result": "PASS"|"FAIL"|"WARN", "detail": str}.
#
# CLI usage (headless, per ADR-0064 D3):
#   python dashboard/health.py --check <id>   → run one check, print JSON
#   python dashboard/health.py --list          → print registered IDs, one per line
#
# Exit codes:
#   0 — check ran; result is PASS or WARN (non-blocking)
#   1 — check ran; result is FAIL (blocking)
#   2 — unknown check ID or bad arguments
#
# CI consumers (tools/ci-checks.sh) use:
#   python3 dashboard/health.py --check DOCS-7   → replaces bash grep loop
#   python3 dashboard/health.py --check DOCS-1   → replaces bash for-loop
#   python3 dashboard/health.py --check DOCS-2   → replaces bash for-loop
# Verdict-identical: same PASS/FAIL outcomes on the current repo state as the
# bash implementations they replace (the check functions predate the registry).
# ---------------------------------------------------------------------------

CHECK_REGISTRY: dict[str, callable] = {
    "DOCS-1":  check_docs1_adr_index_forward,
    "DOCS-2":  check_docs2_adr_index_reverse,
    "DOCS-3":  check_docs3_claude_md_agents,
    "DOCS-4":  check_docs4_claude_md_skills,
    "DOCS-5":  check_docs5_n3_literal,
    "DOCS-6":  check_docs6_glossary_md_refs,
    "DOCS-7":  check_docs7_adr_citations,
    "DOCS-8":  check_docs8_supersession_notes,
    "DOCS-9":  check_docs9_glossary_cap,
    "DOCS-10": check_docs10_backlog_surfacing,
    "DOCS-11": check_docs11_dead_citations,
    "R-SENSITIVE-DETECTOR": check_r_sensitive_detector,
    # Substrate checks
    "CAPTURE-SLO":     check_capture_slo,
    "HOOK-INTEGRITY":  check_hook_integrity,
    "ISOLATION-GROUP": check_isolation_group,
    "RULE-COVERAGE":   check_rule_coverage,
    "SPEC-COVERAGE":   check_spec_coverage,
    # Memory checks (ADR-0067 wave 4)
    "TESTS-COLLECTED": check_tests_collected,
    # Verification-integrity checks (require network/collector)
    "BLIND-RATE":      check_blind_dispatch_rate,
    "RESIDUAL-RATIO":  check_residual_ratio,
    "MERGE-INTEGRITY": check_merge_integrity,
    "CAPTURE-SHAPE":   check_capture_shape,
    "GREEN-MAIN":      check_green_main,
    "SILENT-DRIFT":    check_silent_drift,
}


def check_parity() -> dict:
    """PARITY: registry IDs == audit-skill-declared IDs == CI-consumed IDs.

    Implements ADR-0064 D3 standing parity alarm.

    Three ID sets are compared:
    1. Registry IDs: keys of CHECK_REGISTRY (the single-source implementation).
    2. Skill-declared IDs: DOCS-* and AS-* IDs extracted from the ### <id> —
       headings in audit-meta/SKILL.md and audit-subagents/SKILL.md.
    3. CI-consumed IDs: IDs extracted from python3 dashboard/health.py invocations
       in tools/ci-checks.sh (lines matching --check <ID> or --list patterns).

    The check is honest about what it can and cannot measure today:
    - Skill-declared = the ## headings that look like "### DOCS-N — " or
      "### AS-*-N — " in the two SKILL.md files.  If the skill format changes,
      the parse documents what it found rather than silently under-counting.
    - CI-consumed = `--check <ID>` arguments in ci-checks.sh.  Post-migration
      CHECK 4/5 use registry calls; the set grows as later slices add more.
    - Registry IDs are the authoritative set (per ADR-0064 D3).

    PASS when CI-consumed ⊆ registry (every CI-consumed ID is in the registry).
    WARN when skill-declared IDs exist that are NOT in the registry (gap to close
    in later slices) but CI-consumed is covered.
    FAIL on orphan CI-consumed IDs (CI calls a check the registry doesn't have).

    PARITY: <registry_count> registered, <skill_count> skill-declared,
            <ci_count> CI-consumed; orphan-ci=[] skill-gaps=[]
    """
    # --- 1. Registry IDs ---
    registry_ids = set(CHECK_REGISTRY.keys())

    # --- 2. Skill-declared IDs ---
    # Parse ### <id> — headings from both SKILL.md files.
    _skill_id_pat = re.compile(
        r'^###\s+((?:DOCS|AS|STRUCT)-[A-Z0-9_-]+)\s+—',
        re.MULTILINE,
    )
    skill_ids: set[str] = set()
    for skill_path in [_AUDIT_META_SKILL, _AUDIT_SUBAGENTS_SKILL]:
        try:
            text = skill_path.read_text(encoding="utf-8", errors="replace")
            for m in _skill_id_pat.finditer(text):
                skill_ids.add(m.group(1))
        except Exception:
            pass

    # --- 3. CI-consumed IDs ---
    # Scan tools/ci-checks.sh for: --check <ID> patterns.
    ci_checks_path = _HEALTH_REPO_ROOT / "tools" / "ci-checks.sh"
    _ci_id_pat = re.compile(r'--check\s+([A-Z][A-Z0-9_-]+)', re.MULTILINE)
    ci_ids: set[str] = set()
    try:
        ci_text = ci_checks_path.read_text(encoding="utf-8", errors="replace")
        for m in _ci_id_pat.finditer(ci_text):
            ci_ids.add(m.group(1))
    except Exception:
        pass

    # --- Compute diffs ---
    orphan_ci = sorted(ci_ids - registry_ids)   # CI calls non-existent registry check
    skill_gaps = sorted(skill_ids - registry_ids)  # skill declares IDs not in registry

    r_count = len(registry_ids)
    s_count = len(skill_ids)
    c_count = len(ci_ids)

    detail = (
        f"{r_count} registered, {s_count} skill-declared, {c_count} CI-consumed; "
        f"orphan-ci={orphan_ci}; skill-gaps={skill_gaps}"
    )

    if orphan_ci:
        return {"id": "PARITY", "result": "FAIL", "detail": detail,
                "registry_ids": sorted(registry_ids), "skill_ids": sorted(skill_ids),
                "ci_ids": sorted(ci_ids), "orphan_ci": orphan_ci, "skill_gaps": skill_gaps}
    if skill_gaps:
        return {"id": "PARITY", "result": "WARN", "detail": detail,
                "registry_ids": sorted(registry_ids), "skill_ids": sorted(skill_ids),
                "ci_ids": sorted(ci_ids), "orphan_ci": orphan_ci, "skill_gaps": skill_gaps}
    return {"id": "PARITY", "result": "PASS", "detail": detail,
            "registry_ids": sorted(registry_ids), "skill_ids": sorted(skill_ids),
            "ci_ids": sorted(ci_ids), "orphan_ci": orphan_ci, "skill_gaps": skill_gaps}


# Register PARITY into the registry after defining it (self-referential).
CHECK_REGISTRY["PARITY"] = check_parity


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
                check_rule_coverage(),
                check_spec_coverage(),
                check_critic_health(),
                check_tests_collected(),
            ]
        },
        "verificationIntegrity": {
            "checks": [
                check_blind_dispatch_rate(),
                check_residual_ratio(),
                check_proof_presence(),
                check_merge_integrity(),
                check_capture_shape(),
                check_green_main(),
                check_silent_drift(),
            ]
        },
        "registryIntegrity": {
            "checks": [
                check_parity(),
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
                "verificationIntegrity": {"checks": []},
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


# ---------------------------------------------------------------------------
# CLI entry point (ADR-0064 D3 registry CLI)
#
#   python dashboard/health.py --check <id>   run one check; print verdict
#   python dashboard/health.py --list          list registered IDs
#
# Exit codes: 0 = PASS/WARN, 1 = FAIL, 2 = unknown ID / bad args.
# Output: one line per result, human-readable.  Consumed by ci-checks.sh.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse as _argparse
    import json as _json

    _parser = _argparse.ArgumentParser(
        description="health.py check registry CLI (ADR-0064 D3)",
        prog="python dashboard/health.py",
    )
    _group = _parser.add_mutually_exclusive_group(required=True)
    _group.add_argument(
        "--check", metavar="ID",
        help="run a single check by ID and print its verdict",
    )
    _group.add_argument(
        "--list", action="store_true",
        help="list all registered check IDs, one per line",
    )
    _args = _parser.parse_args()

    if _args.list:
        for _id in sorted(CHECK_REGISTRY.keys()):
            print(_id)
        sys.exit(0)

    # --check <id>
    _check_id = _args.check
    if _check_id not in CHECK_REGISTRY:
        print(f"ERROR: unknown check ID '{_check_id}'", file=sys.stderr)
        print(f"Use --list to see available IDs.", file=sys.stderr)
        sys.exit(2)

    _result = CHECK_REGISTRY[_check_id]()
    _verdict = _result.get("result", "UNKNOWN")
    _detail = _result.get("detail", "")
    _line = f"{_verdict}: {_check_id}"
    if _detail:
        _line += f" — {_detail}"
    print(_line)

    # Exit 1 on FAIL; 0 on PASS or WARN (CI can choose to treat WARN as passing)
    sys.exit(1 if _verdict == "FAIL" else 0)
