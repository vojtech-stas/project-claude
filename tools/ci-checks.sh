#!/usr/bin/env bash
# tools/ci-checks.sh — deterministic CI gate for project-claude.
#
# Runnable locally and in GitHub Actions (see .github/workflows/ci.yml).
# Exits 0 if all checks pass; exits 1 if any check fails.
# ADR-0042 D1 — mechanical CI gate; mirrors audit-meta DOCS-1/DOCS-2/DOCS-7
# logic + ADR-0041 D2 origin/main base for commit-range checks.
#
# Usage: bash tools/ci-checks.sh
#   (run from the repo root)

set -euo pipefail

FAIL_COUNT=0

fail() {
    echo "FAIL: $*" >&2
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

pass() {
    echo "PASS: $*"
}

# ---------------------------------------------------------------------------
# CHECK 1: settings.json valid JSON
# ---------------------------------------------------------------------------
echo "--- CHECK 1: .claude/settings.json valid JSON ---"
if python3 -m json.tool .claude/settings.json > /dev/null 2>&1; then
    pass ".claude/settings.json is valid JSON"
else
    fail ".claude/settings.json is not valid JSON"
fi

# ---------------------------------------------------------------------------
# CHECK 2: README regen-clean
# ---------------------------------------------------------------------------
echo "--- CHECK 2: README regen-clean ---"
if command -v python3 > /dev/null 2>&1 && [ -f "dashboard/server.py" ]; then
    python3 dashboard/server.py --generate-readme > /dev/null 2>&1
    if git diff --exit-code README.md > /dev/null 2>&1; then
        pass "README.md is up-to-date with regen output"
    else
        fail "README.md is stale — run 'python3 dashboard/server.py --generate-readme' and commit"
        # restore to not pollute diff output for other checks
        git checkout -- README.md 2>/dev/null || true
    fi
else
    echo "SKIP: CHECK 2 — python3 or dashboard/server.py not available (soft-degrade)"
fi

# ---------------------------------------------------------------------------
# CHECK 3: Commit subjects — ≤72 chars + Conventional Commits format
# ---------------------------------------------------------------------------
echo "--- CHECK 3: commit subjects over origin/main..HEAD ---"
# Fetch origin/main so the range is available in CI (ADR-0041 D2).
git fetch origin main --quiet 2>/dev/null || true

CONV_RE='^(feat|fix|chore|refactor|docs|test|perf|style|build|ci|hotfix)(\(.+\))?: .+'
RANGE_COMMITS=$(git log --format='%s' origin/main..HEAD 2>/dev/null || true)

if [ -z "$RANGE_COMMITS" ]; then
    pass "no commits ahead of origin/main — nothing to check"
else
    CHECK3_FAIL=0
    while IFS= read -r subject; do
        [ -z "$subject" ] && continue
        # Length check
        len=${#subject}
        if [ "$len" -gt 72 ]; then
            fail "commit subject exceeds 72 chars ($len): $subject"
            CHECK3_FAIL=1
        fi
        # Conventional Commits format
        if ! printf '%s' "$subject" | grep -qE "$CONV_RE"; then
            fail "commit subject not Conventional Commits format: $subject"
            CHECK3_FAIL=1
        fi
    done <<< "$RANGE_COMMITS"
    if [ "$CHECK3_FAIL" -eq 0 ]; then
        pass "all commit subjects pass length + Conventional Commits check"
    fi
fi

# ---------------------------------------------------------------------------
# CHECK 4: Dangling ADR links (DOCS-7 mechanic)
# ---------------------------------------------------------------------------
echo "--- CHECK 4: dangling decisions/NNNN-*.md links in tracked .md files ---"
# Fake/pedagogical slugs to ignore (mirrors audit-meta DOCS-7 allowlist).
FAKE_SLUG_RE='decisions/00[0-9]{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md'

CHECK4_FAIL=0
# Find all tracked .md files (excluding .git).
while IFS= read -r mdfile; do
    [ -f "$mdfile" ] || continue
    # Extract all decisions/NNNN-*.md targets from this file.
    while IFS= read -r target; do
        [ -z "$target" ] && continue
        # Skip fake/example slugs.
        if printf '%s' "$target" | grep -qE "$FAKE_SLUG_RE"; then
            continue
        fi
        if [ ! -f "$target" ]; then
            fail "dangling ADR link '$target' in $mdfile"
            CHECK4_FAIL=1
        fi
    done < <(grep -oE 'decisions/[0-9]{4}-[a-z0-9-]+\.md' "$mdfile" 2>/dev/null || true)
done < <(git ls-files '*.md' 2>/dev/null)

if [ "$CHECK4_FAIL" -eq 0 ]; then
    pass "no dangling decisions/NNNN-*.md links found"
fi

# ---------------------------------------------------------------------------
# CHECK 5: decisions/README.md <-> decisions/[0-9]*.md index consistency
# ---------------------------------------------------------------------------
echo "--- CHECK 5: decisions/README.md <-> decisions/*.md index consistency ---"
CHECK5_FAIL=0

# DOCS-1: every index row resolves to an existing file.
while IFS= read -r target; do
    [ -z "$target" ] && continue
    if [ ! -f "decisions/$target" ]; then
        fail "decisions/README.md row references missing file: decisions/$target"
        CHECK5_FAIL=1
    fi
done < <(grep -oE '[0-9]{4}-[a-z0-9-]+\.md' decisions/README.md 2>/dev/null || true)

# DOCS-2: every ADR file on disk has a row in decisions/README.md.
for adrfile in decisions/[0-9]*.md; do
    [ -f "$adrfile" ] || continue
    basename_adr=$(basename "$adrfile")
    if ! grep -qF "$basename_adr" decisions/README.md 2>/dev/null; then
        fail "decisions/README.md missing index row for: $adrfile"
        CHECK5_FAIL=1
    fi
done

if [ "$CHECK5_FAIL" -eq 0 ]; then
    pass "decisions/README.md index is consistent with decisions/*.md on disk"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "--- CI SUMMARY ---"
if [ "$FAIL_COUNT" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "FAILED: $FAIL_COUNT check(s) failed" >&2
    exit 1
fi
