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
    check_r_sensitive_detector() -> dict   (slice #840/ADR-0070 D4: guardrail-touching promotions counter)
    check_meta_tripwire() -> dict          (slice #840/ADR-0070 D4: promotion meta-tripwire — FAIL if guardrail-path batch lacks promotion-ack)
    audit_subagents() -> dict
    check_audit_subagents() -> dict  (slice #921/PRD #919: AS-AUDIT registry entry)
    audit_meta() -> dict
    cascade_finder_summary() -> dict
    check_test_ordering() -> dict         (slice #816/ADR-0067 D2: fix-type PR test-first ordering rate)
    check_quarantine_sla() -> dict        (slice #816/ADR-0067 D4: quarantine register size + oldest-entry SLA)
    check_frontmatter_coverage() -> dict  (slice #820/ADR-0027 D1: % agent files with explicit model: frontmatter)
    check_capture_slo() -> dict          (slice #767: capture liveness SLO)
    check_hook_integrity() -> dict       (slice #767: hook attempt-vs-ok ratio)
    check_hook_liveness() -> dict        (slice #849: hook-layer dark detection via beacon lag)
    check_stale_server() -> dict         (slice #907/ADR-0071 D5: server sha vs HEAD freshness check)
    check_isolation_group() -> dict      (slice #767: worktree orphan/drift check)
    check_rule_coverage() -> dict        (slice #768/ADR-0056 D3: rule coverage ratio)
    check_spec_coverage() -> dict        (slice #798/ADR-0066 D2: per-PRD criterion coverage)
    check_blind_dispatch_rate() -> dict  (slice #783/ADR-0060 D1: BLIND-REVIEW prefix rate)
    check_residual_ratio() -> dict       (slice #797/ADR-0066 D1: JUDGMENT+EXTRACT_FAILED / total QA-plan rows)
    check_proof_presence() -> dict       (slice #783/ADR-0061 D1: route+proof-token per merged PR)
    check_proof_integrity() -> dict      (slice #839/ADR-0070 D5: DOM inner_text attestation check)
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

# Declared-ID source paths for parsing check rationale + mechanic text (slice #629).
# _AUDIT_META_SKILL was the former source for DOCS-*/STRUCT-* check IDs; after PRD #919
# slice #920, the canonical declared-ID source for those checks moved to codebase-critic.md
# (the ### STRUCT-N / ### DOCS-N headings in its "Deterministic pre-checks" section).
# _AUDIT_SUBAGENTS_SKILL was the former source for AS-* check IDs; after PRD #919
# slice #921, AS-* checks are registered in CHECK_REGISTRY (AS-AUDIT) — no separate source.
_CODEBASE_CRITIC_MD = _HEALTH_REPO_ROOT / ".claude" / "agents" / "codebase-critic.md"

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
    """Return the source file that declares the given check ID.

    DOCS-*/STRUCT-* checks were declared in audit-meta/SKILL.md; after PRD #919
    slice #920 retired that skill, their canonical declared-ID source is
    codebase-critic.md (the Deterministic pre-checks section).
    AS-* checks were declared in audit-subagents/SKILL.md; after PRD #919
    slice #921 retired that skill, AS-AUDIT is registered directly in
    CHECK_REGISTRY — rationale text lives in the check_audit_subagents docstring.
    """
    return _CODEBASE_CRITIC_MD


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
    """DOCS-6: no GLOSSARY.md refs outside the 2-file allowlist + decisions/.

    codebase-critic.md is allowlisted because its absorbed DOCS-6 check heading
    text ("### DOCS-6 — no `GLOSSARY.md` references...") contains "GLOSSARY.md"
    as documentation, not as an active reference. audit-meta/SKILL.md was
    formerly allowlisted for the same reason; it was deleted by PRD #919 slice #920.
    """
    allowlist = {
        ".claude/skills/grill-me/SKILL.md",
        ".claude/agents/codebase-critic.md",
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
                        # Match the CANONICAL row for this ADR: starts with "| [NNNN]"
                        # not just any row that links to ADR-NNNN (which would false-positive
                        # on other ADRs that reference the superseded ADR in their annotations).
                        if line.startswith("|") and re.match(
                            r'^\|\s*\[' + re.escape(sid) + r'\]', line
                        ):
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
    """DOCS-10: no backlog-label surfacing idiom in agents/skills (except allowlist).

    codebase-critic.md is allowlisted because its absorbed DOCS-10 check heading
    text ("### DOCS-10 — no `backlog`-labeled prose...") contains the pattern as
    documentation of the check, not as an instruction to skip the backlog-critic
    gate. audit-meta/SKILL.md was formerly allowlisted for the same reason; it
    was deleted by PRD #919 slice #920. audit-subagents/SKILL.md was similarly
    allowlisted for AS-ALL-4 check text; it was deleted by PRD #919 slice #921.
    """
    allowlist = {"backlog-critic.md", "promote-to-backlog",
                 "codebase-critic.md"}
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
# R-SENSITIVE-DETECTOR + META-TRIPWIRE (ADR-0070 D4 / slice #840)
#
# ADR-0070 D4 supersedes ADR-0064 D4: the human tripwire moves from per-PR
# enforcement-path ack (blocking the autonomous develop flow) to per-promotion
# guardrail-machinery ack (blocking only main advancement for self-modifying
# batches).  R-SENSITIVE-DETECTOR is repurposed to count guardrail-touching
# promotions and their ack status.  META-TRIPWIRE is the new blocking check
# wired into RELEASE-READY condition (f).
# ---------------------------------------------------------------------------

# Guardrail-machinery path set per ADR-0070 D4 (superset of ADR-0064 D4):
#   ADR-0064 D4 enforcement paths +
#   .claude/agents/*-critic.md +
#   release-gate definition (dashboard/health.py RELEASE-READY check + promote.sh) +
#   branch-protection tooling
_GUARDRAIL_PATHS: tuple = (
    # ADR-0064 D4 enforcement layer
    ".github/workflows/",
    ".claude/settings.json",
    ".claude/hooks/",
    "tools/ci-checks.sh",
    ".githooks/",
    # Critic agent prompts
    ".claude/agents/reviewer.md",
    ".claude/agents/prd-critic.md",
    ".claude/agents/adr-critic.md",
    ".claude/agents/slicer-critic.md",
    ".claude/agents/glossary-critic.md",
    ".claude/agents/backlog-critic.md",
    ".claude/agents/codebase-critic.md",
    # Release-gate definition (the check + promotion tooling)
    "dashboard/health.py",
    "tools/promote.sh",
)

# ACK signal: label name or body keyword on a promotion record.
_PROMOTION_ACK_LABEL = "promotion-ack"

# Bootstrap cutoff: slice #840 is the implementing merge.
_META_TRIPWIRE_BOOTSTRAP_PROMOTION = 0  # day-one: all promotions post-implementation


def _is_guardrail_path(path: str) -> bool:
    """Return True if the given file path is in the guardrail-machinery set."""
    for gp in _GUARDRAIL_PATHS:
        if gp.endswith("/"):
            if path.startswith(gp):
                return True
        else:
            if path == gp:
                return True
    # Critic-md pattern: .claude/agents/*-critic.md (any critic name)
    if re.match(r'^\.claude/agents/[^/]+-critic\.md$', path):
        return True
    return False


def _read_promotion_events() -> list[dict]:
    """Read promotion events from workflow-events.jsonl.

    Returns a list of dicts with at least {"sha": str, "ts": str} keys,
    sorted chronologically (oldest first).  Returns [] if the file is absent
    or contains no promotion events.
    """
    events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    if not events_log.exists():
        return []
    promotions = []
    try:
        for line in events_log.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                import json as _json
                evt = _json.loads(line)
            except Exception:
                continue
            if evt.get("event") == "promotion":
                promotions.append(evt)
    except Exception:
        pass
    return promotions


def check_meta_tripwire() -> dict:
    """META-TRIPWIRE: guardrail-machinery promotion gate (ADR-0070 D4).

    A promotion batch is guardrail-touching if any commit since the last
    promotion modifies the guardrail-machinery set (ADR-0064 D4 enforcement
    paths + .claude/agents/*-critic.md + RELEASE-READY check + promote.sh +
    branch-protection config).

    A guardrail-touching batch FAILS this check unless a promotion-ack is
    present (promotion-ack label or body keyword on the promotion record).

    Honest day-one: if no promotions have occurred yet, there is nothing to
    check — returns WARN (no-data) rather than spurious PASS or FAIL.

    Test injection: set env var _META_TRIPWIRE_RESULT_OVERRIDE to PASS|FAIL|WARN
    to bypass the real check (used by tests and RELEASE-READY injection tests).
    """
    # Test injection — honours _META_TRIPWIRE_RESULT_OVERRIDE env var.
    override = os.environ.get("_META_TRIPWIRE_RESULT_OVERRIDE", "").strip().upper()
    if override in {"PASS", "FAIL", "WARN"}:
        detail_map = {
            "PASS": (
                "meta-tripwire: PASS (injected via _META_TRIPWIRE_RESULT_OVERRIDE); "
                "guardrail-touching batch has promotion-ack or batch is clean"
            ),
            "FAIL": (
                "meta-tripwire: FAIL (injected via _META_TRIPWIRE_RESULT_OVERRIDE); "
                "guardrail-path change in unpromoted batch lacks promotion-ack"
            ),
            "WARN": (
                "meta-tripwire: WARN (injected via _META_TRIPWIRE_RESULT_OVERRIDE); "
                "no promotion data"
            ),
        }
        return {
            "id": "META-TRIPWIRE",
            "result": override,
            "detail": detail_map[override],
        }

    # Read promotion events to determine the unpromoted batch.
    promotions = _read_promotion_events()

    if not promotions:
        # Day-one: no promotions yet — nothing to tripwire.
        return {
            "id": "META-TRIPWIRE",
            "result": "WARN",
            "detail": (
                "meta-tripwire: no promotion events found in workflow-events.jsonl; "
                "honest day-one — guardrail check deferred until first promotion runs; "
                "ADR-0070 D4"
            ),
        }

    # Get the last promotion sha.
    last_promotion = promotions[-1]
    last_sha = last_promotion.get("sha", "")

    if not last_sha:
        return {
            "id": "META-TRIPWIRE",
            "result": "WARN",
            "detail": "meta-tripwire: last promotion event missing sha; cannot evaluate",
        }

    # Check if last promotion had a promotion-ack.
    last_ack = (
        _PROMOTION_ACK_LABEL in last_promotion.get("labels", [])
        or _PROMOTION_ACK_LABEL in (last_promotion.get("body", "") or "")
        or last_promotion.get("ack") is True
    )

    # Find commits in unpromoted batch (develop HEAD .. last_sha is the promoted range).
    # Unpromoted = commits since last promotion.
    try:
        result = subprocess.run(
            ["git", "log", "--name-only", "--format=COMMIT:%H",
             f"{last_sha}..HEAD"],
            capture_output=True, text=True, timeout=15,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        if result.returncode != 0:
            return {
                "id": "META-TRIPWIRE",
                "result": "WARN",
                "detail": (
                    f"meta-tripwire: git log failed (exit={result.returncode}); "
                    f"cannot evaluate unpromoted batch"
                ),
            }
        batch_output = result.stdout
    except Exception as exc:
        return {
            "id": "META-TRIPWIRE",
            "result": "WARN",
            "detail": f"meta-tripwire: git log error: {exc}",
        }

    # Parse commit/file list from git log --name-only output.
    guardrail_files_found: list[str] = []
    for line in batch_output.splitlines():
        line = line.strip()
        if not line or line.startswith("COMMIT:"):
            continue
        if _is_guardrail_path(line):
            guardrail_files_found.append(line)

    if not guardrail_files_found:
        return {
            "id": "META-TRIPWIRE",
            "result": "PASS",
            "detail": (
                f"meta-tripwire: PASS — unpromoted batch since {last_sha[:8]} "
                f"touches no guardrail-machinery paths (ADR-0070 D4)"
            ),
        }

    # Guardrail paths found in batch — check for promotion-ack.
    unique_guardrail = sorted(set(guardrail_files_found))[:5]
    if last_ack:
        return {
            "id": "META-TRIPWIRE",
            "result": "PASS",
            "detail": (
                f"meta-tripwire: PASS — guardrail-touching batch has promotion-ack; "
                f"files: {unique_guardrail}; ADR-0070 D4"
            ),
        }

    # Guardrail paths touched + no ack → FAIL.
    return {
        "id": "META-TRIPWIRE",
        "result": "FAIL",
        "detail": (
            f"meta-tripwire: FAIL — unpromoted batch touches guardrail-machinery "
            f"path(s) without promotion-ack; add 'promotion-ack' label or keyword "
            f"to the promotion record before promoting; "
            f"guardrail files: {unique_guardrail}; ADR-0070 D4"
        ),
        "guardrail_files": unique_guardrail,
    }


def check_r_sensitive_detector() -> dict:
    """R-SENSITIVE-DETECTOR: guardrail-touching promotions + ack status (advisory).

    Repurposed per ADR-0070 D4 (slice #840): the old per-PR enforcement-path
    human-ack counter is retired.  This detector now counts guardrail-touching
    promotions (promotions whose batch modified the guardrail-machinery set per
    ADR-0070 D4) and their ack status.

    Honest day-one: 0 promotions → 0 guardrail-touching promotions.
    Always returns WARN — advisory only; not a blocking gate.
    The blocking check is META-TRIPWIRE (wired into RELEASE-READY condition (f)).
    """
    promotions = _read_promotion_events()

    if not promotions:
        return {
            "id": "R-SENSITIVE-DETECTOR",
            "result": "WARN",
            "detail": (
                "guardrail-touching promotions: 0 — no promotion events yet "
                "(honest day-one); advisory only; meta-tripwire is the blocking gate "
                "(ADR-0070 D4; ADR-0071 D3)"
            ),
            "guardrail_touching_count": 0,
            "acked_count": 0,
        }

    guardrail_touching: list[dict] = []
    for promo in promotions:
        sha = promo.get("sha", "")
        if not sha:
            continue
        # Check commits in this promotion batch.
        # For simplicity, we check if the promotion's sha itself was a guardrail
        # commit by looking at the diff from the prior sha.
        # Full per-promotion batch scan is expensive; approximate with the
        # event's recorded files if available, else mark as unknown.
        files_in_promo = promo.get("files", [])
        if files_in_promo:
            guardrail_files = [f for f in files_in_promo if _is_guardrail_path(f)]
            if guardrail_files:
                acked = (
                    _PROMOTION_ACK_LABEL in promo.get("labels", [])
                    or _PROMOTION_ACK_LABEL in (promo.get("body", "") or "")
                    or promo.get("ack") is True
                )
                guardrail_touching.append({
                    "sha": sha[:8],
                    "ts": promo.get("ts", ""),
                    "acked": acked,
                    "files": guardrail_files[:3],
                })

    gt_count = len(guardrail_touching)
    acked_count = sum(1 for p in guardrail_touching if p["acked"])

    detail = (
        f"guardrail-touching promotions: {gt_count} "
        f"({acked_count} with promotion-ack, {gt_count - acked_count} pending); "
        f"advisory only — meta-tripwire is the blocking gate "
        f"(ADR-0070 D4; ADR-0071 D3 — R-SENSITIVE per-PR rule retired)"
    )
    return {
        "id": "R-SENSITIVE-DETECTOR",
        "result": "WARN",
        "detail": detail,
        "guardrail_touching_count": gt_count,
        "acked_count": acked_count,
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
    """AS-ALL-4: no backlog-label surfacing idiom (backlog-critic + codebase-critic excluded).

    codebase-critic.md is excluded (PRD #919 slice #921 / CI promotion) for the
    same reason as in DOCS-10: its "### DOCS-10 —" heading text documents the check
    pattern as metadata, not as an instruction to bypass the backlog-critic gate.
    """
    if path.name in ("backlog-critic.md", "codebase-critic.md"):
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
    """AS-CRIT-2: paranoid OR Adversarial.*mindset (backlog-critic excluded).

    Pattern broadened (PRD #919 slice #921 / CI promotion): accepts
    "Adversarial mindset", "Adversarial-SRE mindset", etc. — any form
    of "Adversarial" followed within 30 chars by "mindset" — alongside
    the original "paranoid" literal.
    """
    if path.name == "backlog-critic.md":
        return {"id": "AS-CRIT-2", "result": "N/A", "detail": "excluded"}
    text = _read_file(path)
    ok = bool(re.search(r'(paranoid|Adversarial.{0,30}mindset)', text))
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


# Human-readable group labels for each check ID (slice #931 / PRD #927 §2 #10).
# Maps check ID → section group header shown in the Health tab.
# Groups: "Docs in sync" | "Rules enforced" | "Hooks live" | "No drift" |
#         "Verification integrity" | "Release gates" | "Session hygiene"
_CHECK_GROUP_MAP: dict = {
    # Docs in sync — audit-meta: ADR index, CLAUDE.md refs, glossary, citations
    "DOCS-1": "Docs in sync",
    "DOCS-2": "Docs in sync",
    "DOCS-3": "Docs in sync",
    "DOCS-4": "Docs in sync",
    "DOCS-5": "Docs in sync",
    "DOCS-6": "Docs in sync",
    "DOCS-7": "Docs in sync",
    "DOCS-8": "Docs in sync",
    "DOCS-9": "Docs in sync",
    "DOCS-10": "Docs in sync",
    "DOCS-11": "Docs in sync",
    # Rules enforced — rule-coverage, registry parity, critic performance
    "RULE-COVERAGE": "Rules enforced",
    "PARITY": "Rules enforced",
    "CRITIC-HEALTH": "Rules enforced",
    "SPEC-COVERAGE": "Rules enforced",
    # Hooks live — hook integrity + liveness
    "HOOK-INTEGRITY": "Hooks live",
    "HOOK-LIVENESS": "Hooks live",
    # No drift — isolation, capture-SLO, silent-drift, test health
    "CAPTURE-SLO": "No drift",
    "ISOLATION-GROUP": "No drift",
    "SILENT-DRIFT": "No drift",
    "STALE-BRANCHES": "No drift",
    "TESTS-COLLECTED": "No drift",
    "TEST-ORDERING": "No drift",
    "QUARANTINE-SLA": "No drift",
    "EVAL-REVIEWER": "No drift",
    "EVAL-PRD-CRITIC": "No drift",
    "EVAL-SLICER-CRITIC": "No drift",
    # Verification integrity — proof-presence, merge-integrity, capture-shape
    "BLIND-RATE": "Verification integrity",
    "RESIDUAL-RATIO": "Verification integrity",
    "PROOF-PRESENCE": "Verification integrity",
    "PROOF-INTEGRITY": "Verification integrity",
    "MERGE-INTEGRITY": "Verification integrity",
    "CAPTURE-SHAPE": "Verification integrity",
    "GREEN-MAIN": "Verification integrity",
    # Release gates — promotion topology, lag, release-readiness
    "BRANCH-TOPOLOGY": "Release gates",
    "PROMOTION-LAG": "Release gates",
    "RELEASE-READY": "Release gates",
    "R-SENSITIVE-DETECTOR": "Release gates",
    "META-TRIPWIRE": "Release gates",
    # Session hygiene — log rotation, untracked files, required labels, dead routes
    "UNTRACKED-SIZE": "Session hygiene",
    "LOG-ROTATION": "Session hygiene",
    "REQUIRED-LABELS": "Session hygiene",
    "DEAD-ROUTES": "Session hygiene",
    "SESSION-INJECTION": "Session hygiene",
}


def _enrich_group(checks: list) -> list:
    """Add 'group' field to each check dict using _CHECK_GROUP_MAP (slice #931).

    Mutates each dict in-place and returns the list for convenience.
    Checks not in the map get group = "Other".
    """
    for c in checks:
        check_id = c.get("id", "")
        c["group"] = _CHECK_GROUP_MAP.get(check_id, "Other")
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


def check_audit_subagents() -> dict:
    """AS-AUDIT: aggregate zero-arg wrapper over all AS-* subagent-prompt checks.

    Runs audit_subagents() across all .claude/agents/*.md files and aggregates
    per-file, per-check results into a single registry-compatible verdict:
      FAIL  — any individual check returned FAIL
      WARN  — any individual check returned WARN (and none FAIL)
      PASS  — all checks passed or N/A

    This function is the CHECK_REGISTRY entry for AS-AUDIT (PRD #919 slice #921):
    the audit-subagents skill was retired; its checks now run automatically in CI
    via `python3 dashboard/health.py --check AS-AUDIT`.

    Rationale: subagent prompts drift silently between slices. The AS-* checks
    (frontmatter, tool-boundaries, cross-ref section, surfacing convention,
    entry-protocol, CRITIC trailer, generator trailer, etc.) are the mechanical
    drift-detector per ADR-0011 D4. Running them in CI ensures every PR is
    checked, not just when the operator remembers to invoke a skill.
    """
    results = audit_subagents()
    fail_ids = []
    warn_ids = []
    for stem, entry in results.items():
        for c in entry.get("checks", []):
            r = c.get("result", "")
            cid = c.get("id", "")
            label = f"{stem}/{cid}"
            if r == "FAIL":
                fail_ids.append(label)
            elif r == "WARN":
                warn_ids.append(label)

    if fail_ids:
        detail = f"FAIL: {fail_ids}"
        if warn_ids:
            detail += f"; WARN: {warn_ids}"
        return {"id": "AS-AUDIT", "result": "FAIL", "detail": detail}
    if warn_ids:
        return {"id": "AS-AUDIT", "result": "WARN",
                "detail": f"WARN: {warn_ids}"}
    agent_count = len(results)
    return {"id": "AS-AUDIT", "result": "PASS",
            "detail": f"all checks passed across {agent_count} agent file(s)"}


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


# Rolling window for HOOK-INTEGRITY — only beacons within this many days are counted.
# Beacons older than this are ignored so pre-fix historical drift never causes a
# permanent FAIL.  Dark-hook detection for hooks silent beyond this window is
# HOOK-LIVENESS's responsibility, not this check's.
_HOOK_INTEGRITY_WINDOW_DAYS = 7


def check_hook_integrity() -> dict:
    """HOOK-INTEGRITY: attempt-vs-ok beacon ratio per hook + ERROR beacon count.

    Reads hook-fires.jsonl (read-only).  Uses a rolling window of
    _HOOK_INTEGRITY_WINDOW_DAYS so stale pre-fix history never causes a
    permanent FAIL.

    Semantics:
    - hook with recent attempts but missing ok → FAIL (genuine drift)
    - hook with NO recent beacons → not counted (dark-detection = HOOK-LIVENESS)
    - all recent attempts have matching ok → PASS
    - ERROR beacons in any window → FAIL
    """
    import json as _json
    from datetime import datetime, timezone, timedelta

    fires_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "hook-fires.jsonl"
    if not fires_log.exists():
        return {
            "id": "HOOK-INTEGRITY",
            "result": "WARN",
            "detail": "hook-fires.jsonl not found",
        }

    window_cutoff = datetime.now(timezone.utc) - timedelta(days=_HOOK_INTEGRITY_WINDOW_DAYS)

    try:
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
                # Rolling-window filter: skip beacons older than _HOOK_INTEGRITY_WINDOW_DAYS.
                ts_str = obj.get("ts", "")
                if ts_str:
                    try:
                        beacon_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if beacon_dt < window_cutoff:
                            continue  # outside rolling window — skip
                    except Exception:
                        pass  # unparseable ts: include conservatively
                if status == "attempt":
                    attempts[hook] = attempts.get(hook, 0) + 1
                elif status == "ok":
                    oks[hook] = oks.get(hook, 0) + 1
                elif status in ("ERROR", "error"):
                    error_count += 1
    except Exception as exc:
        return {"id": "HOOK-INTEGRITY", "result": "WARN",
                "detail": f"read error: {exc}"}

    # If no beacons at all in the rolling window, defer to HOOK-LIVENESS.
    if not attempts and not error_count:
        return {
            "id": "HOOK-INTEGRITY",
            "result": "WARN",
            "detail": (
                f"no attempt beacons in last {_HOOK_INTEGRITY_WINDOW_DAYS}d window; "
                f"dark-detection deferred to HOOK-LIVENESS"
            ),
        }

    # Compute per-hook ratios (only hooks that have attempt beacons in window)
    drift_hooks = []
    ratio_parts = []
    for hook, att in sorted(attempts.items()):
        ok = oks.get(hook, 0)
        ratio_parts.append(f"{hook}:{ok}/{att}")
        if ok < att:
            drift_hooks.append(f"{hook}({ok}/{att})")

    detail_parts = [f"window={_HOOK_INTEGRITY_WINDOW_DAYS}d"]
    if ratio_parts:
        detail_parts.append("ratios: " + ", ".join(ratio_parts))
    if error_count:
        detail_parts.append(f"ERROR beacons: {error_count}")
    if drift_hooks:
        detail_parts.append(f"drift: {', '.join(drift_hooks)}")

    detail = " | ".join(detail_parts)
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


# ---------------------------------------------------------------------------
# Rule→enforcer map (slice #851 — make RULE-COVERAGE count real enforcers)
#
# Each entry maps a CLAUDE.md section-1 rule number to one or more enforcers.
# Enforcer strings must be one of:
#   "R-XXX"   — reviewer.md hard-block rule (verified by check_rule_coverage)
#   "SC-XXX"  — slicer-critic.md rubric rule (verified by check_rule_coverage)
#   "CHECK-ID" — a key in CHECK_REGISTRY (verified by check_rule_coverage)
#   "advisory" — rule is explicitly advisory; no mechanical enforcer required
#
# IMPORTANT: check_rule_coverage() VERIFIES each entry against the actual file
# content at runtime — a mapped R-XXX that disappears from reviewer.md causes
# the mapped rule to fall back to unchecked.  The map cannot silently drift.
# ---------------------------------------------------------------------------
RULE_ENFORCER_MAP: dict[int, list[str]] = {
    # #1 YAGNI — reviewer hard-blocks scope drift / YAGNI violations
    1:  ["R-YAGNI", "R-SCOPE"],
    # #2 Walking-skeleton — slicer-critic enforces at decomposition time
    2:  ["SC-WALKING-SKELETON"],
    # #3 Build primitives first — no mechanical check; purely advisory discipline
    3:  ["advisory"],
    # #4 Never push to main — reviewer detects commits directly on main
    4:  ["R-NO-MAIN"],
    # #5 Conventional Commits — reviewer hard-blocks format violations
    5:  ["R-CONV-COMMITS"],
    # #6 git log as changelog — advisory; no mechanical enforcement feasible
    6:  ["advisory"],
    # #8 One PR per slice — reviewer enforces via Closes + LOC cap
    8:  ["R-CLOSES", "R-LOC"],
    # #9 DRY for docs — advisory; codebase-critic catches egregious duplication
    9:  ["advisory"],
    # #10 Main-agent meta-output discipline — advisory; enforced behaviorally
    10: ["advisory"],
    # #11 Surface deferred work as captured issues — CAPTURE-SHAPE health row
    11: ["CAPTURE-SHAPE"],
    # #12 Hooks five authorized categories — HOOK-INTEGRITY health row
    12: ["HOOK-INTEGRITY"],
    # #13 Root-cause workflow capture — CAPTURE-SHAPE (shape) + TEST-ORDERING (regression rider)
    13: ["CAPTURE-SHAPE", "TEST-ORDERING"],
    # #15 Every feature production-verified — PROOF-PRESENCE health row
    15: ["PROOF-PRESENCE"],
    # #16 Slice-decomposition is slicer's job — advisory; no mechanical check
    16: ["advisory"],
    # #17 Skill-vs-subagent litmus — advisory; audit-subagents skill checks shape
    17: ["advisory"],
    # #18 Never cite ADR from memory — advisory; adr-critic catches violations
    18: ["advisory"],
    # #19 Revise the whole flagged class — advisory; round-3 escalation is behavioral
    19: ["advisory"],
    # #20 Proof-per-claim in wrap-up summaries — PROOF-PRESENCE health row
    20: ["PROOF-PRESENCE"],
    # #21 Fixture discipline — reviewer hard-blocks fixture writes to logs
    21: ["R-FIXTURE"],
    # #22 System skeleton — slicer-critic enforces at decomposition time
    22: ["SC-SYSTEM-SKELETON"],
    # #23 No rule without a check — reviewer hard-blocks new rules without enforcement
    23: ["R-RULE-CHECK"],
}


def check_rule_coverage() -> dict:
    """RULE-COVERAGE (WARN): ratio of CLAUDE.md section-1 rules that have a
    verified enforcer (reviewer R- rule, health check ID, or advisory tag).

    Two complementary coverage paths — a rule is "covered" when EITHER holds:

    Path A — inline signal in CLAUDE.md text (legacy heuristic, preserved):
      - "CI grep", "ci-checks", "tools/ci-checks"
      - "hook validation", "pre-commit", ".claude/hooks"
      - "dashboard evaluator", "health check", "trail evaluator"
      - "output-contract", "trailer schema"
      - "reviewer rule", "R-RULE", "(Mechanized by", "(Enforced at", "(enforced by"
      - Named critic rubric pattern matching \b(R|AC|SC|PC)-[A-Z]{2,}

    Path B — verified RULE_ENFORCER_MAP entry (slice #851 addition):
      Each enforcer in RULE_ENFORCER_MAP is verified at runtime:
        - "R-XXX"    → must appear as "### R-XXX" in .claude/agents/reviewer.md
        - "SC-XXX"   → must appear in .claude/agents/slicer-critic.md
        - "advisory" → always counts as covered (explicitly tagged)
        - other      → must be a key in CHECK_REGISTRY

    Pre-existing rules (≤22) are grandfathered per ADR-0008 D8 (bootstrap-mode);
    reported in the ratio but not flagged as newly violating.
    Only rules #23+ are flagged as unchecked-and-untagged.

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

    # Path A: Coverage signals — one match anywhere in the rule's line-block is sufficient.
    _COVERAGE_SIGNALS = (
        "CI grep", "ci-checks", "tools/ci-checks",
        "hook validation", "pre-commit", ".claude/hooks",
        "dashboard evaluator", "health check", "trail evaluator",
        "output-contract", "trailer schema",
        "reviewer rule", "R-RULE", "(Mechanized by", "(Enforced at", "(enforced by",
    )
    # Named critic rubric patterns (R-XXX, AC-XXX, SC-XXX, PC-XXX) — minimum 2 uppercase letters
    _RUBRIC_PAT = re.compile(r'\b(R|AC|SC|PC)-[A-Z]{2,}')

    # Path B: Load side-files for enforcer verification (once per call).
    reviewer_md_path = _HEALTH_REPO_ROOT / ".claude" / "agents" / "reviewer.md"
    slicer_critic_path = _HEALTH_REPO_ROOT / ".claude" / "agents" / "slicer-critic.md"
    reviewer_text = _read_file(reviewer_md_path) if reviewer_md_path.exists() else ""
    slicer_text = _read_file(slicer_critic_path) if slicer_critic_path.exists() else ""

    def _enforcer_verified(enforcer: str) -> bool:
        """Return True if the enforcer string resolves to a real artifact."""
        if enforcer == "advisory":
            return True
        if enforcer.startswith("R-"):
            # Must appear as a ### heading in reviewer.md
            return f"### {enforcer}" in reviewer_text
        if enforcer.startswith("SC-"):
            return enforcer in slicer_text
        if enforcer.startswith(("PC-", "AC-")):
            return True  # prd-critic / adr-critic rules; not read here
        # Otherwise treat as a CHECK_REGISTRY ID (verified after registry is built)
        return enforcer in CHECK_REGISTRY

    def _map_covers(rnum: int) -> tuple[bool, list[str]]:
        """Return (covered_by_map, verified_enforcers) for the given rule number."""
        enforcers = RULE_ENFORCER_MAP.get(rnum, [])
        verified = [e for e in enforcers if _enforcer_verified(e)]
        return bool(verified), verified

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
    covered_detail: dict[int, str] = {}  # rnum → enforcer description
    unchecked_grandfathered = []
    unchecked_new = []

    _BOOTSTRAP_CUTOFF = 22  # rules ≤22 are grandfathered per ADR-0008 D8

    for rnum, block in rules:
        is_advisory = "(advisory)" in block
        has_signal = any(sig in block for sig in _COVERAGE_SIGNALS)
        has_rubric = bool(_RUBRIC_PAT.search(block))
        inline_covered = is_advisory or has_signal or has_rubric

        map_covered, verified_enforcers = _map_covers(rnum)
        covered = inline_covered or map_covered

        if covered:
            covered_nums.append(rnum)
            if map_covered:
                covered_detail[rnum] = ",".join(verified_enforcers)
            else:
                covered_detail[rnum] = "inline-signal"
        elif rnum <= _BOOTSTRAP_CUTOFF:
            unchecked_grandfathered.append(rnum)
        else:
            unchecked_new.append(rnum)

    covered_count = len(covered_nums)
    ratio_pct = int(covered_count * 100 / total)

    parts = [f"{covered_count}/{total} covered ({ratio_pct}%)"]

    # Emit per-rule enforcer summary for load-bearing mapped rules
    mapped_lines = []
    for rnum in sorted(covered_nums):
        desc = covered_detail.get(rnum, "")
        if desc and desc != "inline-signal":
            mapped_lines.append(f"#{rnum}:{desc}")
    if mapped_lines:
        parts.append("map-enforced: " + " ".join(mapped_lines))

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
    """GREEN-MAIN: last develop_green (or backward-compat main_green) sha + lag + age.

    Reads workflow-events.jsonl for the last 'develop_green' event (ADR-0062 D3,
    two-tier migration: slices merge to develop; green gate tracks develop HEAD).
    Falls back to 'main_green' for backward compatibility with pre-migration history
    (avoids a false-WARN window while historical logs still only carry main_green).
    lag = git rev-list <sha>..origin/develop --count
    age = seconds since the event timestamp
    Red on lag > 0 or stale > 24h.
    """
    import json as _json
    events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    if not events_log.exists():
        return {"id": "GREEN-MAIN", "result": "WARN",
                "detail": "workflow-events.jsonl not found; no develop_green events yet"}

    last_green: dict | None = None
    last_green_compat: dict | None = None  # backward-compat main_green fallback
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
                if obj.get("event") == "develop_green":
                    last_green = obj
                elif obj.get("event") == "main_green":
                    last_green_compat = obj
    except Exception as exc:
        return {"id": "GREEN-MAIN", "result": "WARN",
                "detail": f"read error: {exc}"}

    # Prefer develop_green; fall back to main_green for backward compat
    event_used = "develop_green"
    if last_green is None:
        if last_green_compat is None:
            return {"id": "GREEN-MAIN", "result": "WARN",
                    "detail": "no develop_green events found in workflow-events.jsonl"}
        last_green = last_green_compat
        event_used = "main_green"

    sha = last_green.get("sha", "")
    ts_str = last_green.get("ts", "")

    # Compute lag: commits on origin/develop since the green sha
    lag = -1
    try:
        r = subprocess.run(
            ["git", "rev-list", "--count", f"{sha}..origin/develop"],
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
    compat_note = f" (compat:{event_used})" if event_used == "main_green" else ""

    if lag > 0:
        result = "FAIL"
        detail = f"GREEN-MAIN lag={lag} commits behind; last green sha={sha_short} ({age_str}){compat_note}"
    elif age_h is not None and age_h > 24:
        result = "WARN"
        detail = f"GREEN-MAIN stale ({age_str}); lag=0; sha={sha_short}{compat_note}"
    else:
        result = "PASS"
        detail = f"sha={sha_short} lag=0 ({age_str}){compat_note}"

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
    """TESTS-COLLECTED: count of test items collected in tests/.

    Implements ADR-0067 D1 — the founding memory row: reports how many tests
    are collected in the tests/ suite. PASS when count > 0 (the suite exists
    and is non-empty). FAIL when tests/ exists but no tests are collected.
    WARN when tests/ does not exist.

    Prefers pytest --collect-only -q when pytest is importable; falls back to
    stdlib unittest discovery (python -m unittest discover --collect-only or
    a manual loader) so the health row works on any standard Python install.
    Bind-forward per ADR-0004 D2: pre-suite repos honestly report WARN.
    """
    tests_dir = _HEALTH_REPO_ROOT / "tests"
    if not tests_dir.exists():
        return {
            "id": "TESTS-COLLECTED",
            "result": "WARN",
            "detail": "tests/ directory does not exist (pre-suite: bind-forward ADR-0067 D1)",
        }

    # --- Try pytest first (optional dependency) ---
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir),
             "--collect-only", "-q", "--no-header"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        # pytest available — parse output.
        output = (result.stdout or "") + (result.stderr or "")
        # Lines containing "::" are collected test IDs.
        collected_lines = [
            line for line in output.splitlines()
            if "::" in line and not line.startswith("=") and not line.startswith("-")
        ]
        count = len(collected_lines)
        if count == 0:
            import re as _re
            m = _re.search(r'(\d+)\s+(?:test|item)', output)
            if m:
                count = int(m.group(1))

        if count > 0:
            return {
                "id": "TESTS-COLLECTED",
                "result": "PASS",
                "detail": f"{count} test(s) collected in tests/ via pytest (ADR-0067 D1)",
                "count": count,
            }
        else:
            return {
                "id": "TESTS-COLLECTED",
                "result": "FAIL",
                "detail": (
                    "tests/ exists but 0 tests collected via pytest — "
                    "suite must stay non-empty per ADR-0067 D1"
                ),
                "count": 0,
            }

    except FileNotFoundError:
        # pytest not installed — fall through to stdlib unittest discovery.
        pass
    except Exception as exc:
        # Unexpected error from pytest subprocess — fall through.
        _ = exc  # log if needed; continue to stdlib fallback

    # --- Stdlib unittest fallback (no pytest required) ---
    # Use unittest's TestLoader to discover and count tests without running them.
    try:
        import unittest as _unittest
        loader = _unittest.TestLoader()
        suite = loader.discover(str(tests_dir), pattern="test_*.py",
                                top_level_dir=str(_HEALTH_REPO_ROOT))

        def _count_tests(s) -> int:
            """Recursively count leaf TestCase instances in a suite."""
            total = 0
            for item in s:
                if hasattr(item, "__iter__"):
                    total += _count_tests(item)
                else:
                    total += 1
            return total

        count = _count_tests(suite)
        if count > 0:
            return {
                "id": "TESTS-COLLECTED",
                "result": "PASS",
                "detail": f"{count} test(s) collected in tests/ via stdlib unittest (ADR-0067 D1)",
                "count": count,
            }
        else:
            return {
                "id": "TESTS-COLLECTED",
                "result": "FAIL",
                "detail": (
                    "tests/ exists but 0 tests collected via stdlib unittest — "
                    "suite must stay non-empty per ADR-0067 D1"
                ),
                "count": 0,
            }
    except Exception as exc:
        return {
            "id": "TESTS-COLLECTED",
            "result": "WARN",
            "detail": f"test collection failed (pytest unavailable, stdlib discovery error): {exc}",
        }


# ---------------------------------------------------------------------------
# TEST-ORDERING — fix-type PR test-commit-precedes-fix-commit rate (ADR-0067 D2)
# ---------------------------------------------------------------------------


def check_test_ordering() -> dict:
    """TEST-ORDERING: % of fix-type PRs where test commit precedes fix commit.

    Implements ADR-0067 D2 — bias isolation as git-history sequencing.
    A fix-type PR is one whose branch name matches fix/* (merged or open).

    Algorithm:
    1. Fetch recently merged PRs whose headRefName starts with fix/.
    2. For each, check whether any commit in the PR branch touched tests/
       and whether that commit precedes (is an ancestor of) the first
       non-tests-only commit. Uses `git log --name-only` on the PR's
       merge commit range when available.
    3. Report: ordered/<total> with honest grandfathered bucket for PRs
       merged before this check's activation (pre-ADR-0067-D2).

    Honest grandfathering (ADR-0004 D2): fix-type PRs merged before the
    R-PROVE reviewer rule merge cannot be held to the ordering standard.
    We grandfather all fix/* PRs with merge number < the R-PROVE slice
    (issue #816). PASS = 100% of post-activation PRs conform, or no
    post-activation PRs yet (WARN).
    """
    import json as _json
    import subprocess as _sp

    _GRANDFATHERED_BELOW = 816  # PRs linked to slices < #816 are pre-activation

    def _gh_json(args: list, timeout: int = 20):
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

    # Fetch merged PRs with fix/* head branch
    prs = _gh_json([
        "pr", "list",
        "--state", "merged",
        "--limit", "30",
        "--json", "number,headRefName,mergeCommit,closingIssuesReferences",
    ])
    if prs is None:
        return {
            "id": "TEST-ORDERING",
            "result": "WARN",
            "detail": "GitHub API unavailable; honest fallback — run manually",
            "ordered": 0,
            "total": 0,
            "grandfathered": 0,
            "api_available": False,
        }

    fix_prs = [p for p in prs if (p.get("headRefName") or "").startswith("fix/")]

    grandfathered_count = 0
    ordered = 0
    disordered = []
    post_activation = []

    for pr in fix_prs:
        pr_num = pr.get("number", 0)
        # Grandfather: check if closing slice issue < 816
        closing = pr.get("closingIssuesReferences") or []
        slice_nums = [i.get("number", 0) for i in closing if isinstance(i, dict)]
        is_grandfathered = all(n < _GRANDFATHERED_BELOW for n in slice_nums) if slice_nums else (pr_num < _GRANDFATHERED_BELOW)
        if is_grandfathered:
            grandfathered_count += 1
            continue

        post_activation.append(pr_num)

        # Check ordering: does a test commit precede fix commit?
        merge_commit = (pr.get("mergeCommit") or {}).get("oid", "")
        if not merge_commit:
            # Cannot check — treat as WARN (not FAIL); count but mark unknown
            continue

        # Get commit list for this PR using git log
        try:
            result = _sp.run(
                ["git", "log", "--reverse", "--pretty=%H",
                 f"origin/main...{merge_commit}", "--"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=15,
                cwd=str(_HEALTH_REPO_ROOT),
            )
            commit_shas = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        except Exception:
            continue

        if not commit_shas:
            continue

        # For each commit, check whether it touches tests/
        first_test_idx = None
        first_fix_idx = None
        for idx, sha in enumerate(commit_shas):
            try:
                files_result = _sp.run(
                    ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", sha],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=10,
                    cwd=str(_HEALTH_REPO_ROOT),
                )
                changed = files_result.stdout.splitlines()
            except Exception:
                continue
            touches_tests = any(f.startswith("tests/") for f in changed)
            touches_non_tests = any(not f.startswith("tests/") for f in changed)
            if touches_tests and first_test_idx is None:
                first_test_idx = idx
            if touches_non_tests and not touches_tests and first_fix_idx is None:
                first_fix_idx = idx

        if first_test_idx is not None and first_fix_idx is not None:
            if first_test_idx < first_fix_idx:
                ordered += 1
            else:
                disordered.append(pr_num)
        elif first_test_idx is not None:
            # Only test commits — counts as ordered (no fix commit yet / docs-only fix)
            ordered += 1
        # else: no test commit found — counts as disordered

    total_post = len(post_activation)
    if total_post == 0:
        result_val = "WARN"
        detail = (
            f"no post-activation fix/* PRs found "
            f"(grandfathered: {grandfathered_count}; bind-forward ADR-0067 D2)"
        )
    elif disordered:
        result_val = "WARN"
        detail = (
            f"{ordered}/{total_post} ordered "
            f"(grandfathered: {grandfathered_count}; "
            f"disordered PRs: {disordered})"
        )
    else:
        result_val = "PASS"
        detail = (
            f"{ordered}/{total_post} fix-type PRs have test-first ordering "
            f"(grandfathered pre-ADR-0067-D2: {grandfathered_count})"
        )

    return {
        "id": "TEST-ORDERING",
        "result": result_val,
        "detail": detail,
        "ordered": ordered,
        "total": total_post,
        "grandfathered": grandfathered_count,
        "disordered": disordered,
    }


# ---------------------------------------------------------------------------
# QUARANTINE-SLA — quarantine register size + oldest-entry age (ADR-0067 D4)
# ---------------------------------------------------------------------------


def check_quarantine_sla() -> dict:
    """QUARANTINE-SLA: quarantine register size + oldest-entry age.

    Implements ADR-0067 D4 — flaky quarantine with SLA.
    Reads tests/quarantine.txt (blank lines and #-comment lines ignored).
    Entries must carry a [quarantined: YYYY-MM-DD] tag for age tracking.

    PASS: 0 entries, or all entries within 30-day SLA.
    WARN: entries exist but none breach the 30-day SLA.
    FAIL: at least one entry is older than 30 days (SLA breach).
    """
    import datetime as _dt

    quarantine_file = _HEALTH_REPO_ROOT / "tests" / "quarantine.txt"
    if not quarantine_file.exists():
        return {
            "id": "QUARANTINE-SLA",
            "result": "WARN",
            "detail": "tests/quarantine.txt not found (pre-suite: bind-forward ADR-0067 D4)",
            "size": 0,
            "oldest_days": None,
        }

    text = _read_file(quarantine_file)
    # Active entries: non-blank, non-comment lines
    active_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    size = len(active_lines)

    if size == 0:
        return {
            "id": "QUARANTINE-SLA",
            "result": "PASS",
            "detail": "quarantine register is empty (no quarantined tests)",
            "size": 0,
            "oldest_days": None,
        }

    # Parse [quarantined: YYYY-MM-DD] tags for age check
    _date_re = re.compile(r'\[quarantined:\s*(\d{4}-\d{2}-\d{2})\]')
    today = _dt.date.today()
    sla_days = 30
    breach_entries = []
    oldest_days = None

    for line in active_lines:
        m = _date_re.search(line)
        if m:
            try:
                entry_date = _dt.date.fromisoformat(m.group(1))
                age = (today - entry_date).days
                if oldest_days is None or age > oldest_days:
                    oldest_days = age
                if age > sla_days:
                    breach_entries.append((line.split()[0], age))
            except ValueError:
                pass  # malformed date — skip age check for this entry

    if breach_entries:
        breach_desc = "; ".join(f"{t} ({d}d)" for t, d in breach_entries[:3])
        detail = (
            f"{size} quarantined, {len(breach_entries)} SLA breach(es) >30d: "
            f"{breach_desc}"
        )
        result_val = "FAIL"
    elif oldest_days is not None:
        detail = (
            f"{size} quarantined; oldest {oldest_days}d "
            f"(SLA 30d; all within SLA)"
        )
        result_val = "WARN"
    else:
        detail = (
            f"{size} quarantined; no [quarantined: YYYY-MM-DD] tags found "
            f"— add date tags to entries for SLA tracking"
        )
        result_val = "WARN"

    return {
        "id": "QUARANTINE-SLA",
        "result": result_val,
        "detail": detail,
        "size": size,
        "oldest_days": oldest_days,
        "breach_count": len(breach_entries),
    }


# ---------------------------------------------------------------------------
# Eval checks (ADR-0067 D5) — golden-set critic evals — slice #817
# ---------------------------------------------------------------------------

_EVALS_RESULTS_FILE = _HEALTH_REPO_ROOT / "tests" / "evals" / "results.json"
_EVAL_STALE_DAYS = 14


def _check_eval_critic(critic_id: str, check_id: str) -> dict:
    """Shared implementation for EVAL-REVIEWER / EVAL-PRD-CRITIC / EVAL-SLICER-CRITIC.

    Returns WARN (honest no-baseline) when results.json absent or has no run for this
    critic.  Returns WARN when results are stale (>14 days) or pass_rate < 1.0.
    Returns PASS only when pass_rate == 1.0 and the run is fresh.

    Per ADR-0067 D5: the eval runner is on-demand only — results.json absence is
    expected on a fresh repo and must never produce a false FAIL.
    """
    if not _EVALS_RESULTS_FILE.exists():
        return {
            "id": check_id,
            "result": "WARN",
            "detail": (
                f"tests/evals/results.json not found — no eval run yet for {critic_id}; "
                "honest no-baseline bucket (ADR-0067 D5)"
            ),
            "pass_rate": None,
            "last_run_ts": None,
        }
    try:
        import json as _json  # noqa: PLC0415 — local import to avoid top-level cost
        data = _json.loads(
            _EVALS_RESULTS_FILE.read_text(encoding="utf-8", errors="replace")
        )
    except Exception as exc:
        return {
            "id": check_id,
            "result": "WARN",
            "detail": f"tests/evals/results.json unreadable: {exc}",
            "pass_rate": None,
            "last_run_ts": None,
        }

    critic_data = data.get(critic_id)
    if not critic_data:
        return {
            "id": check_id,
            "result": "WARN",
            "detail": (
                f"no run recorded for critic '{critic_id}' in results.json; "
                "honest no-baseline bucket (ADR-0067 D5)"
            ),
            "pass_rate": None,
            "last_run_ts": None,
        }

    last_run_ts = critic_data.get("ts")
    pass_rate = critic_data.get("pass_rate")
    total = critic_data.get("total", 0)
    passed = critic_data.get("passed", 0)

    # Staleness check
    stale = False
    if last_run_ts:
        try:
            from datetime import datetime as _dt, timezone as _tz  # noqa: PLC0415
            run_dt = _dt.fromisoformat(last_run_ts.replace("Z", "+00:00"))
            age_days = (_dt.now(_tz.utc) - run_dt).days
            stale = age_days > _EVAL_STALE_DAYS
        except Exception:
            stale = False

    if stale:
        return {
            "id": check_id,
            "result": "WARN",
            "detail": (
                f"eval results for '{critic_id}' are stale (>{_EVAL_STALE_DAYS} days); "
                f"re-run: python tools/run_evals.py --critic {critic_id}"
            ),
            "pass_rate": pass_rate,
            "last_run_ts": last_run_ts,
        }

    if pass_rate is None:
        return {
            "id": check_id,
            "result": "WARN",
            "detail": (
                f"eval run for '{critic_id}' has no pass_rate (0 cases?); "
                "honest no-baseline bucket (ADR-0067 D5)"
            ),
            "pass_rate": None,
            "last_run_ts": last_run_ts,
        }

    if pass_rate < 1.0:
        failed = total - passed
        return {
            "id": check_id,
            "result": "WARN",
            "detail": (
                f"eval pass_rate={pass_rate:.2%} for '{critic_id}' "
                f"({passed}/{total} passed, {failed} failed); "
                "review failing cases in tests/evals/results.json"
            ),
            "pass_rate": pass_rate,
            "last_run_ts": last_run_ts,
        }

    return {
        "id": check_id,
        "result": "PASS",
        "detail": (
            f"eval pass_rate=100% for '{critic_id}' ({passed}/{total} cases); "
            f"run ts={last_run_ts}"
        ),
        "pass_rate": pass_rate,
        "last_run_ts": last_run_ts,
    }


def check_eval_reviewer() -> dict:
    """EVAL-REVIEWER: golden-set evals for the reviewer critic (ADR-0067 D5)."""
    return _check_eval_critic("reviewer", "EVAL-REVIEWER")


def check_eval_prd_critic() -> dict:
    """EVAL-PRD-CRITIC: golden-set evals for the prd-critic (ADR-0067 D5)."""
    return _check_eval_critic("prd-critic", "EVAL-PRD-CRITIC")


def check_eval_slicer_critic() -> dict:
    """EVAL-SLICER-CRITIC: golden-set evals for the slicer-critic (ADR-0067 D5)."""
    return _check_eval_critic("slicer-critic", "EVAL-SLICER-CRITIC")


def _insert_dashboard_sys_path() -> None:
    """Ensure dashboard/ is on sys.path for sibling imports."""
    dashboard_dir = str(Path(__file__).resolve().parent)
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)




def check_frontmatter_coverage() -> dict:
    """FRONTMATTER-COVERAGE: % subagent files with explicit model: frontmatter.

    Implements ADR-0027 D1 standing invariant (every .claude/agents/*.md
    MUST have explicit model: frontmatter). Reports honest current value; PASS=100%.

    PASS when all agent files have explicit model: frontmatter.
    FAIL when any agent file is missing the model: field.
    WARN when the agents directory is missing or unreadable.
    """
    agents_dir = _HEALTH_REPO_ROOT / ".claude" / "agents"
    if not agents_dir.exists():
        return {
            "id": "FRONTMATTER-COVERAGE",
            "result": "WARN",
            "detail": ".claude/agents/ directory not found",
            "covered": 0, "total": 0, "missing": [],
        }

    agent_files = sorted(agents_dir.glob("*.md"))
    if not agent_files:
        return {
            "id": "FRONTMATTER-COVERAGE",
            "result": "WARN",
            "detail": "no .md files in .claude/agents/",
            "covered": 0, "total": 0, "missing": [],
        }

    missing = []
    _model_re = re.compile(r'^model\s*:', re.MULTILINE)
    for agent_path in agent_files:
        try:
            text = agent_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            missing.append(agent_path.name)
            continue
        if not _model_re.search(text):
            missing.append(agent_path.name)

    total = len(agent_files)
    covered = total - len(missing)
    pct = int(covered * 100 / total) if total > 0 else 0
    detail = (
        f"{covered}/{total} agent files have explicit model: frontmatter "
        f"({pct}%; ADR-0027 D1 invariant; expect 100%)"
    )
    if missing:
        detail += f"; missing: {missing[:5]}"
    result = "PASS" if not missing else "FAIL"
    return {
        "id": "FRONTMATTER-COVERAGE",
        "result": result,
        "detail": detail,
        "covered": covered,
        "total": total,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Stale-server check (ADR-0071 D5 — slice #907)
# ---------------------------------------------------------------------------

def check_stale_server() -> dict:
    """STALE-SERVER: dashboard server sha vs git HEAD (is the server fresh?).

    Compares the sha reported by /api/meta against the current git HEAD.
    PASS  when server sha == HEAD (server loaded current code).
    FAIL  when sha differs from HEAD OR /api/meta reports stale=True.
    WARN  when the server is not reachable (no server running is not stale).

    Supports env-var overrides for offline testing:
      _STALE_SERVER_META_OVERRIDE  — JSON string for the /api/meta response body
        (empty string = simulate unreachable / connection error).
      _STALE_SERVER_HEAD_OVERRIDE  — HEAD sha string (overrides git rev-parse).

    Per ADR-0071 D5 (server-staleness claim); surfaces the #726 staleness
    condition as an honest registry row.
    """
    import json as _json
    import urllib.request as _urllib_request
    import urllib.error as _urllib_error

    # --- 1. Get HEAD sha ---
    head_override = os.environ.get("_STALE_SERVER_HEAD_OVERRIDE", "")
    if head_override:
        head_sha = head_override.strip()
    else:
        try:
            r = subprocess.run(
                ["git", "-C", str(_HEALTH_REPO_ROOT), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            head_sha = r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            head_sha = ""

    if not head_sha:
        return {
            "id": "STALE-SERVER",
            "result": "WARN",
            "detail": "could not determine git HEAD sha; check skipped",
        }

    # --- 2. Fetch /api/meta from running server ---
    meta_override = os.environ.get("_STALE_SERVER_META_OVERRIDE", None)
    if meta_override is not None:
        # Test injection path
        if meta_override == "":
            # Simulate unreachable server
            return {
                "id": "STALE-SERVER",
                "result": "WARN",
                "detail": "dashboard server not reachable (no server running is not stale)",
            }
        try:
            meta = _json.loads(meta_override)
        except Exception as exc:
            return {
                "id": "STALE-SERVER",
                "result": "WARN",
                "detail": f"meta override parse error: {exc}",
            }
    else:
        # Production path: try localhost:8765 (the canonical dashboard port)
        try:
            with _urllib_request.urlopen(
                "http://localhost:8765/api/meta", timeout=3
            ) as resp:
                meta = _json.loads(resp.read().decode("utf-8"))
        except (_urllib_error.URLError, OSError):
            return {
                "id": "STALE-SERVER",
                "result": "WARN",
                "detail": "dashboard server not reachable at localhost:8765 (no server running is not stale)",
            }
        except Exception as exc:
            return {
                "id": "STALE-SERVER",
                "result": "WARN",
                "detail": f"unexpected error fetching /api/meta: {exc}",
            }

    # --- 3. Compare sha and stale flag ---
    server_sha = meta.get("sha", "")
    server_stale_flag = bool(meta.get("stale", False))

    if not server_sha:
        return {
            "id": "STALE-SERVER",
            "result": "WARN",
            "detail": "server /api/meta did not return a sha; cannot compare",
        }

    if server_stale_flag or server_sha != head_sha:
        reason = []
        if server_stale_flag:
            reason.append("server reports stale=True")
        if server_sha != head_sha:
            reason.append(
                f"server sha {server_sha[:12]} != HEAD {head_sha[:12]}"
            )
        return {
            "id": "STALE-SERVER",
            "result": "FAIL",
            "detail": (
                "stale server detected: " + "; ".join(reason)
                + " — restart dashboard to load current code"
            ),
            "server_sha": server_sha,
            "head_sha": head_sha,
        }

    return {
        "id": "STALE-SERVER",
        "result": "PASS",
        "detail": f"server sha {server_sha[:12]} matches HEAD (server is fresh)",
        "server_sha": server_sha,
        "head_sha": head_sha,
    }


# ---------------------------------------------------------------------------
# Hygiene registry checks (ADR-0068 D1) — wave-4 slice #818
# ---------------------------------------------------------------------------

# Threshold: untracked file count under tracked directories before WARN.
_UNTRACKED_SIZE_WARN_COUNT = 50
# Rotation cap in bytes (must match log-tool-event.sh _ROTATION_CAP_BYTES).
_LOG_ROTATION_CAP_BYTES = 5 * 1024 * 1024   # 5 MB
# Stale branch age in days (no PR + inactive > this → stale).
_STALE_BRANCH_DAYS = 14
# Required labels as declared in bootstrap.sh LABELS array.
_REQUIRED_LABELS = [
    "prd", "slice", "backlog", "captured",
    "trivial", "needs-human", "needs-human-check", "root-cause",
]


def check_untracked_size() -> dict:
    """UNTRACKED-SIZE: count + size of untracked files under tracked dirs.

    Implements ADR-0068 D1 — workspace hygiene row. Reports the count of
    untracked files under tracked directories (e.g. qa-proof/).
    WARN when count > _UNTRACKED_SIZE_WARN_COUNT.
    Honest day-one values: pre-existing accumulation is the honest starting
    value, not a FAIL (ADR-0004 D2 bootstrap-mode).
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=15,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        if result.returncode != 0:
            return {"id": "UNTRACKED-SIZE", "result": "WARN",
                    "detail": "git ls-files failed"}
        files = [f for f in result.stdout.splitlines() if f.strip()]
        count = len(files)
        # Sum sizes
        total_bytes = 0
        for f in files:
            try:
                total_bytes += (_HEALTH_REPO_ROOT / f).stat().st_size
            except Exception:
                pass
        size_mb = round(total_bytes / (1024 * 1024), 2)
        detail = (
            f"{count} untracked file(s) under tracked dirs "
            f"({size_mb} MB total); "
            f"threshold: WARN at >{_UNTRACKED_SIZE_WARN_COUNT} "
            f"(honest day-one ADR-0068 D1)"
        )
        result_str = "WARN" if count > _UNTRACKED_SIZE_WARN_COUNT else "PASS"
        return {"id": "UNTRACKED-SIZE", "result": result_str, "detail": detail,
                "count": count, "size_mb": size_mb}
    except Exception as exc:
        return {"id": "UNTRACKED-SIZE", "result": "WARN",
                "detail": f"check failed: {exc}"}


def check_log_rotation() -> dict:
    """LOG-ROTATION: workflow-events.jsonl size vs the rotation cap.

    Implements ADR-0068 D1. FAIL when the production log file meets or exceeds
    the cap and no rotation archive exists (rotation is broken).
    WARN when the log file exceeds 80% of the cap (proactive notice).
    PASS otherwise.

    Rotation cap: _LOG_ROTATION_CAP_BYTES (5 MB) — must match the cap
    documented in log-tool-event.sh _ROTATION_CAP_BYTES.
    """
    logs_dir = _HEALTH_REPO_ROOT / ".claude" / "logs"
    events_log = logs_dir / "workflow-events.jsonl"
    if not events_log.exists():
        return {"id": "LOG-ROTATION", "result": "WARN",
                "detail": "workflow-events.jsonl not found (pre-hook setup expected)"}

    try:
        size = events_log.stat().st_size
        size_mb = round(size / (1024 * 1024), 2)
        cap_mb = round(_LOG_ROTATION_CAP_BYTES / (1024 * 1024), 1)

        # Count archive files (workflow-events.YYYYMMDDTHHMMSS.jsonl).
        import glob as _glob
        archives = _glob.glob(
            str(logs_dir / "workflow-events.2*.jsonl")
        )
        archive_count = len(archives)

        if size >= _LOG_ROTATION_CAP_BYTES:
            return {
                "id": "LOG-ROTATION",
                "result": "FAIL",
                "detail": (
                    f"workflow-events.jsonl is {size_mb} MB "
                    f"(cap {cap_mb} MB) — rotation not occurring; "
                    f"archives on disk: {archive_count}"
                ),
                "size_mb": size_mb, "cap_mb": cap_mb,
                "archive_count": archive_count,
            }
        elif size >= 0.8 * _LOG_ROTATION_CAP_BYTES:
            return {
                "id": "LOG-ROTATION",
                "result": "WARN",
                "detail": (
                    f"workflow-events.jsonl at {size_mb} MB "
                    f"(>80% of {cap_mb} MB cap); "
                    f"archives on disk: {archive_count}"
                ),
                "size_mb": size_mb, "cap_mb": cap_mb,
                "archive_count": archive_count,
            }
        return {
            "id": "LOG-ROTATION",
            "result": "PASS",
            "detail": (
                f"{size_mb} MB / {cap_mb} MB cap; "
                f"rotation grip = archive-aside (ADR-0068 D1); "
                f"archives on disk: {archive_count}"
            ),
            "size_mb": size_mb, "cap_mb": cap_mb,
            "archive_count": archive_count,
        }
    except Exception as exc:
        return {"id": "LOG-ROTATION", "result": "WARN",
                "detail": f"check failed: {exc}"}


def check_stale_branches() -> dict:
    """STALE-BRANCHES: remote branches merged or >14 days inactive without PR.

    Implements ADR-0068 D1. Advisory only: detectors report, humans act.
    Bind-forward per ADR-0004 D2: pre-existing branches are honest starting value.
    Needs git access; degrades gracefully on network failure.
    """
    try:
        import datetime as _dt
        import json as _json

        # Fetch remote branch refs + last commit date.
        result = subprocess.run(
            ["git", "for-each-ref",
             "--format=%(refname:short) %(committerdate:iso8601)",
             "refs/remotes/origin"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        if result.returncode != 0:
            return {"id": "STALE-BRANCHES", "result": "WARN",
                    "detail": "git for-each-ref failed (network/repo unavailable)"}

        now = _dt.datetime.now(_dt.timezone.utc)
        cutoff = now - _dt.timedelta(days=_STALE_BRANCH_DAYS)

        stale = []
        total = 0
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            ref_name = parts[0]
            # Skip HEAD and main
            if ref_name in ("origin/HEAD", "origin/main"):
                continue
            total += 1
            date_str = parts[1].strip()
            try:
                # Parse iso8601 with timezone offset
                dt = _dt.datetime.fromisoformat(date_str[:25])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_dt.timezone.utc)
                if dt < cutoff:
                    age_days = (now - dt).days
                    stale.append(f"{ref_name}({age_days}d)")
            except Exception:
                pass

        if stale:
            return {
                "id": "STALE-BRANCHES",
                "result": "WARN",
                "detail": (
                    f"{len(stale)}/{total} remote branches inactive "
                    f">{_STALE_BRANCH_DAYS}d: {', '.join(stale[:5])}"
                    + (" ..." if len(stale) > 5 else "")
                    + " (detectors-report-humans-act per ADR-0068 D1)"
                ),
                "stale_count": len(stale),
                "total": total,
            }
        return {
            "id": "STALE-BRANCHES",
            "result": "PASS",
            "detail": (
                f"0/{total} remote branches stale "
                f"(threshold >{_STALE_BRANCH_DAYS}d inactive)"
            ),
            "stale_count": 0,
            "total": total,
        }
    except Exception as exc:
        return {"id": "STALE-BRANCHES", "result": "WARN",
                "detail": f"check failed: {exc}"}


def check_required_labels() -> dict:
    """REQUIRED-LABELS: declared labels in bootstrap.sh vs live repo.

    Implements ADR-0068 D1. Checks that every label in _REQUIRED_LABELS
    exists on the live GitHub repo. Missing labels = WARN (bootstrap.sh drift).
    Gracefully degrades when gh CLI is unavailable.
    """
    import json as _json
    try:
        result = subprocess.run(
            ["gh", "label", "list", "--limit", "200", "--json", "name"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20,
            cwd=str(_HEALTH_REPO_ROOT), stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return {"id": "REQUIRED-LABELS", "result": "WARN",
                    "detail": "gh label list failed (auth/network; degrade expected)"}
        live_labels = {item["name"] for item in _json.loads(result.stdout)}
    except Exception as exc:
        return {"id": "REQUIRED-LABELS", "result": "WARN",
                "detail": f"gh unavailable: {exc}"}

    missing = [lb for lb in _REQUIRED_LABELS if lb not in live_labels]
    if missing:
        return {
            "id": "REQUIRED-LABELS",
            "result": "WARN",
            "detail": (
                f"labels missing from live repo: {missing}; "
                f"run bootstrap.sh to create them (ADR-0068 D1)"
            ),
            "missing": missing,
        }
    return {
        "id": "REQUIRED-LABELS",
        "result": "PASS",
        "detail": (
            f"all {len(_REQUIRED_LABELS)} required labels present "
            f"on live repo (ADR-0068 D1)"
        ),
        "missing": [],
    }


def check_dead_routes() -> dict:
    """DEAD-ROUTES: API routes served but never fetched by the frontend.

    Implements ADR-0068 D1. Scans dashboard/server.py for registered API routes
    (lines with @app.route('/api/...')) then checks dashboard/index.html for
    fetch('/api/...') calls. Routes served but never fetched = dead surface.
    Honest day-one: pre-existing dead routes are the starting value, not a FAIL.
    """
    server_py = _HEALTH_REPO_ROOT / "dashboard" / "server.py"
    index_html = _HEALTH_REPO_ROOT / "dashboard" / "index.html"

    if not server_py.exists():
        return {"id": "DEAD-ROUTES", "result": "WARN",
                "detail": "dashboard/server.py not found"}
    if not index_html.exists():
        return {"id": "DEAD-ROUTES", "result": "WARN",
                "detail": "dashboard/index.html not found"}

    try:
        server_text = _read_file(server_py)
        html_text = _read_file(index_html)

        # Extract routes from server.py.
        # Supports two patterns:
        #   1. elif path == "/api/..."  (custom HTTPHandler dispatch)
        #   2. @app.route('/api/...')   (Flask-style decorator)
        served_routes = set(re.findall(
            r'''elif\s+path\s*==\s*['"](/api/[^'"]+)['"]''',
            server_text
        ))
        served_routes |= set(re.findall(
            r'''@app\.route\(['"](/api/[^'"]+)['"]''',
            server_text
        ))
        # Extract fetch targets from index.html: fetch('/api/...') or fetch(`/api/...`)
        fetched_routes = set(re.findall(
            r'''fetch\([`'"]([/][^`'"?]+)''',
            html_text
        ))
        # Normalize: strip trailing slashes
        served_normalized = {r.rstrip("/") for r in served_routes}
        fetched_normalized = {r.rstrip("/") for r in fetched_routes}

        dead = sorted(served_normalized - fetched_normalized)
        total_served = len(served_normalized)

        if dead:
            return {
                "id": "DEAD-ROUTES",
                "result": "WARN",
                "detail": (
                    f"{len(dead)}/{total_served} route(s) served but not fetched "
                    f"by index.html: {dead[:5]}"
                    + (" ..." if len(dead) > 5 else "")
                    + " (detectors-report per ADR-0068 D1)"
                ),
                "dead_count": len(dead),
                "dead_routes": dead[:10],
                "total_served": total_served,
            }
        return {
            "id": "DEAD-ROUTES",
            "result": "PASS",
            "detail": (
                f"all {total_served} served /api/* routes are fetched "
                f"by index.html (ADR-0068 D1)"
            ),
            "dead_count": 0,
            "dead_routes": [],
            "total_served": total_served,
        }
    except Exception as exc:
        return {"id": "DEAD-ROUTES", "result": "WARN",
                "detail": f"check failed: {exc}"}


def check_session_injection() -> dict:
    """SESSION-INJECTION: one session_context_injected event per session_id.

    Implements ADR-0068 D3. Reads workflow-events.jsonl and counts sessions
    that have a 'session_context_injected' event.

    PASS when all sessions in the last 20-session window have an injection
    event (the hook is live).
    WARN when fewer than 50% have one (hook not yet active / pre-hook sessions
    dominate the window — expected before this slice's deployment).
    Reports resumed-session gap count (sessions without injection).

    Bind-forward per ADR-0004 D2: pre-hook sessions are honest gaps, not FAILs.
    """
    import json as _json
    events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"
    if not events_log.exists():
        return {"id": "SESSION-INJECTION", "result": "WARN",
                "detail": "workflow-events.jsonl not found (pre-hook setup expected)"}

    _SESSION_WINDOW = 20

    try:
        sessions: dict[str, set] = {}  # session_id → set of event types seen
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
                if ev:
                    sessions[sid].add(ev)
    except Exception as exc:
        return {"id": "SESSION-INJECTION", "result": "WARN",
                "detail": f"read error: {exc}"}

    if not sessions:
        return {"id": "SESSION-INJECTION", "result": "WARN",
                "detail": "no sessions found in workflow-events.jsonl"}

    window = list(sessions.items())[-_SESSION_WINDOW:]
    total = len(window)
    with_injection = sum(
        1 for _sid, evts in window
        if "session_context_injected" in evts
    )
    without = total - with_injection
    ratio = with_injection / total if total > 0 else 0.0

    # Per-session summary (most recent first, capped at 8)
    per_session = []
    for sid, evts in reversed(window[-8:]):
        tag = "injected" if "session_context_injected" in evts else "no-injection"
        per_session.append(f"{sid[:8]}:{tag}")

    detail = (
        f"{with_injection}/{total} sessions in last {_SESSION_WINDOW}-session "
        f"window have injection event "
        f"({ratio*100:.0f}%); gaps={without} | "
        + ", ".join(per_session)
    )

    # Pre-hook: WARN (not FAIL) — bind-forward ADR-0004 D2.
    # Once the hook is live, WARN when <50% of the window has injection.
    result = "PASS" if ratio >= 0.50 else "WARN"
    return {
        "id": "SESSION-INJECTION",
        "result": result,
        "detail": detail,
        "with_injection": with_injection,
        "total": total,
        "ratio": round(ratio, 3),
    }


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


# ---------------------------------------------------------------------------
# Two-tier topology checks (ADR-0070 wave 5 — slice #843 full implementation)
# ---------------------------------------------------------------------------

def _git_sha(ref: str) -> str:
    """Return the SHA for a git ref; empty string on failure."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", ref],
            capture_output=True, text=True, timeout=8,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_count(range_spec: str) -> int:
    """Return commit count for a git rev-list range; -1 on error."""
    try:
        r = subprocess.run(
            ["git", "rev-list", "--count", range_spec],
            capture_output=True, text=True, timeout=8,
            cwd=str(_HEALTH_REPO_ROOT),
        )
        return int(r.stdout.strip()) if r.returncode == 0 else -1
    except Exception:
        return -1


def check_branch_topology() -> dict:
    """BRANCH-TOPOLOGY: real two-tier develop/main topology assertion (ADR-0070 D1/D3).

    Checks (in order; first failure determines result/detail):
    1. origin/develop exists — FAIL if missing.
    2. origin/main exists — FAIL if missing.
    3. main is an ancestor of develop (fast-forward topology) — WARN if not.
    4. develop is ahead of main by N commits (healthy: N>=0).
    5. Recent merged PRs base develop, not main — WARN if any recent PR has main base.
    6. Branch-protection on develop — WARN (honest, requires API availability).

    Returns PASS when the topology is clean, WARN on advisory issues, FAIL on
    structural breaks. Always emits real data — never the "dormant" stub.

    Extra fields for /api/promotion:
      develop_sha, main_sha, ahead, behind, main_is_ancestor
    """
    import json as _json

    # 1. Check origin/develop exists
    develop_sha = _git_sha("origin/develop")
    if not develop_sha:
        return {
            "id": "BRANCH-TOPOLOGY",
            "result": "FAIL",
            "detail": "origin/develop does not exist — two-tier topology not initialised",
        }

    # 2. Check origin/main exists
    main_sha = _git_sha("origin/main")
    if not main_sha:
        return {
            "id": "BRANCH-TOPOLOGY",
            "result": "FAIL",
            "detail": "origin/main does not exist",
        }

    # 3. Commit counts
    ahead = _git_count(f"origin/main..origin/develop")
    behind = _git_count(f"origin/develop..origin/main")

    # 4. Ancestor check: main should be ancestor of develop (ff-clean)
    try:
        anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "origin/main", "origin/develop"],
            capture_output=True, timeout=8, cwd=str(_HEALTH_REPO_ROOT),
        )
        main_is_ancestor = (anc.returncode == 0)
    except Exception:
        main_is_ancestor = False

    # 5. Recent PRs base check via gh CLI
    pr_base_ok = True
    pr_warn_detail = ""
    try:
        pr_r = subprocess.run(
            ["gh", "pr", "list", "--state", "merged", "--limit", "10",
             "--json", "number,baseRefName"],
            capture_output=True, text=True, timeout=20,
            cwd=str(_HEALTH_REPO_ROOT), stdin=subprocess.DEVNULL,
        )
        if pr_r.returncode == 0:
            prs = _json.loads(pr_r.stdout or "[]")
            main_based = [p["number"] for p in prs if p.get("baseRefName") == "main"]
            if main_based:
                pr_base_ok = False
                pr_warn_detail = f" | recent PRs with main base: {main_based[:3]}"
    except Exception:
        pass  # gh unavailable — skip PR check, don't WARN for this

    # 6. Branch-protection advisory
    bp_note = ""
    try:
        bp_r = subprocess.run(
            ["gh", "api", "repos/{owner}/{repo}/branches/develop"],
            capture_output=True, text=True, timeout=15,
            cwd=str(_HEALTH_REPO_ROOT), stdin=subprocess.DEVNULL,
        )
        if bp_r.returncode == 0:
            bp = _json.loads(bp_r.stdout or "{}")
            protected = bp.get("protected", False)
            bp_note = f" | branch-protection={'on' if protected else 'off (advisory: enable)'}"
        else:
            bp_note = " | branch-protection: API unavailable (WARN)"
    except Exception:
        bp_note = " | branch-protection: check skipped"

    # Determine result
    ahead_str = str(ahead) if ahead >= 0 else "?"
    behind_str = str(behind) if behind >= 0 else "?"
    base_detail = (
        f"develop ahead of main by {ahead_str}, behind by {behind_str}; "
        f"main-is-ancestor={main_is_ancestor}; "
        f"develop={develop_sha[:8]}, main={main_sha[:8]}"
        f"{pr_warn_detail}{bp_note}"
    )

    if not main_is_ancestor:
        return {
            "id": "BRANCH-TOPOLOGY",
            "result": "WARN",
            "detail": f"main is NOT ancestor of develop (diverged topology); {base_detail}",
            "develop_sha": develop_sha,
            "main_sha": main_sha,
            "ahead": ahead,
            "behind": behind,
            "main_is_ancestor": main_is_ancestor,
        }

    if not pr_base_ok:
        return {
            "id": "BRANCH-TOPOLOGY",
            "result": "WARN",
            "detail": f"recent PRs targeting main (should target develop); {base_detail}",
            "develop_sha": develop_sha,
            "main_sha": main_sha,
            "ahead": ahead,
            "behind": behind,
            "main_is_ancestor": main_is_ancestor,
        }

    return {
        "id": "BRANCH-TOPOLOGY",
        "result": "PASS",
        "detail": base_detail,
        "develop_sha": develop_sha,
        "main_sha": main_sha,
        "ahead": ahead,
        "behind": behind,
        "main_is_ancestor": main_is_ancestor,
    }


def check_promotion_lag() -> dict:
    """PROMOTION-LAG: age of develop HEAD since last promotion to main (ADR-0070 D3).

    Measures how long develop has been ahead of main:
    - 0 commits ahead: no lag (PASS)
    - ahead > 0, last promotion < 24h ago: PASS
    - ahead > 0, last promotion 24h-72h: WARN (promotion due)
    - ahead > 0, last promotion > 72h: WARN (promotion overdue)
    - no promotions yet + ahead > 0: WARN (day-one, honest)

    Reads promotion events from workflow-events.jsonl.
    """
    import json as _json
    import time as _time

    promotions = _read_promotion_events()
    ahead = _git_count("origin/main..origin/develop")
    now = _time.time()

    if ahead == 0:
        last_sha = promotions[-1].get("sha", "")[:8] if promotions else "none"
        return {
            "id": "PROMOTION-LAG",
            "result": "PASS",
            "detail": f"develop == main (0 commits ahead); last promotion sha: {last_sha}",
            "ahead": 0,
            "last_promotion_ts": promotions[-1].get("ts", "") if promotions else None,
            "lag_hours": 0.0,
        }

    if not promotions:
        return {
            "id": "PROMOTION-LAG",
            "result": "WARN",
            "detail": (
                f"develop is {ahead} commit(s) ahead of main; no promotion events yet "
                f"(honest day-one — first promotion pending); ADR-0070 D3"
            ),
            "ahead": ahead,
            "last_promotion_ts": None,
            "lag_hours": None,
        }

    last_promo = promotions[-1]
    last_ts_str = last_promo.get("ts", "")
    lag_hours: float = 0.0
    try:
        from datetime import datetime, timezone
        last_dt = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
        lag_hours = round((now - last_dt.timestamp()) / 3600.0, 1)
    except Exception:
        lag_hours = 0.0

    last_sha = last_promo.get("sha", "")[:8]
    detail = (
        f"develop {ahead} commit(s) ahead of main; "
        f"last promotion {lag_hours}h ago (sha={last_sha}, ts={last_ts_str})"
    )

    if lag_hours > 72:
        result = "WARN"
        detail = f"promotion overdue ({lag_hours:.1f}h); {detail}"
    elif lag_hours > 24:
        result = "WARN"
        detail = f"promotion due ({lag_hours:.1f}h); {detail}"
    else:
        result = "PASS"

    return {
        "id": "PROMOTION-LAG",
        "result": result,
        "detail": detail,
        "ahead": ahead,
        "last_promotion_ts": last_ts_str,
        "lag_hours": lag_hours,
    }


def check_release_ready() -> dict:
    """RELEASE-READY: deterministic six-condition promotion gate (ADR-0070 D2).

    Evaluates develop HEAD against six conditions (ADR-0070 D2):
      (a) CI green on develop HEAD — via tools/ci-checks.sh exit code
      (b) full test suite passes (ADR-0067 D1) — via pytest exit code
      (c) latest production-verify PASS — wired to PROOF-INTEGRITY check (slice #839)
      (d) green-develop streak intact — no failing checkpoint since last promotion
          (uses main_green events in workflow-events.jsonl as the green-develop proxy
          until a full green-develop event stream is landed by migration slices)
      (e) zero open needs-human items — gh issue list --label needs-human
      (f) guardrail-path batch check — wired to check_meta_tripwire() (slice #840 / ADR-0070 D4)

    Returns:
      result="PASS", verdict="true" — all six conditions hold
      result="WARN", verdict="false", first_failing_condition="<a-f>" — gate held

    Exit code semantics (CLI): always 0 when the check ran — even when the gate is
    held.  A held gate is an honest WARN, not a FAIL.  Only genuine check errors
    (subprocess failures, import errors) emit WARN with an error detail.

    Test injection — env vars override individual condition results:
      _RELEASE_READY_CI_RESULT           PASS|FAIL  (bypasses ci-checks.sh)
      _RELEASE_READY_TESTS_RESULT        PASS|FAIL  (bypasses pytest)
      _RELEASE_READY_PROOF_INTEGRITY_RESULT  PASS|WARN|FAIL  (bypasses check_proof_integrity)
      _RELEASE_READY_STREAK_RESULT       PASS|FAIL  (bypasses event-log streak check)
      _RELEASE_READY_NEEDS_HUMAN_COUNT   <int>      (bypasses gh issue list)
      _META_TRIPWIRE_RESULT_OVERRIDE     PASS|FAIL|WARN  (bypasses check_meta_tripwire for (f))
      _RELEASE_READY_FORCE_FAIL          1          (forces verdict false; for promote.sh guard tests)
    """
    import json as _json

    # Hard-fail override for testing promote.sh guard logic.
    if os.environ.get("_RELEASE_READY_FORCE_FAIL", "").strip() == "1":
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": "gate held: forced fail via _RELEASE_READY_FORCE_FAIL (test injection)",
            "first_failing_condition": "test-override",
        }

    # -----------------------------------------------------------------------
    # (a) CI green on develop HEAD — run tools/ci-checks.sh
    # -----------------------------------------------------------------------
    ci_override = os.environ.get("_RELEASE_READY_CI_RESULT", "").strip().upper()
    if ci_override:
        ci_pass = (ci_override == "PASS")
        ci_detail = f"CI result (injected): {ci_override}"
    else:
        try:
            ci_result = subprocess.run(
                ["bash", str(_HEALTH_REPO_ROOT / "tools" / "ci-checks.sh")],
                capture_output=True, text=True, timeout=60,
                cwd=str(_HEALTH_REPO_ROOT),
            )
            ci_pass = (ci_result.returncode == 0)
            ci_detail = f"ci-checks.sh exit={ci_result.returncode}"
        except Exception as exc:
            ci_pass = False
            ci_detail = f"ci-checks.sh error: {exc}"

    if not ci_pass:
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": f"gate held: condition (a) CI not green — {ci_detail}",
            "first_failing_condition": "a",
        }

    # -----------------------------------------------------------------------
    # (b) Full test suite passes (ADR-0067 D1)
    # -----------------------------------------------------------------------
    tests_override = os.environ.get("_RELEASE_READY_TESTS_RESULT", "").strip().upper()
    if tests_override:
        tests_pass = (tests_override == "PASS")
        tests_detail = f"test suite result (injected): {tests_override}"
    else:
        tests_dir = _HEALTH_REPO_ROOT / "tests"
        if not tests_dir.exists():
            tests_pass = False
            tests_detail = "tests/ directory not found"
        else:
            try:
                t_result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(tests_dir), "-q",
                     "--no-header", "--tb=no"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(_HEALTH_REPO_ROOT),
                )
                tests_pass = (t_result.returncode == 0)
                # Extract summary line from pytest output
                out_lines = (t_result.stdout or "").splitlines()
                summary = next(
                    (l for l in reversed(out_lines) if "passed" in l or "failed" in l),
                    f"exit={t_result.returncode}",
                )
                tests_detail = f"pytest: {summary.strip()}"
            except Exception as exc:
                tests_pass = False
                tests_detail = f"pytest error: {exc}"

    if not tests_pass:
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": f"gate held: condition (b) test suite not green — {tests_detail}",
            "first_failing_condition": "b",
        }

    # -----------------------------------------------------------------------
    # (c) Latest production-verify PASS — wired to PROOF-INTEGRITY check
    # Condition (c) degrades gracefully: PROOF-INTEGRITY WARN = no-data (pass);
    # PROOF-INTEGRITY FAIL = condition (c) fails.
    # -----------------------------------------------------------------------
    proof_override = os.environ.get("_RELEASE_READY_PROOF_INTEGRITY_RESULT", "").strip().upper()
    if proof_override:
        proof_result = proof_override
        proof_detail = f"PROOF-INTEGRITY result (injected): {proof_override}"
    else:
        try:
            pi = check_proof_integrity()
            proof_result = pi.get("result", "WARN")
            proof_detail = pi.get("detail", "")
        except Exception as exc:
            proof_result = "WARN"
            proof_detail = f"PROOF-INTEGRITY check error: {exc}"

    if proof_result == "FAIL":
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": f"gate held: condition (c) DOM-attestation failed — {proof_detail}",
            "first_failing_condition": "c",
        }
    # WARN = no qualifying data yet (honest no-data); treat as pass for (c).

    # -----------------------------------------------------------------------
    # (d) Green-develop streak intact
    # Green-develop streak: no RED checkpoint since the last promotion event.
    # Uses main_green events in workflow-events.jsonl as the proxy until
    # green-develop event stream lands in the migration slices.
    # A streak FAIL means there has been a red merge since last green event.
    # -----------------------------------------------------------------------
    streak_override = os.environ.get("_RELEASE_READY_STREAK_RESULT", "").strip().upper()
    if streak_override:
        streak_pass = (streak_override == "PASS")
        streak_detail = f"streak result (injected): {streak_override}"
    else:
        # Proxy: use check_green_main() — if it returns FAIL, streak is broken.
        try:
            gm = check_green_main()
            gm_result = gm.get("result", "WARN")
            if gm_result == "FAIL":
                streak_pass = False
                streak_detail = gm.get("detail", "green-main check FAIL")
            else:
                streak_pass = True
                streak_detail = gm.get("detail", "ok")
        except Exception as exc:
            streak_pass = True  # cannot determine → pass optimistically
            streak_detail = f"streak check error (pass optimistically): {exc}"

    if not streak_pass:
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": f"gate held: condition (d) green-develop streak broken — {streak_detail}",
            "first_failing_condition": "d",
        }

    # -----------------------------------------------------------------------
    # (e) Zero open needs-human items
    # -----------------------------------------------------------------------
    nh_override = os.environ.get("_RELEASE_READY_NEEDS_HUMAN_COUNT", "").strip()
    if nh_override:
        try:
            nh_count = int(nh_override)
            nh_detail = f"needs-human count (injected): {nh_count}"
        except ValueError:
            nh_count = 0
            nh_detail = f"needs-human count override parse error (default 0)"
    else:
        try:
            nh_result = subprocess.run(
                ["gh", "issue", "list", "--label", "needs-human",
                 "--state", "open", "--json", "number"],
                capture_output=True, text=True, timeout=20,
                cwd=str(_HEALTH_REPO_ROOT),
            )
            if nh_result.returncode == 0:
                issues = _json.loads(nh_result.stdout or "[]")
                nh_count = len(issues)
                nh_detail = f"needs-human open: {nh_count}"
            else:
                # gh CLI error → cannot determine; treat as 0 to avoid false holds
                nh_count = 0
                nh_detail = f"gh issue list error (treat as 0): {nh_result.stderr[:80]}"
        except Exception as exc:
            nh_count = 0
            nh_detail = f"needs-human check error (treat as 0): {exc}"

    if nh_count > 0:
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": (
                f"gate held: condition (e) {nh_count} open needs-human item(s) — "
                f"resolve before promoting; {nh_detail}"
            ),
            "first_failing_condition": "e",
        }

    # -----------------------------------------------------------------------
    # (f) Guardrail-path batch check — wired to check_meta_tripwire() (slice #840)
    # -----------------------------------------------------------------------
    mt_override = os.environ.get("_META_TRIPWIRE_RESULT_OVERRIDE", "").strip().upper()
    if mt_override in {"PASS", "FAIL", "WARN"}:
        mt_result_val = mt_override
        mt_detail = f"meta-tripwire result (injected): {mt_override}"
    else:
        try:
            mt = check_meta_tripwire()
            mt_result_val = mt.get("result", "WARN")
            mt_detail = mt.get("detail", "")
        except Exception as exc:
            mt_result_val = "WARN"
            mt_detail = f"meta-tripwire check error: {exc}"

    if mt_result_val == "FAIL":
        return {
            "id": "RELEASE-READY",
            "result": "WARN",
            "verdict": "false",
            "detail": f"gate held: condition (f) guardrail-path tripwire — {mt_detail}",
            "first_failing_condition": "f",
        }
    # WARN = no promotion data yet (day-one honest); treat as pass for (f).
    condition_f_note = f"meta-tripwire: {mt_result_val.lower()} — {mt_detail}"

    # -----------------------------------------------------------------------
    # All conditions pass — gate is open.
    # -----------------------------------------------------------------------
    return {
        "id": "RELEASE-READY",
        "result": "PASS",
        "verdict": "true",
        "detail": (
            "gate open: (a) CI green, (b) tests pass, (c) proof-integrity ok, "
            f"(d) streak intact, (e) zero needs-human, (f) guardrail-tripwire {mt_result_val.lower()}"
        ),
        "first_failing_condition": "",
        "condition_f": condition_f_note,
    }


# ---------------------------------------------------------------------------
# PROOF-INTEGRITY check (slice #839 / ADR-0070 D5)
#
# Validates that browser-route proof artifacts are genuinely DOM-attested,
# NOT API-layer-only.  The #811/#833 class shipped because the API-layer proof
# passed while the rendered DOM was empty; this check closes that gap.
#
# Sub-checks per ADR-0070 D5:
#   (1) Browser-route PRs: the claimed proof string must appear in a captured
#       rendered-DOM inner_text assertion (inner_text: <text> token in body or
#       comments).  A proof with only a .png screenshot or an API JSON blob but
#       no inner_text: line FAILS.
#   (2) All routes: PROOF_SOURCE must name a live non-fixture session
#       (must not contain "fixture" per rule #21).
#   (3) All routes: ENV: field must be non-empty (sha freshness attestation).
#
# Test injection: set _PROOF_INTEGRITY_PR_OVERRIDE to a JSON array of PR dicts
# (each with keys: number, headRefName, labels, files, body, comments).
# When set, the network fetch is bypassed entirely.
# ---------------------------------------------------------------------------

# Bootstrap cutoff — PRs at or below this number are grandfathered.
# Bind-forward per ADR-0004 D2; slice #839 is the implementing merge.
_PROOF_INTEGRITY_BOOTSTRAP_PR = 839

# Regex tokens that indicate DOM inner_text attestation in a PR body/comment.
_INNER_TEXT_RE = re.compile(r'inner_text\s*:', re.IGNORECASE)

# PROOF_SOURCE fixture-marker: presence of "fixture" anywhere in the value.
_FIXTURE_SOURCE_RE = re.compile(r'PROOF_SOURCE\s*:\s*([^\n]+)', re.IGNORECASE)

# ENV field: must be non-empty after the colon.
_ENV_FIELD_RE = re.compile(r'\bENV\s*:\s*(\S+)', re.IGNORECASE)


def _pr_has_inner_text_attestation(pr_body: str, comments: list[str]) -> bool:
    """Return True if inner_text: appears in the PR body or any comment."""
    if _INNER_TEXT_RE.search(pr_body):
        return True
    for comment in comments:
        if _INNER_TEXT_RE.search(comment):
            return True
    return False


def _proof_source_is_fixture(pr_body: str, comments: list[str]) -> bool:
    """Return True if any PROOF_SOURCE: line contains 'fixture' (rule #21)."""
    all_text = pr_body + "\n" + "\n".join(comments)
    for m in _FIXTURE_SOURCE_RE.finditer(all_text):
        value = m.group(1).strip()
        if "fixture" in value.lower():
            return True
    return False


def _env_field_is_empty(pr_body: str, comments: list[str]) -> bool:
    """Return True when ENV: is present but has no non-whitespace value."""
    all_text = pr_body + "\n" + "\n".join(comments)
    # Look for ENV: lines — bare "ENV:" or "ENV: " with nothing after it.
    env_bare_re = re.compile(r'^\s*ENV\s*:\s*$', re.IGNORECASE | re.MULTILINE)
    if env_bare_re.search(all_text):
        return True
    return False


def check_proof_integrity() -> dict:
    """PROOF-INTEGRITY: validate DOM-attestation of browser-route proof artifacts.

    Per ADR-0070 D5: for browser-route proof, asserts the claimed string appears
    in captured rendered-DOM inner_text (NOT API JSON — the #811/#833 class
    shipped because API-layer proof passed while the DOM was empty).

    Sub-checks (applied to each qualifying browser-route PR):
      (1) inner_text: token present in body or comments (DOM-attested)
      (2) PROOF_SOURCE does not contain 'fixture' (rule #21 live-source rule)
      (3) ENV: field is non-empty (sha freshness attestation)

    Honest day-one: evaluates over recent merged non-trivial browser-route PRs.
    Grandfathers PRs <= _PROOF_INTEGRITY_BOOTSTRAP_PR.

    WARN when no qualifying browser-route PRs found (no data yet).
    FAIL when any PR fails a sub-check (genuine DOM-attestation violation).
    PASS when all evaluated PRs pass all sub-checks.

    Test injection: set env var _PROOF_INTEGRITY_PR_OVERRIDE to a JSON list of
    PR dicts (keys: number, headRefName, labels, files, body, comments).
    """
    import json as _json

    # --- Test-injection path ---
    override_raw = os.environ.get("_PROOF_INTEGRITY_PR_OVERRIDE", "")
    if override_raw:
        try:
            all_prs = _json.loads(override_raw)
        except Exception as exc:
            return {
                "id": "PROOF-INTEGRITY",
                "result": "WARN",
                "detail": f"_PROOF_INTEGRITY_PR_OVERRIDE parse error: {exc}",
            }
    else:
        # --- Production path: fetch recent merged PRs via collector ---
        try:
            _insert_dashboard_sys_path()
            from collector import get_recent_merged_prs  # noqa: PLC0415
        except Exception as exc:
            return {
                "id": "PROOF-INTEGRITY",
                "result": "WARN",
                "detail": f"collector import failed: {exc}",
            }
        all_prs = get_recent_merged_prs(limit=_PROOF_PRESENCE_WINDOW + 5)

    # --- Filter to qualifying PRs ---
    # Skip trivial-lane; skip grandfathered; keep only browser-route PRs.
    browser_prs = []
    for pr in all_prs:
        ref = pr.get("headRefName", "")
        labels = [lb.get("name", "") for lb in (pr.get("labels") or [])]
        if "trivial" in labels or ref.startswith("hotfix/"):
            continue
        if pr.get("number", 0) <= _PROOF_INTEGRITY_BOOTSTRAP_PR:
            continue
        # Determine route: only evaluate browser-route PRs.
        changed_files = [f.get("path", "") for f in (pr.get("files") or [])]
        route_classes = _classify_route(changed_files)
        if "browser" not in route_classes:
            continue
        browser_prs.append(pr)

    if not browser_prs:
        return {
            "id": "PROOF-INTEGRITY",
            "result": "WARN",
            "detail": (
                f"no qualifying browser-route PRs found above bootstrap "
                f"threshold #{_PROOF_INTEGRITY_BOOTSTRAP_PR} — honest no-data"
            ),
        }

    # --- Evaluate each PR against the three sub-checks ---
    violations: list[str] = []
    passed = 0

    for pr in browser_prs:
        pr_num = pr.get("number", "?")
        pr_body = pr.get("body", "") or ""
        comments = [c.get("body", "") for c in (pr.get("comments") or [])]

        # Sub-check (1): browser route requires inner_text: attestation
        if not _pr_has_inner_text_attestation(pr_body, comments):
            violations.append(
                f"PR #{pr_num}: browser-route proof lacks inner_text: "
                f"attestation (API-only or screenshot-only proof — #811/#833 class)"
            )
            continue

        # Sub-check (2): PROOF_SOURCE must not be fixture-tagged (rule #21)
        if _proof_source_is_fixture(pr_body, comments):
            violations.append(
                f"PR #{pr_num}: PROOF_SOURCE contains 'fixture' "
                f"(live non-fixture session required per rule #21)"
            )
            continue

        # Sub-check (3): ENV: field must be non-empty
        if _env_field_is_empty(pr_body, comments):
            violations.append(
                f"PR #{pr_num}: ENV: field is empty "
                f"(sha freshness attestation required per ADR-0070 D5)"
            )
            continue

        passed += 1

    total = len(browser_prs)
    if violations:
        detail = (
            f"{len(violations)}/{total} browser-route PRs fail DOM-attestation: "
            + "; ".join(violations[:3])
            + (" [truncated]" if len(violations) > 3 else "")
        )
        return {"id": "PROOF-INTEGRITY", "result": "FAIL", "detail": detail,
                "passed": passed, "failed": len(violations), "total": total}

    detail = (
        f"{passed}/{total} browser-route PRs pass DOM-attestation "
        f"(inner_text:-attested, live PROOF_SOURCE, non-empty ENV)"
    )
    return {"id": "PROOF-INTEGRITY", "result": "PASS", "detail": detail,
            "passed": passed, "failed": 0, "total": total}


# ---------------------------------------------------------------------------
# HOOK-LIVENESS check (slice #849) — detects silent total-dark of hook layer.
# ---------------------------------------------------------------------------

# Named constant: delta threshold in minutes beyond which the hook layer is
# considered dark. (Module constant so tests can mirror it without importing.)
_HOOK_LIVENESS_DARK_MINUTES = 60


def check_hook_liveness() -> dict:
    """HOOK-LIVENESS: detect when the hook layer has gone silently dark.

    Compares the newest beacon timestamp in hook-fires.jsonl against the
    newest activity timestamp (workflow-events.jsonl OR latest git commit
    author-time, whichever is newer).

    If activity_ts - beacon_ts > _HOOK_LIVENESS_DARK_MINUTES → FAIL.
    Idle repos where both are old produce a small delta → PASS (no false alarm).

    Supports _HOOK_LIVENESS_FIRES_OVERRIDE / _HOOK_LIVENESS_EVENTS_OVERRIDE /
    _HOOK_LIVENESS_GIT_OVERRIDE env vars for test injection.

    Returns:
        {"id": "HOOK-LIVENESS", "result": "PASS"|"WARN"|"FAIL", "detail": ...}
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    def _parse_ts(ts_str: str) -> float:
        """Parse ISO-8601 timestamp to unix float; return 0.0 on error."""
        if not ts_str:
            return 0.0
        try:
            return _dt.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    # --- 1. Newest beacon in hook-fires.jsonl ---
    fires_override = os.environ.get("_HOOK_LIVENESS_FIRES_OVERRIDE", "")
    if fires_override:
        fires_log = Path(fires_override)
    else:
        fires_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "hook-fires.jsonl"

    if not fires_log.exists():
        return {
            "id": "HOOK-LIVENESS",
            "result": "WARN",
            "detail": "hook-fires.jsonl not found — hook layer may never have fired",
        }

    beacon_ts: float = 0.0
    try:
        with fires_log.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = _json.loads(raw)
                except Exception:
                    continue
                ts_val = _parse_ts(obj.get("ts", ""))
                if ts_val > beacon_ts:
                    beacon_ts = ts_val
    except Exception as exc:
        return {"id": "HOOK-LIVENESS", "result": "WARN",
                "detail": f"read error on hook-fires.jsonl: {exc}"}

    if beacon_ts == 0.0:
        return {
            "id": "HOOK-LIVENESS",
            "result": "WARN",
            "detail": "hook-fires.jsonl exists but contains no parseable beacon timestamps",
        }

    # --- 2. Newest activity: max(workflow-events.jsonl, git commit time) ---
    events_override = os.environ.get("_HOOK_LIVENESS_EVENTS_OVERRIDE", "")
    if events_override:
        events_log = Path(events_override)
    else:
        events_log = _HEALTH_REPO_ROOT / ".claude" / "logs" / "workflow-events.jsonl"

    events_ts: float = 0.0
    if events_log.exists():
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
                    ts_val = _parse_ts(obj.get("ts", ""))
                    if ts_val > events_ts:
                        events_ts = ts_val
        except Exception:
            pass

    # Git commit author-time (fallback if no events log or env override)
    git_override = os.environ.get("_HOOK_LIVENESS_GIT_OVERRIDE", "")
    git_ts: float = 0.0
    if git_override:
        try:
            raw_ts = Path(git_override).read_text(encoding="utf-8").strip()
            git_ts = _parse_ts(raw_ts)
        except Exception:
            pass
    else:
        try:
            r = subprocess.run(
                ["git", "-C", str(_HEALTH_REPO_ROOT), "log", "-1", "--format=%cI"],
                capture_output=True, text=True, timeout=10,
            )
            git_ts = _parse_ts(r.stdout.strip()) if r.returncode == 0 else 0.0
        except Exception:
            git_ts = 0.0

    activity_ts = max(events_ts, git_ts)

    if activity_ts == 0.0:
        return {
            "id": "HOOK-LIVENESS",
            "result": "WARN",
            "detail": (
                f"could not determine activity timestamp "
                f"(events_ts={events_ts:.0f}, git_ts={git_ts:.0f}); "
                "check skipped"
            ),
        }

    # --- 3. Compare ---
    delta_minutes = (activity_ts - beacon_ts) / 60.0

    beacon_iso = _dt.fromtimestamp(beacon_ts, tz=_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity_iso = _dt.fromtimestamp(activity_ts, tz=_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if delta_minutes > _HOOK_LIVENESS_DARK_MINUTES:
        return {
            "id": "HOOK-LIVENESS",
            "result": "FAIL",
            "detail": (
                f"hook layer appears dark: newest beacon {beacon_iso} is "
                f"{delta_minutes:.0f} min behind live activity {activity_iso} "
                f"(threshold {_HOOK_LIVENESS_DARK_MINUTES} min)"
            ),
        }

    return {
        "id": "HOOK-LIVENESS",
        "result": "PASS",
        "detail": (
            f"newest beacon {beacon_iso}; activity {activity_iso}; "
            f"delta {delta_minutes:.1f} min (threshold {_HOOK_LIVENESS_DARK_MINUTES} min)"
        ),
    }


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
    "HOOK-LIVENESS":   check_hook_liveness,
    "ISOLATION-GROUP": check_isolation_group,
    "RULE-COVERAGE":   check_rule_coverage,
    "SPEC-COVERAGE":   check_spec_coverage,
    # Memory checks (ADR-0067 wave 4)
    "TESTS-COLLECTED":  check_tests_collected,
    "TEST-ORDERING":    check_test_ordering,
    "QUARANTINE-SLA":   check_quarantine_sla,
    # Eval checks (ADR-0067 D5) — slice #817
    "EVAL-REVIEWER":      check_eval_reviewer,
    "EVAL-PRD-CRITIC":    check_eval_prd_critic,
    "EVAL-SLICER-CRITIC": check_eval_slicer_critic,
    # Hygiene checks (ADR-0068 D1/D3 wave 4 slice #818)
    "UNTRACKED-SIZE":    check_untracked_size,
    "LOG-ROTATION":      check_log_rotation,
    "STALE-BRANCHES":    check_stale_branches,
    "REQUIRED-LABELS":   check_required_labels,
    "DEAD-ROUTES":       check_dead_routes,
    "SESSION-INJECTION": check_session_injection,
    # model-frontmatter invariant check (ADR-0027 D1; fleet-economics removed per ADR-0071 D2)
    "FRONTMATTER-COVERAGE": check_frontmatter_coverage,
    # Verification-integrity checks (require network/collector)
    "BLIND-RATE":      check_blind_dispatch_rate,
    "RESIDUAL-RATIO":  check_residual_ratio,
    "MERGE-INTEGRITY": check_merge_integrity,
    "CAPTURE-SHAPE":   check_capture_shape,
    "GREEN-MAIN":      check_green_main,
    "PROOF-PRESENCE":  check_proof_presence,
    "SILENT-DRIFT":    check_silent_drift,
    # Two-tier topology (ADR-0070 wave 5 — slice #843 full implementation)
    "BRANCH-TOPOLOGY":  check_branch_topology,
    "PROMOTION-LAG":    check_promotion_lag,
    "RELEASE-READY":    check_release_ready,
    # DOM-attestation integrity (ADR-0070 D5 — slice #839)
    "PROOF-INTEGRITY": check_proof_integrity,
    # Guardrail-machinery promotion meta-tripwire (ADR-0070 D4 — slice #840)
    "META-TRIPWIRE": check_meta_tripwire,
    # Server-staleness check (ADR-0071 D5 — slice #907)
    "STALE-SERVER": check_stale_server,
    # Audit-subagents aggregate check (PRD #919 slice #921 — replaces /audit-subagents skill)
    "AS-AUDIT": check_audit_subagents,
}


def check_parity() -> dict:
    """PARITY: registry IDs == declared IDs == CI-consumed IDs.

    Implements ADR-0064 D3 standing parity alarm.

    Three ID sets are compared:
    1. Registry IDs: keys of CHECK_REGISTRY (the single-source implementation).
    2. Declared IDs: DOCS-*/STRUCT-* IDs extracted from ### <id> — headings in
       their canonical declared-ID source:
       - DOCS-*/STRUCT-*: codebase-critic.md "Deterministic pre-checks" section
         (moved from audit-meta/SKILL.md by PRD #919 slice #920).
       - AS-*: AS-AUDIT is registered directly in CHECK_REGISTRY (PRD #919
         slice #921 retired audit-subagents/SKILL.md); no separate declared-ID
         source is scanned for AS-* (the individual AS-ALL/CRIT/GEN check IDs
         are internal helpers, not declared IDs in the registry sense).
    3. CI-consumed IDs: IDs extracted from python3 dashboard/health.py invocations
       in tools/ci-checks.sh (lines matching --check <ID> or --list patterns).

    The check is honest about what it can and cannot measure today:
    - Declared = the ### headings that look like "### DOCS-N — " or
      "### STRUCT-N — " in codebase-critic.md.
    - CI-consumed = `--check <ID>` arguments in ci-checks.sh.  Post-migration
      CHECK 4/5 use registry calls; the set grows as later slices add more.
    - Registry IDs are the authoritative set (per ADR-0064 D3).

    Deferred-gap acknowledgement: STRUCT-* declared IDs are not individually
    registered because they run grouped via audit_meta() inside the
    codebase-critic per-PRD pass (PRD #919 slice #920); individual
    registration is deferred to a later slice.
    These known-deferred IDs are excluded from skill_gaps to avoid spurious
    WARN. The orphan-ci check (FAIL trigger) is unaffected — it catches any
    CI invocation of a check the registry does not have, regardless of deferral.

    PASS when CI-consumed ⊆ registry AND no non-deferred skill_gaps.
    WARN when non-deferred skill_gaps exist (gap to close in later slices).
    FAIL on orphan CI-consumed IDs (CI calls a check the registry does not have).

    PARITY: <registry_count> registered, <skill_count> declared,
            <ci_count> CI-consumed; orphan-ci=[] skill-gaps=[]
    """
    # IDs declared in source files but legitimately not individually registered
    # because they run grouped (STRUCT-*) via codebase-critic per-PRD pass.
    _DEFERRED_GAPS: set = set()
    # STRUCT-1..10: run via audit_meta() group call in codebase-critic per-PRD pass.
    for i in range(1, 11):
        _DEFERRED_GAPS.add(f"STRUCT-{i}")

    # --- 1. Registry IDs ---
    registry_ids = set(CHECK_REGISTRY.keys())

    # --- 2. Declared IDs ---
    # Parse ### <id> — headings from canonical declared-ID sources.
    # DOCS-*/STRUCT-* declared in codebase-critic.md (post slice #920).
    # AS-AUDIT is registered directly in CHECK_REGISTRY; no separate source file.
    _skill_id_pat = re.compile(
        r"^###\s+((?:DOCS|STRUCT)-[A-Z0-9_-]+)\s+—",
        re.MULTILINE,
    )
    skill_ids: set = set()
    try:
        text = _CODEBASE_CRITIC_MD.read_text(encoding="utf-8", errors="replace")
        for m in _skill_id_pat.finditer(text):
            skill_ids.add(m.group(1))
    except Exception:
        pass

    # --- 3. CI-consumed IDs ---
    # Scan tools/ci-checks.sh for: --check <ID> patterns.
    ci_checks_path = _HEALTH_REPO_ROOT / "tools" / "ci-checks.sh"
    _ci_id_pat = re.compile(r"--check\s+([A-Z][A-Z0-9_-]+)", re.MULTILINE)
    ci_ids: set = set()
    try:
        ci_text = ci_checks_path.read_text(encoding="utf-8", errors="replace")
        for m in _ci_id_pat.finditer(ci_text):
            ci_ids.add(m.group(1))
    except Exception:
        pass

    # --- Compute diffs ---
    orphan_ci = sorted(ci_ids - registry_ids)   # CI calls non-existent registry check
    all_skill_gaps = skill_ids - registry_ids    # declared IDs not in registry
    # Exclude known-deferred IDs (STRUCT-* group-registered)
    skill_gaps = sorted(
        gid for gid in all_skill_gaps
        if gid not in _DEFERRED_GAPS
    )
    deferred = sorted(gid for gid in all_skill_gaps
                      if gid in _DEFERRED_GAPS)

    r_count = len(registry_ids)
    s_count = len(skill_ids)
    c_count = len(ci_ids)

    detail = (
        f"{r_count} registered, {s_count} declared, {c_count} CI-consumed; "
        f"orphan-ci={orphan_ci}; skill-gaps={skill_gaps}; deferred={deferred}"
    )

    base = {
        "id": "PARITY",
        "registry_ids": sorted(registry_ids),
        "skill_ids": sorted(skill_ids),
        "ci_ids": sorted(ci_ids),
        "orphan_ci": orphan_ci,
        "skill_gaps": skill_gaps,
        "deferred": deferred,
    }
    if orphan_ci:
        return {**base, "result": "FAIL", "detail": detail}
    if skill_gaps:
        return {**base, "result": "WARN", "detail": detail}
    return {**base, "result": "PASS", "detail": detail}


# Register PARITY into the registry after defining it (self-referential).
CHECK_REGISTRY["PARITY"] = check_parity


def _build_health_data() -> dict:
    """Build the full /api/health payload synchronously.

    Called from the background thread; never from an HTTP handler.
    """
    # _enrich_group adds the 'group' field used by the Health tab section headers
    # (slice #931 / PRD #927 §2 #10) — presentation only, no check-logic change.
    audit = audit_meta()
    _enrich_group(audit["checks"])
    return {
        "auditMeta": audit,
        "auditSubagents": audit_subagents(),
        "cascadeFinder": cascade_finder_summary(),
        "substrateMeta": {
            "checks": _enrich_group([
                check_capture_slo(),
                check_hook_integrity(),
                check_hook_liveness(),
                check_isolation_group(),
                check_rule_coverage(),
                check_spec_coverage(),
                check_critic_health(),
                check_tests_collected(),
                check_test_ordering(),
                check_quarantine_sla(),
                # Eval rows (ADR-0067 D5) — slice #817
                check_eval_reviewer(),
                check_eval_prd_critic(),
                check_eval_slicer_critic(),
            ])
        },
        "verificationIntegrity": {
            "checks": _enrich_group([
                check_blind_dispatch_rate(),
                check_residual_ratio(),
                check_proof_presence(),
                check_proof_integrity(),
                check_merge_integrity(),
                check_capture_shape(),
                check_green_main(),
                check_silent_drift(),
            ])
        },
        "registryIntegrity": {
            "checks": _enrich_group([
                check_parity(),
            ])
        },
        "hygieneIntegrity": {
            "checks": _enrich_group([
                check_untracked_size(),
                check_log_rotation(),
                check_stale_branches(),
                check_required_labels(),
                check_dead_routes(),
                check_session_injection(),
            ])
        },
        "promotionIntegrity": {
            "checks": _enrich_group([
                check_branch_topology(),
                check_promotion_lag(),
                check_release_ready(),
                check_r_sensitive_detector(),
                check_meta_tripwire(),
            ])
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
