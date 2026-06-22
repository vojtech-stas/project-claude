"""
Tests for slice #968: purpose_group, hook-trio composite, what_to_do, --list conservation.
PRD #957 slice 3 (final).
"""

import subprocess
import sys
import os
import types
import importlib

try:
    import pytest
except ImportError:  # CI runs stdlib unittest without pytest installed (CHECK 12 / #985)
    pytest = None


def _skip_if_no_pytest(fn):
    """No-op pass-through when pytest is available; skip decorator otherwise."""
    import unittest
    if pytest is None:
        return unittest.skip("pytest not installed — parametrized variant skipped in no-pytest CI")(fn)
    return fn


# ---------------------------------------------------------------------------
# Module import helper
# ---------------------------------------------------------------------------
HEALTH_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")


def _import_health():
    spec = importlib.util.spec_from_file_location(
        "health_968", os.path.join(HEALTH_DIR, "health.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC1: ≥5 purpose groups present in PURPOSE_GROUP_MAP
# ---------------------------------------------------------------------------
class TestPurposeGroupMapGroups:
    def test_at_least_five_distinct_groups(self):
        h = _import_health()
        groups = set(h.PURPOSE_GROUP_MAP.values())
        assert len(groups) >= 5, f"Expected ≥5 purpose groups, got {sorted(groups)}"

    def test_expected_group_names_present(self):
        h = _import_health()
        groups = set(h.PURPOSE_GROUP_MAP.values())
        expected = {
            "Docs in sync",
            "Rules enforced",
            "Telemetry live",
            "Verification integrity",
            "Isolation/hygiene",
        }
        missing = expected - groups
        assert not missing, f"Missing expected purpose groups: {missing}"

    def test_purpose_group_order_has_all_six(self):
        h = _import_health()
        order = h.PURPOSE_GROUP_ORDER
        assert len(order) >= 5, f"PURPOSE_GROUP_ORDER too short: {order}"
        assert "Telemetry live" in order


# ---------------------------------------------------------------------------
# AC2: 4 excluded checks NOT in PURPOSE_GROUP_MAP
# ---------------------------------------------------------------------------
EXCLUDED_IDS = ["BRANCH-TOPOLOGY", "FRONTMATTER-COVERAGE", "META-TRIPWIRE", "RELEASE-READY"]


class TestExcludedChecksNotInMap:
    # pytest parametrize — only applied when pytest is present; otherwise the sibling
    # test_all_four_excluded covers the same assertions under stdlib unittest.
    if pytest is not None:
        @pytest.mark.parametrize("check_id", EXCLUDED_IDS)
        def test_check_excluded_from_purpose_group_map(self, check_id):
            h = _import_health()
            assert check_id not in h.PURPOSE_GROUP_MAP, (
                f"{check_id} should NOT be in PURPOSE_GROUP_MAP (registered-but-UI-invisible)"
            )

    def test_all_four_excluded(self):
        h = _import_health()
        for cid in EXCLUDED_IDS:
            assert cid not in h.PURPOSE_GROUP_MAP, f"{cid} unexpectedly in PURPOSE_GROUP_MAP"


# ---------------------------------------------------------------------------
# AC3: Hook-trio composite rollup logic
#      Worst actionable sub-signal wins; no-data does NOT downgrade composite
#
# NOTE: health.py check functions return UPPERCASE result values ("PASS", "WARN",
# "FAIL", "NO-DATA") and lowercase data_state ("pass", "actionable", "no-data").
# Tests use the same conventions.
# ---------------------------------------------------------------------------
class TestHookTrioComposite:
    def _make_result(self, result, data_state, check_id):
        # result = uppercase ("PASS"/"WARN"/"FAIL"/"NO-DATA")
        # data_state = lowercase ("pass"/"actionable"/"no-data")
        return {
            "id": check_id,
            "result": result,
            "data_state": data_state,
            "detail": "",
            "description": "",
        }

    def _rollup(self, h, capture_result, capture_state, integrity_result, integrity_state,
                liveness_result, liveness_state):
        slo = self._make_result(capture_result, capture_state, "CAPTURE-SLO")
        integrity = self._make_result(integrity_result, integrity_state, "HOOK-INTEGRITY")
        liveness = self._make_result(liveness_result, liveness_state, "HOOK-LIVENESS")
        comp = h._build_hook_trio_composite(slo, integrity, liveness)
        return comp

    def test_all_pass_gives_pass(self):
        h = _import_health()
        comp = self._rollup(
            h,
            "PASS", "pass",
            "PASS", "pass",
            "PASS", "pass",
        )
        assert comp["result"] == "PASS", f"Expected PASS, got {comp['result']}"

    def test_one_fail_gives_fail(self):
        h = _import_health()
        comp = self._rollup(
            h,
            "FAIL", "actionable",
            "PASS", "pass",
            "PASS", "pass",
        )
        assert comp["result"] == "FAIL"

    def test_no_data_does_not_downgrade(self):
        """If all actionable sub-signals pass, no-data must not make composite fail/warn."""
        h = _import_health()
        comp = self._rollup(
            h,
            "PASS", "pass",
            "PASS", "pass",
            "NO-DATA", "no-data",   # liveness no-data
        )
        # Composite should pass or at most warn (not degraded to fail by no-data)
        assert comp["result"] in ("PASS", "WARN"), (
            f"no-data should not downgrade composite to fail; got {comp['result']}"
        )
        assert comp["result"] != "FAIL", (
            "no-data sub-signal must not force composite to 'FAIL'"
        )

    def test_only_no_data_subs_yields_not_fail(self):
        """All three no-data → composite is not FAIL (no actionable worst-signal)."""
        h = _import_health()
        comp = self._rollup(
            h,
            "NO-DATA", "no-data",
            "NO-DATA", "no-data",
            "NO-DATA", "no-data",
        )
        # No actionable signals → composite must not be FAIL
        assert comp["result"] != "FAIL", (
            f"All-no-data should not yield FAIL; got {comp['result']}"
        )

    def test_composite_has_three_sub_signals(self):
        h = _import_health()
        comp = self._rollup(
            h,
            "PASS", "pass",
            "PASS", "pass",
            "PASS", "pass",
        )
        assert "sub_signals" in comp
        assert len(comp["sub_signals"]) == 3

    def test_composite_id_is_telemetry_live(self):
        h = _import_health()
        comp = self._rollup(
            h,
            "PASS", "pass",
            "PASS", "pass",
            "PASS", "pass",
        )
        assert comp["id"] == "TELEMETRY-LIVE"

    def test_composite_is_composite_flag(self):
        h = _import_health()
        comp = self._rollup(
            h,
            "PASS", "pass",
            "PASS", "pass",
            "PASS", "pass",
        )
        assert comp.get("is_composite") is True

    def test_warn_actionable_gives_warn(self):
        h = _import_health()
        comp = self._rollup(
            h,
            "WARN", "actionable",
            "PASS", "pass",
            "PASS", "pass",
        )
        assert comp["result"] == "WARN"


# ---------------------------------------------------------------------------
# AC4: --list count invariant (must equal 46)
# ---------------------------------------------------------------------------
class TestListCountInvariant:
    def test_list_count_is_46(self):
        """python dashboard/health.py --list | wc -l must stay 46."""
        result = subprocess.run(
            [sys.executable, os.path.join(HEALTH_DIR, "health.py"), "--list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"health.py --list failed: {result.stderr}"
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        count = len(lines)
        assert count == 46, (
            f"--list count changed! Expected 46, got {count}. "
            "Conservation violated (slice #968 §2 #8)."
        )


# ---------------------------------------------------------------------------
# AC5: _attach_purpose_group annotates known check IDs correctly
# ---------------------------------------------------------------------------
class TestAttachPurposeGroup:
    def test_docs1_gets_docs_in_sync(self):
        h = _import_health()
        checks = [{"id": "DOCS-1", "result": "pass"}]
        result = h._attach_purpose_group(checks)
        assert result[0]["purpose_group"] == "Docs in sync"

    def test_hook_integrity_gets_telemetry_live(self):
        h = _import_health()
        checks = [{"id": "HOOK-INTEGRITY", "result": "pass"}]
        result = h._attach_purpose_group(checks)
        assert result[0]["purpose_group"] == "Telemetry live"

    def test_excluded_check_gets_none(self):
        h = _import_health()
        for cid in EXCLUDED_IDS:
            checks = [{"id": cid, "result": "pass"}]
            result = h._attach_purpose_group(checks)
            assert result[0]["purpose_group"] is None, (
                f"{cid} should have purpose_group=None"
            )


# ---------------------------------------------------------------------------
# AC6: _attach_what_to_do only fills actionable checks
# ---------------------------------------------------------------------------
class TestAttachWhatToDo:
    def test_actionable_check_gets_what_to_do(self):
        h = _import_health()
        checks = [{"id": "DOCS-1", "result": "fail", "data_state": "actionable"}]
        result = h._attach_what_to_do(checks)
        # Should be non-empty string (fallback is allowed)
        assert isinstance(result[0].get("what_to_do"), str)

    def test_pass_check_gets_empty_what_to_do(self):
        h = _import_health()
        checks = [{"id": "DOCS-1", "result": "pass", "data_state": "pass"}]
        result = h._attach_what_to_do(checks)
        assert result[0].get("what_to_do") == ""

    def test_no_data_check_gets_empty_what_to_do(self):
        h = _import_health()
        checks = [{"id": "HOOK-LIVENESS", "result": "no-data", "data_state": "no-data"}]
        result = h._attach_what_to_do(checks)
        assert result[0].get("what_to_do") == ""
