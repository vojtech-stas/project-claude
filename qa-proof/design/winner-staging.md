# Staging — six PRDs, dependency-ordered, each with appetite + walking skeleton

**PRD 1 — "Trail of record: spec + collector + comparison skeleton"** (ships with ADR-0052 through the joint prd-critic + adr-critic gate). Appetite: 1 week.
- **Slice 1 (walking skeleton — the rule-#22 proof for this very refactor):** minimal `SPEC` v1 covering only the spine (prd-issue → slice-issue → pr → reviewer → merge → closed) with evidence ids; `dashboard/collector.py` (one GraphQL per PRD, closedAt-keyed cache, retry-once-on-401); `dashboard/comparison.py` (confirmed/missing/not-reached on the spine); `/api/comparison?prd=N`; a bare table render in the dashboard. **Proof: run against real closed PRD #640 — its full trail (3 slices, 3 PRs, APPROVE rounds, merges, 51m13s wall-time) renders end-to-end. One real datum traverses spec→collector→comparison→UI on day 1.** Browser-route screenshot + inner_text + CLI output with exit code.
- Slice 2: full ontology — all nodes/edges, three tiers, conditional edges, stable edge ids; SPEC replaces `__edges__`/`children[]`; mermaid + README regenerate from SPEC; declared topology renders SPEC with tier styling (the incomparable both-mode dies here).
- Slice 3: comparison UI v2 — per-edge states painted on the declared graph, run picker, repo rollup with confirmation-count edge weights; violation detectors live (must flag the real PR #650 unreviewed merge as its proof).
- Slice 4 (cascade): README/decisions-index regeneration, doc currency.

**PRD 2 — "Verdict provenance + process hardening"** (ships with ADR-0053). Appetite: 3–4 days. Lands BEFORE capture v2 so all later work happens under fixture discipline.
- Slice 1: verdict-posting convention in /ship + /qa-plan; CRITIC trailer standardization (ROUND mandatory) + reviewer R-TRAILER. Proof: next real run shows a prd-critic trailer as a PRD comment that the PRD-1 collector parses (command-run excerpt).
- Slice 2: CLAUDE.md rules #21/#22 + rule-#20 amendment; reviewer R-FIXTURE; prd-critic PC-LIVE-FEED; slicer-critic SC-SYSTEM-SKELETON; qa-tester route-downgrade/registration-liveness/data-provenance edits. Proof: static greps per rule #20.

**PRD 3 — "Capture v2: script hooks + quarantine"** (runtime artifacts — settings.json + hooks; slices sized hard against R-LOC ≤300). Appetite: 1 week.
- **Slice 1 (skeleton):** ONE event type (`skill_invoke`) through the new `log-tool-event.sh` script registration, end-to-end: fresh `claude -p` session → v2 event with non-empty sid in the production log → visible via /api/runs. Proof: the new registration-liveness route, dogfooded on itself (fresh-session beacon + log-line excerpt with `exit=`).
- Slice 2: remaining event types incl. agent_complete TAIL capture, session_start/stop with stdin sid, loud-failure beacons, shared `lib-root.sh` resolution.
- Slice 3: fixture routing to workflow-events.test.jsonl, reader-side validation, per-event-type truthful telemetry + red error badges in the hooks panel.

**PRD 4 — "Live tab v2: two lanes, honest pills."** Appetite: 1 week.
- **Slice 1 (skeleton):** Lane A — artifact run-progress for the most recent open PRD, polled from the collector; works with hooks dead. Proof: screenshot captured DURING this PRD's own /ship run showing its own slices progressing.
- Slice 2: Lane B session feed (byte-cursor incremental poll, strict sid bucketing, verdict badges from trailer tails) + capture/collector status pills; delete `_serve_sse` + legacy live-UI CSS.
- Slice 3: golden-run surface — per-run "declared == measured: PASS/FAIL" banner + downloadable JSON comparison report.

**PRD 5 — "Dashboard decomposition + dead-code purge."** Appetite: 3–5 days. Last, because the deletions depend on PRDs 1–4 having replaced the old views (new code already landed in new modules, so this is mostly moves).
- Slice 1: server facade split (pipeline_spec/discovery/health/events/workitems/readme_gen siblings; server.py re-exports). Proof: `bash tools/ci-checks.sh` — CHECK 9 PASS excerpt with exit code.
- Slice 2: index.html dedupe (assignLevels, showPanel, span pairing, time utils), orphan-CSS purge, /api/health caching, dead-function deletions.

**Golden-run closure (the acceptance for the whole refactor):** PRD 5 is shipped via a real `/ship` run, and PRD 5's production-verify REQUIRES the comparison report for that very run to be PASS (all traversed spine edges confirmed, zero unexpected) plus the Live tab two-lane screenshot taken during the run. The system's final proof is itself shipping cleanly through the pipeline it measures.

Total appetite ≈ 4 weeks. Parallelism: PRD 2 slice 2 (process docs) can run alongside PRD 1 slices 2–3; PRD 3 and PRD 4 slice 1 are independent after PRD 1 (the artifact lane needs only the collector).