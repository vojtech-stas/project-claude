---
id: "ADR-0076"
status: "accepted"
supersedes: []
superseded_by: []
scope: "pipeline"
rule_ids:
  - "PIP-014"
  - "PIP-015"
  - "PIP-016"
  - "PIP-017"
  - "PIP-018"
  - "PIP-019"
---
# 0076 — Guarded-verb pipeline engine: verbs as the sole mechanical-transition path

Status: Accepted
Date: 2026-08-02
**Extends:** ADR-0075 D3 (side-effect wrapper emitters — completed here into the full verb set), ADR-0075 D5 (blocking-day-1 for incident-proven classes — the deny set below inherits that posture), ADR-0070 D1 (two-tier delivery — the merge/promotion gates this engine feeds), ADR-0004 D2 (bootstrap-mode — see binding paragraph below)

**Bootstrap-mode (ADR-0004 D2):** every decision below binds FORWARD from the merge of this PRD's slice 1. All pre-anchor history is grandfathered: no retroactive spans are fabricated, dispatches and merges that predate the anchor carry no `dispatch`/`verdict` spans, and the MERGED-WITHOUT-VERDICT and CLOSED-PRD-VS-QA reconcilers evaluate only post-anchor artifacts (mirroring RECORD-VS-GH's anchored window with its documented grandfathered set). The permanent gap is named, not hidden: pre-anchor merges will forever lack verdict spans, and the reconcilers say so rather than alarm on them.

## Context

PRD #1075 (per ADR-0075) shipped the recorded-trace core: five side-effect wrappers whose spans are atomic with their gh actions. In their live window the wrappers achieved 100% recorded compliance (every post-anchor merge carries its span; the mechanism survived a real false-negative incident, #1100), while every prose-remembered obligation in the same window measured at or near 0% (zero ship-state-`<prd>`.json files ever written against a standing mandate; 34 green events lifetime against hundreds of merges before the wrapper; ADR-0056's measured 0–17% prose-rule compliance). Meanwhile the transitions BETWEEN the recorded anchors remain unenforced: dispatch is untraced and unvalidated (#918 class — ~16 hand-created slices), merge-to-develop requires no reviewer verdict anywhere (develop branch protection: HTTP 404; `tools/pipe/pr-merge` checks CI and merged-state but never a verdict — the G2 gap), PRD closure requires no verification evidence, and the batch queue exists only in conversation context. The operator locked the phase-2 fork decisions on 2026-08-02 (F1=1A, F6=6B, F7=7A among them) after an explicit long-term comparison against LangGraph- and Temporal-class alternatives.

## Decisions

### D1 — Verbs are the sole sanctioned path for mechanical pipeline transitions

