---
id: "ADR-0079"
title: "Post-merge verification trusts recorded CI; per-call hook overhead diet"
status: "accepted"
date: "2026-08-20"
scope: "pipeline"
rule_ids:
  - "PIP-023"
supersedes: []
superseded_by: []
---

# 0079 — Post-merge verification trusts recorded CI; per-call hook overhead diet

Status: Accepted
Date: 2026-08-20
**Extends/narrows:** ADR-0062 D3 (post-merge green verification — its always-run local re-run mandate is narrowed to the no-recorded-evidence fallback), ADR-0075 D3 (which wrapped tools/record-green.sh into tools/pipe/record-green — the mechanism D1 documents and modifies), ADR-0077 (ceremony-overhead reduction — this is its measured second phase), ADR-0057 D1 (fail-loud beacons — extended with an outcome field), ADR-0068 D3 (session-start context injection — its implementation gains concurrency, its contract is unchanged)

**Bootstrap-mode (ADR-0004 D2):** binds forward from the merge of its PRD's slices; no retroactive sweep.

## Context

The 2026-08-20 full-component audit measured where pipeline wall-time actually goes. Three findings motivate this decision. (1) The full pytest suite (336 s local) runs ≥3× per merged slice; the post-merge run mandated by ADR-0062 D3 re-verifies a sha for which a recorded GitHub CI conclusion already exists — the same evidence class that record-green.sh and RELEASE-READY conditions (a)/(b) ALREADY trust — root-cause issue #1161 (GREEN-FAST), shipped via PR #1163, formalized by no ADR until this one. An adversarial refutation of "drop the post-merge run" was UPHELD with the constraint that the implementer's pre-push run must stay (its sha is unpushed, so no recorded run can exist). (2) PR #1190/#1191 proved a residual sha-attribution gap live: record-green now certifies the correct sha, but `health.py::_fetch_github_ci_conclusion` re-derives its own sha from a possibly-unfetched local ref, so the CI evidence cited a neighbouring PR's run (#1192, third site of the stale-local-ref class). (3) The deny-guard costs ~652 ms on every Bash tool call (eight sequential `jq` spawns on the allow path: one command extraction, two shape validations, five per-flag reads) and its beacon records no outcome, so its real-world deny history is unmeasurable; session-start's five serial `gh` queries cost ~11.4 s per session start.

## Decisions

### D1 — Post-merge green evidence is the recorded CI conclusion for the exact merged sha; the redundant SKILL-mandated re-run is deleted

The recorded-CI trust itself is NOT new: `tools/record-green.sh` and RELEASE-READY conditions (a)/(b) already skip the local suite on a recorded GitHub `ci=pass` for the exact sha — shipped under #1161 and formalized by no ADR until this one. D1's net-new decision is twofold. (a) That precedent is DOCUMENTED here as the pipeline's evidence model: recorded conclusion for the exact certified sha (PR-mergeCommit lookup); local run only on `unavailable`; refusal on `fail`/`pending`. (b) The separate, ALWAYS-RUN `bash tools/ci-checks.sh` step that ADR-0062 D3's literal prose still mandates at three sites — `ship/SKILL.md` step 5c-4 (~line 175, per merge), `ship/SKILL.md` step 5f (~line 184, per batch), and `build/SKILL.md`'s post-merge block (~line 190) — is DELETED in the same PR that lands this ADR, because record-green's own #1161 logic already performs the equivalent verification against recorded evidence. The implementer's pre-push gate is unchanged — an unpushed sha can have no recorded run.

**Enforcement (rule #23):** PIP-023 (this ADR's rule_ids) + the existing RECORD-VS-GH reconciler; the repointed `ship`/`build` prose is deleted in the same PR that lands the behavior (ADR-0076 D5 pattern, reviewer-checkable grep count=0); regression tests assert the no-re-run path on recorded pass and the fallback on unavailable.

### D2 — CI-trust evidence must cite the sha it certifies

Every CI-conclusion lookup used as verification evidence receives the certified sha explicitly and cites that sha's run; deriving the sha internally from a local ref is forbidden on evidence paths. A mismatch between the certified sha and the sha whose run supplied the evidence REFUSES rather than proceeds. This closes the #1192 site and the class (#1183 fixed the emitter; this fixes the evidence).

**Enforcement (rule #23):** regression test — certify sha X while local `origin/develop` points at Y: evidence must cite X or refuse (REG-002 test-first rider applies; this is a code defect fix). Parsimony note: the existing RECORD-VS-GH reconciler catches a MISSING green span for a merged sha; nothing today catches a PRESENT span whose CI evidence is misattributed to a neighbouring sha — that gap is exactly what this test pins.

### D3 — Hook overhead diet with an outcome-carrying beacon

`pre-tool-bash.sh` consolidates its payload parsing into a single spawn (target: ≤~350 ms allow-path median, from ~652 ms) and its beacon gains an `outcome` field (`deny`|`warn`|`allow`), making real deny history measurable for the first time. `session-start.sh` runs its five `gh` queries concurrently (target: ≤~4 s median, from ~11.4 s). Contracts preserved exactly: HOK-008 attempt-beacon-first and ERROR-on-internal-error; deny/warn semantics and clause-anchoring behavior byte-equivalent; CI-tested literals in session-start.sh; v2 event shapes unchanged.

**Enforcement (rule #23):** existing deny-guard regression suite must pass unmodified (a weakened test is a reviewer BLOCK); new timed-fire assertions with generous CI margins; HOOK-INTEGRITY pairing unchanged.

## Consequences

- A merged slice stops paying ~5.6 min of redundant local suite wall; the suite still gates every push (pre-push) and every PR (GitHub CI).
- Green evidence becomes attributable: the certified sha, the CI run cited, and the span all name the same commit — the reconcilers can finally cross-check them mechanically.
- The deny-guard's insurance value becomes measurable (outcome field) instead of asserted.
- Session start drops ~8 s; the injected context is unchanged, so nothing downstream notices.
- Risk accepted: recorded-CI trust inherits GitHub's availability; the `unavailable` fallback keeps offline merges verifiable at the old cost.

## Alternatives considered

- **Keep the post-merge local run:** measured ~0 marginal safety (same sha, same suite, evidence already recorded) at ~5.6 min/slice; rejected.
- **Drop the implementer pre-push run too:** refuted — the pre-push sha has no recorded run yet; rejected as unsound.
- **Speed the suite instead (fixture-ize the two 100 s tests):** superseded by the approved frontend cut, which deletes those tests' subject entirely; doing both was wasted motion.
- **Rewrite hooks in a faster runtime:** unjustified while a single-spawn consolidation reaches the target; revisit only if measurements say otherwise.

## References

- ADR-0062 D3 (narrowed), ADR-0075 D3 (record-green wrapper mechanism), ADR-0077 (phase 1), ADR-0057 D1 / ADR-0068 D3 (contracts preserved), ADR-0076 D5 (prose-shrink pattern)
- Issues: #1161 (the shipped-but-undocumented CI-trust precedent D1 formalizes; landed via PR #1163), #1134/PR #1148 (the pr-merge record-green chain the fast path accelerates), #1192 (D2's instance), #1183/PR #1190 + PR #1191 (live proof pair), #1122 (the budget class #1161 killed)
- 2026-08-20 audit: measured 336 s suite × ≥3 runs/slice; 652 ms/Bash call; 11.4 s session start
