# ADR-0053: Artifact trail as system of record for workflow measurement

- **Status:** Accepted
- **Date:** 2026-06-10
- **Supersedes:** [ADR-0039](0039-single-source-workflow-topology.md) D3 (the "measured" overlay derived from runtime `skill_invoke`→`agent_complete` events — replaced by artifact-derived measurement); supersedes the exclusivity of [ADR-0016](0016-workflow-event-log-jsonl.md) D2 (hook-only delivery — invoking that ADR's own anticipated escape hatch: "If hook-based capture proves insufficient for rich workflow semantics… a future PRD may add hybrid in-skill instrumentation"; insufficiency is now proven twice over: all 7 hook registrations die ENOEXEC in claude-spawned shells, and resumed sessions never register hooks at all).
- **Extends:** [ADR-0039](0039-single-source-workflow-topology.md) D1/D2 (single declared spec, two renders — preserved and strengthened).
- **Honors:** [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (hook scope unchanged — this ADR touches no hooks); [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 (`dashboard/*` non-runtime); [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (no new critic); [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).

## Context

A 2026-06-10 forensic audit proved that the dashboard's declared-vs-measured comparison is
unsatisfiable by construction:

1. **Category error.** The declared topology (`PIPELINE.__edges__`, 36 edges / 31 node ids,
   12 of them artifact pseudo-nodes like `prd_issue`/`pr`/`merge`) and the measured topology
   (`deriveMeasuredEdges` — only two derivable edge shapes: `orchestrator→skill`,
   `lastSkill→agent`) share no common ontology. `orchestrator` does not appear in `__edges__`
   at all, so the most common measured edge is permanently painted red; only 8/36 declared
   edges could ever match under perfect capture. Empirical replay of the full event corpus:
   25 measured edges → 3 green, 22 red.

2. **The measured side's feed is structurally unreliable.** All 7 event-logging hook
   registrations are inline-jq commands that die ENOEXEC in claude-spawned shells (proven via
   `claude -p --debug`), and resumed marathon sessions never register hooks at all — two
   independent kill mechanisms for the runtime stream, both silent.

3. **The durable ground truth was never used.** The pipeline already writes verdict-rich,
   fixture-proof telemetry as GitHub artifacts: one batched GraphQL query reconstructs a
   complete PRD run (slices, PRs, reviewer verdict rounds including BLOCK→APPROVE sequences,
   merges, timestamps) in ~0.8s/PRD (verified; 95-PRD cold backfill 73s, then cacheable
   forever for closed PRDs). The `closingIssuesReferences` slice→PR join is 99.6% reliable
   (full 238-PR census). The trail catches real violations: PR #650 merged with zero reviewer
   verdicts.

The fix is an architecture inversion: **the GitHub artifact trail becomes the system of record
for declared==measured; runtime hook events become live enrichment only.**

## Decisions

### D1: Artifact trail is the system of record for workflow measurement

Declared==measured is evaluated against the GitHub artifact trail (issues/sub-issues/PRs/
verdict comments/labels/merges), reconstructed per-PRD by `dashboard/collector.py`. Runtime
hook events are live enrichment only and never feed the comparison engine. This supersedes
[ADR-0039](0039-single-source-workflow-topology.md) D3 (which sourced the measured overlay
from `skill_invoke`→`agent_complete` hook events) and supersedes the exclusivity of
[ADR-0016](0016-workflow-event-log-jsonl.md) D2 (hook-only delivery) via that ADR's own
anticipated escape hatch. [ADR-0015](0015-claude-code-hooks-adoption.md) D2 hook-scope
policy is untouched.

### D2: One evidence-annotated SPEC

Single id-space + node kinds (`human|orchestrator|skill|agent|artifact`) + stable edge ids
(`E-*`) + `required: always|conditional` + per-edge `evidence` tier
(`github|runtime|unmeasurable`) with a named predicate. SPEC is the only declared topology
(replaces `children[]` + `__edges__` in the full-ontology slice). `/api/pipeline`, dashboard
render, and README mermaid all generate from it (extends [ADR-0039](0039-single-source-workflow-topology.md) D1/D2 — single-source preserved and strengthened).

Evidence tiers:
- **`github`** — authoritative; evaluated in the comparison engine against real GitHub
  artifacts. These are the only edges that can be `confirmed` or `missing`.
- **`runtime`** — live enrichment only (hook events, session timestamps); never compared
  against the trail; rendered as context where available, silently absent where not.
- **`unmeasurable`** — in-conversation events (human decisions, grill sessions); rendered
  as declared context only; never treated as drift evidence.

### D3: Per-run comparison with explicit states

`compare(SPEC, trail) → report` evaluated **per PRD-run** (attribution by artifact linkage —
sub-issues, `closingIssuesReferences`, comment-on-issue — never timestamp adjacency).

Per-edge states:
- **`confirmed`** — predicate true; carries counts/timestamps/rounds
- **`missing`** — predicate false AND the run demonstrably progressed past the stage
  (never applied to in-flight runs)
- **`not-reached`** — in-flight or ended early; **never red**
- **`not-exercised`** — conditional edge whose condition never arose; **never red**
- **`unexpected`** — trail evidence matching no declared edge (first-class output)

Violation detectors are first-class outputs:
- `unreviewed_merge` — merged PR, no verdict comment, no `trivial` label
- `no_closes_slice` — PR merged but `closingIssuesReferences` points to no slice in this PRD
- `slice_no_pr` — slice issue closed with no known closing PR

**Run PASS** := every `required:always` github-tier edge on the traversed path `confirmed`
AND zero violations.

String-pair edge matching (the `deriveMeasuredEdges` pattern) is abolished. Stable `E-*` ids
are the join key.

### D4: Collector resilience ladder

`dashboard/collector.py` implements a four-level degradation ladder:

1. **Cache-first** — closed PRDs (`closedAt` non-null) are cached forever under
   `.claude/logs/trail-cache/prd-<n>.json` (immutable run; never refetch). Open PRDs use a
   short TTL (60s). Cache key includes `closedAt`; a non-null `closedAt` means immutable.
2. **Bounded retry** — 0s/2s/8s backoff on 401/5xx/timeout. Instant-retry recovers the
   ~15% transient Windows keyring flake.
3. **Distinct `auth_dead` state** — sustained failure (all retries exhausted) surfaces a
   "run `gh auth status`" message; never busy-loops.
4. **Git-log offline floor** (future) — squash `(#N)` + `Co-authored-by:` trailers recover
   merge/provenance with zero API; not implemented in slice 1 (walking skeleton).

Degradation is always visible ("measured as of N min ago"), never silent.

### D5: Golden-run acceptance

The staging plan's final PRD must ship via a real `/ship` run whose own comparison report is
PASS (all `required:always` github-tier edges `confirmed`, zero violations). Until then, each
PRD's production check exercises the comparison against real closed PRDs. The comparison must
work with the event log empty (it reads GitHub, not `.claude/logs/workflow-events.jsonl`).

### D6: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge of this slice. Historical PRDs are measured as-is: missing
convention-era evidence (e.g., no `closingIssuesReferences` on very old PRs) renders as
`missing (discipline)` — honest history, no retroactive rewrite. `not-reached` is used for
any edge where the run demonstrably ended before the stage was reached.

## Consequences

**Positive:**
- The declared-vs-measured comparison is satisfiable: the trail is durable, complete, and
  fast (~0.8s/PRD cold; instant from cache for closed PRDs).
- In-flight runs are never painted red (`not-reached` and `not-exercised` are never alarm
  states); only proven gaps are `missing`.
- Real violations are surfaced: `unreviewed_merge` catches the PR #650 class of bug.
- No new runtime artifacts, no new hooks, no new critics, no new dependencies.

**Negative:**
- The GitHub API is a remote call; network-isolated environments or expired tokens degrade
  to `auth_dead` (surfaced clearly, never silent).
- The measured overlay (Declared/Measured/Both mode toggle) built under ADR-0039 D3 is
  superseded; the UI replaces it with the per-run comparison painted on the declared graph
  (implemented in slice 3).

**Neutral:**
- Hook events remain the Live tab's concern (PRD 4 in the staging plan) and are untouched.
- `KNOWN_CRITICS` stays literal in `dashboard/server.py` (CHECK 7 regexes source text);
  new modules import INTO server.py with explicit named imports (never `import *`).
- CHECK 9's `import server; server.check_docs1..10` surface is preserved.

## Alternatives considered

- **Alt-A (rejected): keep runtime hook events as the primary source.** The two independent
  kill mechanisms (ENOEXEC in claude shells + missed hook registration on resume) make this
  unreliable. The 22/25 red-edge result proves it is unsatisfiable, not just imprecise.
- **Alt-B (rejected): polling gh for every page reload, no cache.** Unacceptable latency
  (73s for 95 PRDs cold). The cache-first ladder is load-bearing.
- **Alt-C (rejected): replace GitHub with git-log-only offline reconstruction.** Git log
  recovers merge provenance but not reviewer verdicts or label events. It is a valid offline
  floor (D4 future work) but insufficient as a primary source.

## References

- Forensic audit (2026-06-10): `qa-proof/forensics/` (6 readers); design record:
  `qa-proof/design/` (3 architects, 3 judges, 6 adversarial verdicts).
- [ADR-0039](0039-single-source-workflow-topology.md) D1/D2 (extended) + D3 (superseded)
- [ADR-0016](0016-workflow-event-log-jsonl.md) D2 (exclusivity superseded via its own escape hatch)
- [ADR-0015](0015-claude-code-hooks-adoption.md) D2 (untouched)
- [ADR-0033](0033-tooling-spawn-hook-scope.md) D4 (non-runtime)
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (no new critic)
- [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode)
- `dashboard/collector.py`, `dashboard/comparison.py`, `dashboard/pipeline_spec.py`
- Real PRD #640 (proof corpus: 3 slices, 3 PRs, APPROVE rounds, ~51m wall-time)
- PR #650 (the unreviewed-merge violation the trail catches)
