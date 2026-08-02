#!/usr/bin/env bash
# tools/ci-failure-kind.sh — classify a failed GitHub Actions `ci` run as
# "format" (the #869 commit-subject-format class, CHECK 3) or "other" (any
# other tools/ci-checks.sh check).
#
# Extracted from .claude/skills/ship/SKILL.md's pre-review CI gate (stage
# 5c, PRD #1075 criterion 6 / slice #1084) after a reviewer BLOCK (PR #1087
# round 1) proved the original inline classifier broken:
#   gh run view "$RUN_ID" --log-failed | grep -q "CHECK 3"
# tools/ci-checks.sh intentionally omits `set -e` and always runs all 20
# checks regardless of earlier failures (its own header comment); CHECK 3's
# section header (`echo "--- CHECK 3: commit subjects ... ---"`) therefore
# prints on EVERY run whether or not CHECK 3 itself fails. A bare grep for
# the literal string "CHECK 3" matches on that always-present header (and
# on unrelated pytest test-case names that happen to mention "CHECK 3"),
# so it misclassified ANY ci-checks.sh failure as the format class —
# verified empirically by the reviewer against real historical run
# 28578918251 (a genuine CHECK 12 failure; CHECK 3 itself passed).
#
# The real CHECK-3-specific evidence is its FAIL: line, emitted ONLY when
# CHECK 3 itself fails (see tools/ci-checks.sh's `fail()` call sites):
#   FAIL: commit subject exceeds 72 chars (<N>): <subject>
#   FAIL: commit subject not Conventional Commits format: <subject>
#
# Usage:
#   tools/ci-failure-kind.sh <run-id>              # live gh lookup
#   tools/ci-failure-kind.sh --from-file <logfile>  # offline / test mode
#
# Prints exactly one word to stdout: "format" or "other". Exit 0 on a
# successful classification (either word); exit 2 on a usage error
# (missing/invalid argument). This is a classifier, not a pass/fail gate —
# callers (ship/SKILL.md) decide what to do with the printed word.

set -uo pipefail

# CHECK-3-specific FAIL: line signature (tools/ci-checks.sh's two `fail()`
# call sites for CHECK 3) — matches ONLY a genuine CHECK 3 failure, never
# the always-present section header or unrelated "CHECK 3" substring
# mentions elsewhere in a run's log (e.g. pytest test-case names).
FORMAT_PATTERN='FAIL: commit subject (exceeds 72 chars|not Conventional Commits format)'

usage() {
    echo "usage: tools/ci-failure-kind.sh <run-id> | --from-file <log-file>" >&2
}

if [ "${1:-}" = "--from-file" ]; then
    LOG_FILE="${2:-}"
    if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
        usage
        exit 2
    fi
    if grep -qE "$FORMAT_PATTERN" "$LOG_FILE"; then
        echo "format"
    else
        echo "other"
    fi
    exit 0
fi

RUN_ID="${1:-}"
if [ -z "$RUN_ID" ]; then
    usage
    exit 2
fi

if gh run view "$RUN_ID" --log-failed 2>&1 | grep -qE "$FORMAT_PATTERN"; then
    echo "format"
else
    echo "other"
fi
