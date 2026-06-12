# Trail of Record — artifact-first closed-loop workflow observability

Design position: **GitHub artifacts are the system of record for declared==measured. Runtime hook events are optional live garnish that degrades honestly.** This inverts the current stack (which made the fragile layer load-bearing and the durable layer invisible) and is the only architecture that satisfies C2: when the user works in a marathon resumed session and hooks never register, the measurement must not care — and an artifact trail does not care.

The pipeline already *writes its own telemetry*: every stage that matters ends in a `gh` write (issue, sub-issue, PR, verdict comment, label event, merge). The forensics prove it: 38/40 recent PRs have parseable verdict trailers, one batched GraphQL query reconstructs a full PRD run in 0.816s, multi-round BLOCK→APPROVE trails are recoverable with timestamps, and the trail even *caught a real violation* (PR #650 merged with zero reviewer verdict). Meanwhile the runtime log captured 11 `skill_invoke` events in its whole life and was 64% unattributable and majority-synthetic. The system of record decision is not a preference; it is what the evidence supports.

---

## 1. The single declared spec

**One file, one id space, one encoding: `dashboard/pipeline_spec.py` exporting `SPEC`.** It replaces both `children[]` and `__edges__` in the `PIPELINE` dict (dashboard/server.py:39–201). Everything renders from it: `/api/pipeline`, the dashboard topology, `render_pipeline_mermaid()` for README regeneration (ADR-0039 D2 preserved), and the comparison engine.

**Shape:**

```python
SPEC = {
  "version": 2,
  "nodes": {
    # kind: human | orchestrator | skill | agent | artifact
    "user":            {"kind": "human"},
    "orchestrator":    {"kind": "orchestrator"},          # first-class — was absent from __edges__
    "ship":            {"kind": "skill", "stage": "S1", "path": ".claude/skills/ship/SKILL.md"},
    "prd-critic":      {"kind": "agent", "stage": "S2", "path": ".claude/agents/prd-critic.md"},
    "promote-to-backlog": {"kind": "skill", "stage": "SS"},  # real id — 'ptb' alias dies
    "prd-issue":       {"kind": "artifact", "stage": "S2"},  # noun ids; underscore/hyphen duality dies
    "pr":              {"kind": "artifact", "stage": "S3"},
    "merge":           {"kind": "artifact", "stage": "S3"},
    # ... slice-issue, needs-human, captured-issue, backlog-issue, glossary-pr, verify-verdict
  },
  "edges": [
    {"id": "E-PR-REVIEW", "from": "pr", "to": "reviewer", "kind": "gates",
     "required": "always",
     "evidence": {"tier": "github",
                  "predicate": "pr.comments[fenced CRITIC trailer].VERDICT"}},
    {"id": "E-REVIEW-BLOCK", "from": "reviewer", "to": "implementer", "kind": "blocks",
     "required": "conditional",
     "evidence": {"tier": "github", "predicate": "pr.comments[VERDICT=BLOCK, ROUND=n]"}},
    {"id": "E-USER-BUILD", "from": "user", "to": "build", "kind": "invokes",
     "evidence": {"tier": "runtime", "predicate": "skill_invoke[skill=build]"}},
    {"id": "E-GRILL-SHIP", "from": "grill-me", "to": "ship", "kind": "handoff",
     "evidence": {"tier": "unmeasurable",
                  "note": "in-conversation; PRD-body grill footer is the documented proxy"}},
    # ...
  ],
}
```

**Three evidence tiers** (this is the C3 answer — every edge gets exactly one):

| Tier | Meaning | Participates in declared==measured? | Render |
|---|---|---|---|
| `github` | Recoverable from the artifact trail by a named predicate | **YES — authoritative** | solid; painted green/red/gray by state |
| `runtime` | Observable only via live hook events | NO — enrichment only (activity dots/counts when capture alive) | solid, with "live-only" glyph |
| `unmeasurable` | In-conversation; declared as context | NO — never colored as drift | dotted/hollow, labeled |

**Ontology fixes baked in:** canonical hyphen ids identical to skill/agent directory names; `orchestrator` and `promote-to-backlog` first-class; `qa-review` added (it is a real shipped skill, currently absent); `U1/U2` become `user` + the `verify-verdict` artifact; the `ptb/cap/bl/capstay` 3-letter aliases die; edges carry **stable ids** (`E-*`) so the collector, comparison report, UI, and golden-run proof all key on edge ids — string-pair matching is abolished. `required: always|conditional` distinguishes spine edges from BLOCK loops and if-ADR branches.

**Coverage arithmetic after this redesign** (vs. today's hard ceiling of 8/36): the 12 artifact pseudo-nodes flip from "unmeasurable by construction" to *the best-measured nodes in the system*, because artifacts are measured with artifacts. With the verdict-posting convention (§7), ~24–26 of ~36 edges sit in the `github` tier with timestamps and round counts; ~8 (user/skill invocations, advisory audits, whole-repo background codebase-critic) are honest `runtime` tier; 2–4 (grill content, in-conversation handoffs) are explicit `unmeasurable`. Nothing renders as fake drift.

Key per-edge evidence mapping (the load-bearing rows):

| Declared edge | Evidence (github tier) |
|---|---|
| to-prd → prd-critic / adr-critic | CRITIC trailer posted as PRD-issue comment (convention, §7) — VERDICT + ROUND |
| prd-critic → prd-issue | issue createdAt + label `prd` + APPROVE comment |
| to-issues → slicer → slicer-critic → slice-issue | native `subIssues` (deterministic) + slicer-critic trailer comment (convention) |
| slice-issue → implementer → pr | PR `closingIssuesReferences` (exact, proven) + `feat/<N>-` branch + `Co-authored-by:` commit trailer |
| pr → reviewer (+ BLOCK rounds) | PR verdict comments — regex `VERDICT:/ROUND:` (38/40 parse today) |
| reviewer → merge | `mergedAt` + last-verdict APPROVE + git-log `(#N)` cross-check |
| reviewer → needs-human | `needs-human` LABELED timeline event |
| merge → qa-plan → qa-tester → verify-verdict | QA-plan PRD comment (already posted) + `PRODUCTION_VERIFY:` PRD comment (convention) |
| captured-issue → promote-to-backlog → backlog-critic → backlog-issue | `captured` label create + verdict audit comment (skill already posts it) + label swap event |

## 2. Capture v2 — the runtime garnish layer

Demoted, simplified, and made honest. Its only consumers are the Live tab's session feed and optional verdict-badge enrichment. **It feeds nothing in declared==measured.**

**Delivery (C1):** all 7 inline-jq registrations in `.claude/settings.json` are replaced by ONE parameterized script-file hook — the empirically-proven delivery mechanism:

```
bash "$CLAUDE_PROJECT_DIR/.claude/hooks/log-tool-event.sh" agent_complete
```

registered per matcher (PreToolUse Agent/Skill, PostToolUse Agent/Bash/AskUserQuestion, Stop, SessionStart). Inside the script: read stdin once, parse with **python3** (already required by the dashboard; jq is banished from the capture path — the ENOEXEC machine hazard becomes irrelevant), append one canonical line. All path resolution through one shared sourced snippet `.claude/hooks/lib-root.sh` (`git rev-parse --git-common-dir` + `mkdir -p`) — beacons and events from worktree sessions land in the main repo's logs, ending the split-brain.

**Schema v2** (every event): `{"v":2, "ts": ISO8601, "session_id": <required non-empty>, "src":"hook", "wt": <worktree-or-main>, "event": ..., ...payload}`. Event set: `session_start` (NEW — real run boundaries), `user_prompt` (slash-commands only), `skill_invoke{skill}`, `agent_start{subagent_type}`, `agent_complete{subagent_type, tail}`, `bash_complete{command≤200}`, `session_stop` (sid from stdin JSON like every other event — env sourcing dies).

**Trailer capture (C4):** `agent_complete.tail` = the **last 2,000 chars** of `tool_response` (the head-capture defect inverted) — the fenced CRITIC/GENERATOR trailer lives there. Used for live VERDICT badges only; authoritative verdicts come from GitHub.

**Failure loudness:** the script writes a beacon `{"hook":"<event_type>","status":"attempt"}` **first**, before any parsing; on failure it writes `{"hook":"<event_type>","status":"error","reason":...}` instead of exiting silently. This fixes three defects at once: silent total data loss by construction, the all-7-collapse-to-"log-event" telemetry join (the beacon carries the event-type name), and "fired N×" counting deliveries instead of attempts. The dashboard hooks panel renders error beacons red.

**Fixture quarantine (C5) — three independent structural layers:**
1. **The deepest one is the architecture itself:** measurement reads GitHub, not the log. No amount of log pollution can touch declared==measured ever again. (And GitHub artifacts can't be fixture-polluted without leaving an audit trail of real issues/PRs.)
2. **Writer-side routing:** the logger routes any event with `session_id` matching `^(demo|test|verify|fixture|sess-|manual)` or carrying `"synthetic":true` to `.claude/logs/workflow-events.test.jsonl`, which the server never reads outside `?fixture=1`. Demo data for screenshots lives in `dashboard/fixtures/` (which has existed since CHECK 8 and was never used for this).
3. **Reader-side validation + reviewer rule:** `/api/runs` requires schema v2 + non-empty sid and drops fixture-pattern sids defensively; new reviewer grep rule **R-FIXTURE** BLOCKs any PR whose code writes `.claude/logs/` paths outside `.claude/hooks/`.

**C2 honesty:** capture v2 makes *no claim* to work in resumed sessions. `session_start` + beacon recency drive a per-session liveness verdict the Live tab displays truthfully (§5). Nothing breaks when it is dead.

R-LOC note (C6): hooks + settings.json are runtime artifacts; the capture-v2 PRD slices are sized ≤300 LoC each (one logger script + registrations is small by design — 7 inline blobs collapse into 1 script).

## 3. The durable measurement layer — GitHub-artifact collector

**Placement:** `dashboard/collector.py` (non-runtime per ADR-0033 D4), stdlib-only, shelling to the `gh` CLI (already a hard project dependency; matches the existing `fetch_workitems` pattern). Two entry points: HTTP (`/api/trail?prd=N`, `/api/comparison?prd=N` served by server.py) and CLI (`python dashboard/collector.py --prd 640 [--compare]`) so qa-tester's command-run route and future audits can consume it without a browser.

**Mechanism:** one batched GraphQL query per PRD (the proven 0.816s/46KB shape): `issue(N){createdAt, closedAt, labels, comments, subIssues{..., timelineItems(CLOSED_EVENT, LABELED_EVENT)}}` + `closingIssuesReferences` on each candidate PR + PR comments. Slice→PR mapping uses `closingIssuesReferences` exclusively (timeline cross-refs are proven noisy); branch name `feat/<N>-` is the secondary check. Git log is the local cross-check layer: squash-subject `(#N)` joins and `Co-authored-by:` trailers prove merge integrity and agent provenance with zero API calls.

**What it recovers:** prd_posted; grill proxy (PRD-body footer); prd-critic/adr-critic verdicts + rounds (from posted trailer comments); slices_posted (native sub-issues); per-slice pr_opened; **reviewer verdict rounds including full BLOCK→APPROVE sequences** (regex on fenced trailer, tolerant parser: when `ROUND:` is absent — the PR #559 drift class — infer round from verdict-comment ordering and mark `round_inferred:true`); merged + slice closed; needs-human label events; production-verify comment; captured→backlog label transitions; prd_closed.

**Violation detectors (first-class outputs, not afterthoughts):**
- **Unreviewed merge** — merged PR, no verdict comment, no `trivial` label (catches the real PR #650 today; this becomes the design's first honest red).
- PR without `Closes #<slice>` (R-CLOSES breach); slice closed with no PR; PRD closed with open slices; commit on main with no PR number.

**Caching:** per-PRD JSON under `.claude/logs/trail-cache/` (gitignored), keyed on `closedAt` — closed PRDs are immutable, cached forever; the open/in-flight PRD refreshes on a 20–30s TTL while the dashboard is open. **Retry-once on transient 401** (the proven Windows keyring flake). Budget: a cold full-repo backfill ≈ 15 queries ≈ <1% of GraphQL rate limit.

## 4. Comparison semantics

**Scope unit = a run.** A *PRD-run* roots at a `prd`-labeled issue and evaluates the S1–S4 spine + per-PRD side edges; *side-runs* root at a glossary PR or a captured issue. This kills the cross-session temporal-heuristic class of corruption: attribution is by artifact linkage (sub-issue, closingIssuesReferences, comment-on-issue), never by timestamp adjacency.

**Computed in ONE place, server-side:** `dashboard/comparison.py`, a pure function `compare(SPEC, trail) -> report`, consumed by the Architecture tab, the Live tab's run lane, the CLI, and the golden-run proof. The client never re-derives edges (deriveMeasuredEdges dies).

**Per-edge states** (each `github`-tier edge, per run):

| State | Meaning | Color |
|---|---|---|
| `confirmed` | evidence predicate true; carries count, timestamps, rounds | green |
| `missing` | predicate false AND the run demonstrably progressed past this stage (e.g. merge exists but no reviewer verdict) | red — drift |
| `not-reached` | upstream stage absent (run in flight or ended early) | gray |
| `not-exercised` | `conditional` edge whose condition never arose (BLOCK loop on a clean run) | neutral |
| `unexpected` | trail evidence matching no declared edge (the enumerated violation detectors) | red — drift |
| `runtime-only` / `unmeasurable` | tiered out of the comparison | styled, never red |

**`declared == measured` PASS for a run** := every `required:always` github-tier edge on the traversed path is `confirmed` AND zero `unexpected` findings. The repo-level rollup aggregates the last N runs: per-edge confirmation counts become edge weights (this is the user's "how many times", answered durably), and any always-edge never confirmed across N runs is flagged "never exercised — spec may be aspirational".

**Golden-run acceptance (defined in ADR-0052, enforced by qa-tester):** the first real `/ship` run after the comparison ships must yield PASS — every traversed spine edge green, zero red — with the JSON comparison report + a browser screenshot as the proof artifacts. The staging plan (§8) additionally proves the machinery on day 1 against an *already-closed real PRD* (#640), and closes the loop at the end by requiring the final PRD's own `/ship` run to be a golden run. The comparison verifies the pipeline; the pipeline shipping the comparison verifies the comparison.

## 5. Live tab contract

**Mechanism: incremental polling. SSE is deleted, not rescued.** Justification: (a) the server is stdlib `http.server` — a held-open SSE connection occupies the handler; polling keeps C7 comfortable with zero daemon/threading complexity; (b) under C2 the live feed's availability is dominated by whether hooks registered *at all* — sub-second push transport buys nothing when the variable is feed-existence, and dishonest "real-time" branding is exactly what burned this tab; (c) the existing `/api/events` endpoint has zero consumers, a duplicate-replay resume bug, and re-reads the whole file per second — it is dead code (code-health). Poll design: `/api/runs?since=<byte-cursor>` — the server stats the file and reads only appended bytes, returning `{cursor, events[]}`; the client polls every 3–5s while the tab is visible. O(new bytes), not O(file).

**Session bucketing:** strict group-by non-empty `session_id`; `session_start`/`session_stop` give real boundaries (no more first-tool-event inference); full-window scan with group-by (the contiguity/break-on-non-match assumption dies — interleaved orchestrator + worktree sessions are the designed norm); `wt` field renders as a lane badge; fixture-pattern sids excluded by the reader.

**What the user sees during a `/ship` run — two lanes plus a status strip:**

- **Lane A — "Run progress" (authoritative, artifact-fed).** The collector's trail for the in-flight PRD, polled on 20–30s TTL: `PRD #672 posted ✓ → slices 3/3 ✓ → #673: PR #676 open → reviewer BLOCK r1 → APPROVE r2 → merged ✓ → ...` with timestamps and stage durations (review latency, slice wall-time). **This lane works in a marathon resumed session with zero hooks registered** — the user always sees the agents' work land, because the work itself is the telemetry.
- **Lane B — "Session feed" (best-effort, hook-fed).** Newest-first events for the selected session: skill invokes, agent start/complete with live VERDICT badges parsed from trailer tails, bash calls. Present only when capture is alive.
- **Status strip — honest degradation as a feature:** capture pill = `LIVE — last event 8s ago` or `INACTIVE — this session never registered hooks (known Claude Code behavior on resumed sessions); measurement unaffected — Run progress is artifact-based. Start a fresh session to watch the live feed.` Collector pill = last successful gh fetch / auth-flake warning / `OFFLINE — showing cached trails`. The #648 honest-banner primitive, promoted from apology to contract.

## 6. Code-health refactor scope (CHECK 9 survives)

**server.py (1,981 lines, 6 programs) → thin facade + flat siblings in `dashboard/`:** `pipeline_spec.py` (SPEC + mermaid renderer), `discovery.py`, `health.py` (check_docs1–10 + AS-*), `events.py` (runs + tail-seek + cursor), `collector.py` (new), `comparison.py` (new), `workitems.py`, `readme_gen.py`. `server.py` keeps the HTTP handler + explicit re-exports (`from health import check_docs1_adr_index_forward, ...`) so CHECK 9's `sys.path.insert('dashboard'); import server; server.check_docs1_*` (tools/ci-checks.sh:501–539) resolves unchanged; each split slice runs `bash tools/ci-checks.sh` as its proof. New code lands in new modules from PRD 1 onward; the move-and-purge of old code comes last.

**Deletions:** `_serve_sse` + `/api/events` route + the docstring's SSE claim; `_dispatchMapFromSpec`/`_orchestratorChildrenFromSpec`; the `children[]` arrays (replaced by SPEC edges — their consumer count is already zero); `deriveMeasuredEdges` + `fetchMeasuredEvents` (comparison moved server-side); `toggleDetail`; `_grep_count`/`_grep_fixed`; the `'m:'` dead ternary (#631 — clicks become edge/node-id keyed against SPEC paths); ~45 orphan CSS classes (~170 lines, 502–669); `cascade_finder_summary` either checks its returncode or goes.

**Dedupe:** one `assignLevels(edges)` BFS with the cycle cap (retires the #637/#638 fix-it-twice class); one `showPanel(panelId, {title, fields, bodyHtml})` + `renderExtraFields()` replacing the 4 pasted blocks and 4 panel implementations; one agent-span pairing util; one time-format util.

**Deliberately NOT done (YAGNI):** no `js/*.js` split (would require a new static-file route; the in-file cleanup plus server-side comparison removes most client complexity anyway); CDN vendoring captured as a backlog issue, not scoped.

`/api/health` gets an mtime-keyed cache and parses each SKILL.md once per request.

## 7. Process-rule changes

**ADRs (2 new):**
- **ADR-0052 — "Artifact trail is the system of record for workflow measurement."** Supersedes ADR-0039 D3 (measured overlay from runtime `skill_invoke`→`agent_complete` events) and ADR-0016 D2's hook-only exclusivity — invoking ADR-0016's own escape hatch ("if hook-based capture proves insufficient... a future PRD may add hybrid in-skill instrumentation"; it has been proven insufficient twice over, C1+C2). Defines: the single SPEC, evidence tiers, per-edge comparison states, golden-run acceptance, collector caching/retry, runtime-as-enrichment. Rule #12 (ADR-0015 D2) is untouched: hooks remain logging-only; the in-skill side of the hybrid is "post a comment via gh" — a workflow output, not a hook action.
- **ADR-0053 — "Fixture and provenance discipline"** (D1–D6): fixture rule, proof provenance, route-downgrade policy, registration-liveness check, live-feed precondition, system-skeleton rule.

**CLAUDE.md rules:**
- **NEW rule #21 — fixture discipline:** fixture/synthetic data never enters production data stores (`.claude/logs/*`); fixtures live in `dashboard/fixtures/` and load only behind an explicit flag; any verification whose evidence derives from fixture-tagged data is INVALID.
- **Rule #20 amended — provenance per proof:** every proof artifact states its data source (real session id / PRD / PR + timestamp) and environment freshness (server restarted after merge); the orchestrator mechanically checks both at wrap-up. This shifts the gate from artifact-*shape* to evidence-*validity* — the P1/P6 fix: a false PASS becomes more expensive than an honest FAIL.
- **NEW rule #22 — system skeleton:** a feature implementing stage N of a multi-PRD pipeline must, in slice 1, demonstrate one REAL datum traversing stages 1..N in the production environment.

**Critic rubric changes (no new critic — parsimony per ADR-0046 D1):**
- **reviewer:** R-FIXTURE (BLOCK PRs writing `.claude/logs/` outside `.claude/hooks/`); R-TRAILER (CRITIC trailer standard key set, ROUND mandatory).
- **prd-critic:** PC-LIVE-FEED — a PRD consuming an upstream pipeline must declare a live-feed precondition ("upstream emits a real datum < N min old in the verification environment") and the gate FAILs (not PROVISIONALs) when the feed is dead.
- **slicer-critic:** SC-SYSTEM-SKELETON — enforces rule #22 at decomposition time.
- **qa-tester:** (a) **route downgrade is a residual, never a silent PASS** — declared route's tooling unavailable → PROVISIONAL + `needs-human-check` (the #639 silent-downgrade fix); (b) hook-fire route gains a **registration-liveness assertion** — spawn fresh `claude -p 'noop'`, assert a new beacon, manual script invocation only proves script-correctness; (c) browser route gains **data-provenance assertions** — rendered session id non-fixture, event ts newer than verification start, dashboard restarted from origin/main.
- **Verdict-posting convention (the coverage lever):** `/ship` posts prd-critic/adr-critic/slicer-critic/codebase-critic CRITIC trailers as PRD-issue comments; `/qa-plan` posts `PRODUCTION_VERIFY:` as a PRD comment (reviewer already posts to PRs; promote-to-backlog already posts its audit comment). This is what raises artifact coverage from 7/11 stages to ~10/11 — by convention, not hooks, exactly as the trail-assessor proved cheapest.

## 8. Staging

Six PRDs in dependency order, each with an appetite and a walking skeleton; rule #22 applies to this refactor itself — **PRD 1 slice 1 proves one real datum end-to-end on day 1** (a real closed PRD's trail flowing spec→collector→comparison→pixel). Full plan in the staging section.