The complete verb set is `tools/pipe/{dispatch, pr-open, pr-merge, qa-verify, prd-close, record-green, batch-plan}` plus `tools/promote.sh`. Each verb executes: precondition checks (against the trace ledger and GitHub ground truth) → the side effect → an atomic v3 span. A refused transition exits non-zero with a named reason; a verb never half-succeeds silently (the pr-merge MERGE-PENDING/--confirm pattern is the template for bounded-budget deferral). **Enforcement (rule #23), named inline:** (a) the D4 deny-guard funnels the incident-backed raw forms to the verbs at PreToolUse time; (b) STREAM-LIVENESS per-kind rows expose any verb that silently stops being invoked; (c) the D6 reconciler family names every transition that routed around a verb as a per-artifact FAIL. No existing mechanism covers this: the R-* reviewer rules are review-time judgment over a diff, and the ADR-0029 stop-gate is session-boundary detection — neither acts at the moment of the side effect, which is where the incident record shows transitions get skipped.

### D2 — Closed span-kind enum at the writer

`tools/trace.py` accepts only the closed kind set {pr_opened, pr_merged, qa_verified, develop_green, promotion, dispatch, dispatch_end, verdict, batch_planned}. An unknown kind is a hard error (non-zero, nothing written). This kills the invisible-stream class (a typo'd kind silently minting an unwatched stream) at the writer rather than at a reconciler. Enforcement: the emit-path regression test plus STREAM-LIVENESS's per-kind registry, whose denominator is exactly this enum.

### D3 — Reviewer-verdict assertion + server-side floor on develop (fork 7A)

`tools/pipe/pr-merge` refuses to merge a slice PR lacking a reviewer comment containing `VERDICT: APPROVE` and emits a `verdict` span derived from the comment it verified. develop gains server-side branch protection requiring the `ci` status context — making the reviewer-doc claim "a red-CI PR never merges" true on the branch where every slice lands. **Parsimony delta vs the existing ADR-0029 stop-gate:** the stop-gate detects un-reviewed OPEN PRs at session-Stop only — a PR merged without review vanishes from its view instantly, it carries a documented `STOP_GATE_BYPASS=1` escape, and it cannot fire mid-session; the merge-time assertion enforces at the choke point where the side effect happens. The two compose (detection at the boundary, prevention at the transition); neither subsumes the other. The same-actor admin-bypass residual (#1098) remains explicitly deferred and captured.

### D4 — Deny-guard funnel for incident-backed raw forms with a working sanctioned alternative

The PreToolUse(Bash) validation hook DENIES exactly three raw forms, each with an incident number AND an existing sanctioned alternative: (1) raw `gh pr merge` (G2/#880 class → `tools/pipe/pr-merge`); (2) `tools/promote.sh` invoked from a subagent context (#880 → the operator/orchestrator sanctioned procedure) — subagent context detected by the same discriminator the ADR-0023 D3 meta-output hook already uses, so the operator's own invocation passes; (3) refspec-form pushes targeting main (`HEAD:main`, `refs/heads/main` — closes the evasion of the existing ADR-0023 D4 deny). Deny messages name the sanctioned verb. **Deliberately NOT denied:** `gh issue create --label slice|prd` — no sanctioned posting verb exists and `/to-issues`/`/to-prd` legitimately run this form in main-agent context; a hard deny would break the sanctioned pipeline itself (the #1038 untested-gate class this ADR's Alternatives reject). That form gets an advisory nudge naming `/to-issues`/`/to-prd`, and the #918 class keeps its deterministic enforcement via CI CHECK 19 (slicer-provenance) plus the SLICE-VS-PR reconciler; a posting verb is future work if the recorded evidence shows the nudge leaking. The hook stays within the validation category (HOK-002) and the fail-loud contract (HOK-008).

### D5 — Prose-shrink contract (fork 6B)

Each verb's landing PR deletes the SKILL.md prose block it mechanizes — same PR, reviewer-checkable (grep count=0 for the named block, verb call site remains). Skills shrink to the judgment layer (grill, plan, reroute, wrap-up); the prose shrinks exactly as fast as enforcement becomes real. **Parsimony delta vs existing doc-currency mechanisms:** R-DOCS-CURRENT gates generated-README regeneration and the codebase-critic judges semantic doc currency per-PRD — both are drift DETECTION over docs that are allowed to exist; this contract is a structural PROHIBITION on a specific dual-truth shape (procedure prose coexisting with the verb that owns the transition), checked mechanically per-PR by the reviewer with a named grep, no judgment required.

### D6 — Executor deferral re-affirmed with its recorded trigger

Sequencing BETWEEN verbs stays LLM judgment this phase. A sequencing-as-code executor — a bespoke daemon over the trace store, NOT LangGraph (operator-rejected after explicit long-term comparison: parity bill, dependency spine, loss of the chat-native proof surface) — is commissioned if and only if the recorded evidence trigger fires: a nonzero RECORD-VS-GH emission-gap rate after 2+ PRDs traced end-to-end, OR one new bypass incident (restating ADR-0075 D8's deferral triggers as binding for this phase). The reconciler family (RECORD-VS-GH promoted into CI, SLICE-VS-PR, MERGED-WITHOUT-VERDICT, CLOSED-PRD-VS-QA) is the instrument that produces that evidence.

## Consequences

- Illegal transitions are refused at the moment of side effect by deterministic code, not detected after the fact by prose-dependent discipline; every skip that routes around a verb becomes a named reconciler FAIL.
- "Running now" and "up next" become ledger queries (dispatch spans without terminal child; latest batch_planned), giving W2's run-board its data model and the duplicate-dispatch mutex for free.
- Verb indirection must actually be used: the deny-guard funnels the incident-backed raw forms, and STREAM-LIVENESS per-kind rows expose silently-unused verbs.
- The registry grows by three reconciler rows plus per-kind liveness rows; registry pruning stays coupled to the executor decision per ADR-0075 D7.
- The `gh issue create --label slice|prd` form remains advisory-only until a posting verb exists — a named, accepted residual (detection via CHECK 19 + SLICE-VS-PR, not prevention).
- Existing CLI contracts stay byte-stable for existing invocations; refusals fire only on newly-checked preconditions with named reasons.
- Cascade-doc surface (advisory): `.claude/hooks/pre-tool-bash.sh`, `.claude/agents/reviewer.md`, `.claude/skills/ship/SKILL.md` + `build/SKILL.md`, `decisions/branch-protection-config.json`, and the health-registry docs all move with the slices that touch them.

## Alternatives considered

- **LangGraph conductor (fork 1B):** structurally-unreachable illegal paths, but 4–6 weeks to /ship parity, the repo's first non-stdlib dependency spine (one semver strike on record), re-implementation of worktree isolation and permission posture, and loss of the operator's chat-native grill/proof workflow. Rejected now; its free native pieces remain adoptable in headless lanes.
- **Temporal-class durable execution:** the model (append-only history as truth, derived state, refoldability) is already adopted; the dependency (server + workers on a solo Windows box) is disproportionate. Rejected.
- **Prose + reconcilers only (fork 1D):** zero new machinery, but measured 0–17% prose compliance means the loop stays skippable exactly where the incident record shows it was skipped. Rejected.
- **Blocking everything reachable now (including the posting form):** guards shipped without a working sanctioned alternative self-destruct or break the pipeline they protect (#1038 class; the `gh issue create` deny would have blocked `/to-issues` itself). Rejected in favor of incident-backed denies with working alternatives only.

## References

- ADR-0075 (trace-core fork decisions: D3 wrapper pattern, D5 gate posture, D7 registry pruning, D8 deferral triggers)
- ADR-0056 (measured prose-compliance evidence; rule #23)
- ADR-0070 (two-tier delivery; D1 promotion gate)
- ADR-0066 (upstream spec contract; EARS criteria the parent PRD uses)
- ADR-0029 (stop-reviewer-gate; the session-boundary detector this ADR's D3 composes with)
- ADR-0023 (D3 subagent-context discriminator reused by this ADR's D4; ADR-0023 D4's push-to-main deny extended by this ADR's D4)
- ADR-0004 (D2 bootstrap-mode binding; D5c the missing-bootstrap-policy errata this ADR's binding paragraph avoids repeating)
- Operator fork decisions F1–F7, locked 2026-08-02 (session 2f257aec grill records)
- Incident classes: #918 (hand-created slices), #880 (unacked promotion), #869 (format review burn), #1038 (self-destructing gate), #1100 (pr-merge false negative survived)
