# ADR-0006: Backlog queue + session continuity (live-state reconstruction)

- **Status:** Accepted (drafted by `/to-prd` alongside PRD-D; reviewed jointly by `prd-critic` and `adr-critic` per ADR-0004 D1)
- **Date:** 2026-05-14
- **Extends:** ADR-0001 D8 (orientation artifacts — adds the backlog mechanism as a complement); reinforces ADR-0003 D8 (ADR placement unchanged; backlog is complementary, not a replacement)
- **Supersedes:** none
- **Decided in:** Grill session "Session state management" (2026-05-14, following PRD-A merge)

---

## Context

After PRD-A merged, the user raised three adjacent gaps in a grill session:

1. **Can I queue a new PRD grill topic to come back to later?** There was no forward-looking queue. Ideas surfaced in a grill but not yet ready for full grilling had nowhere to land.

2. **How does a new agent session continue the work of a previous one?** When context fills or the user closes Claude Code, a new session opens with no canonical "previous session was working on X; next is Y" pointer. Today the agent infers from `git log` + open issues + the project board, but the convention is undocumented.

3. **Where do new ideas surfaced in grill-me sessions go?** They were being captured ad-hoc in ADR "Future direction" sections, or lost.

Investigation surfaced that ADRs already partially solve concern #3 (Future-direction sections capture deferred work), but they fall short on aggregation ("what's all the queued work across all ADRs?") and on new ideas not tied to any decision.

For concern #2 (handoff), every alternative considered (committed `HANDOFF.md`, memory file, GitHub Issue, per-stage updates) either added discipline overhead or didn't solve the underlying problem (mid-grill interruption loses conversational context regardless of mechanism). The honest answer was: "humans don't keep a live handoff document either; they reconstruct from live state."

For concern #1 (backlog), the modal modern best practice for a small repo with a strong issue tracker is GitHub Issues with a `backlog` label, organized in a project-board column. This integrates with existing infrastructure (PRDs and slices are already issues) and requires zero new repo files.

This ADR records the architectural response.

---

## Decisions

### D1: Forward-looking work queue lives as GitHub Issues with `backlog` label + Project board "Backlog" column

The work queue is **not a file in the repo.** It is GitHub Issues labeled `backlog`, organized on the project board's "Backlog" column. Specifically:

- A backlog item is a regular GitHub Issue with the `backlog` label.
- The Project board (currently #2) has a "Backlog" column option on the `Status` field.
- Item content is free-form markdown in the issue body. The body briefly captures: the item, optional grill-context where it surfaced, optional link to the motivating ADR section if any.
- Browse: `gh issue list --label backlog` or look at the Backlog column on the project board.
- Cross-reference to ADR Future-direction sections is bidirectional but manual — a backlog issue body MAY link back to the motivating ADR section; the ADR is never edited to add a link to the backlog issue.

**Rationale:** native integration with the existing PRD/Slice/PR issue workflow; zero new repo files; modern GitHub-native best practice (used by `github/roadmap`, `cli/cli`, and many small/mid teams). Promotion from backlog to PRD is a label change + grilling: `gh issue edit <N> --remove-label backlog --add-label prd` + `/grill-me #<N>` to refine the body into a proper PRD.

### D2: No explicit handoff document; sessions reconstruct state from live state

When a new Claude Code session opens (because the previous session's context filled, the user closed Claude, the machine restarted, etc.), the new agent reconstructs the prior session's state from **live system state**, not from any persisted handoff document:

- `git log --oneline -10` — recent commits + branch state
- `gh issue list --state open --label slice` — in-flight slices (slices not yet merged)
- `gh pr list --state open` — in-flight PRs (work currently under review)
- `gh issue list --label backlog` — forward queue (not-yet-started items)
- The project board's Status columns — visual state of in-flight work

**Rationale:** humans solo-developing don't keep a live handoff document either. Live state is rich and timely; a persistent handoff doc adds discipline overhead without solving the only case where it would matter (mid-grill interruption — conversational context is lost regardless of mechanism). The natural pipeline milestones (end of `/grill-me`, end of `/ship`, end of `/qa-plan`) always leave a new session in a state where live reconstruction is sufficient.

**Accepted trade-off:** the "intent capture" loss (what the previous session was about to do next) is real but unavoidable. None of the considered alternatives (committed `HANDOFF.md`, memory file, GitHub Issue, per-stage updates) solve the mid-grill case; for the pipeline's natural milestone cases, live state captures intent implicitly (the open PR's title says what's being worked on; the project board column shows what's blocked).

### D3: ADRs and backlog cross-reference bidirectionally

The artifacts serve different roles:

- **ADRs** record the *why*: deferred-from-decision items live in ADR "Future direction" + "Open questions deferred" sections, with the architectural rationale that produced them.
- **Backlog issues** record the *what's-next*: actionable forward items, optionally linking back to the motivating ADR section that produced them.

The cross-reference is bidirectional but **manually maintained**:

- A backlog issue body MAY link back to the motivating ADR section (e.g., "Per ADR-0005 D5 — defers post-PRD audit stage to PRD-C").
- ADR Future-direction sections are NEVER edited to add a link to a backlog issue (immutability — the ADR is frozen at decision time).
- Discoverability of "which ADR Future-direction items have been promoted to backlog" is via cross-reading: a maintainer reading an ADR's Future-direction section can search `gh issue list --label backlog` for matching items.

**No enforcement:** no mechanism keeps these in sync. If a backlog issue is created without linking back to its ADR, that's acceptable. If an ADR Future-direction item is never promoted to backlog, that's acceptable (it stays in the ADR as a record of considered but not actioned future direction).

### D4: Agent prompt convention — agents write backlog issues when they identify deferred work

The following subagents and skills are expected to create `backlog`-labeled issues when they identify items worth tracking but not addressing in the current PRD or pipeline cycle:

| Agent | Trigger |
|---|---|
| `/grill-me` skill | At end of each grill session, sweep surfaced-but-deferred items |
| `slicer` subagent | When a decomposition explicitly defers an item (e.g., "Item 3 deferred to PRD-C") |
| `slicer-critic` subagent | When WARN-flagging an item for follow-up that wasn't addressed in the chosen decomposition |
| `prd-critic` subagent | When Open questions surface during review that warrant future-PRD treatment |
| `adr-critic` subagent | When ADR Open questions surface during review that warrant future-PRD tracking |
| `reviewer` subagent | When non-blocking recommendations during PR review are meaningful follow-ups (not nitpicks) |
| `/qa-plan` skill | At PRD-close, sweep "Coverage gaps" and "Recommendation" sections of the QA plan for items that warrant backlog tracking |

Each agent gets a 1-2 line additive clause in its prompt body. The clauses are **discretionary** (the agent decides whether an item warrants a backlog issue), not mandatory. A future-PRD (e.g., a PRD-C audit-stage build) MAY tighten this to mandatory via a new mechanism, but ADR-0006 leaves it discretionary.

**Convention for backlog-issue body shape:** free-form markdown. Recommended (not enforced) sections:

- One-paragraph description of the item
- Optional: link to the motivating context (ADR section, grill-session date, PR comment)
- Optional: priority indicator or rough complexity sketch

Promotion convention: when a backlog issue is ready to become a PRD, relabel (`gh issue edit <N> --remove-label backlog --add-label prd`) then invoke `/grill-me #<N>` to refine the body into a proper 6-section PRD (per ADR-0005 D1 template).

### D5 (bootstrap): Bootstrap-mode acknowledgment for D1 and D4 enforcement

D1 (new backlog convention — label + project-board column become the canonical forward queue) and D4 (new per-agent prompt enforcement clauses across seven agents/skills) are **new enforcement mechanisms.** Per **ADR-0004 D2 bootstrap-mode policy**, each applies *forward from the moment the slice that ships it merges*; earlier slices of PRD-D — and PRD-D's own pipeline-stage outputs (the grill session that produced PRD-D, the slicer/critic runs gating PRD-D, the joint prd-critic + adr-critic gate gating ADR-0006 itself) — are grandfathered.

Specifically:

- **D1 (backlog convention):** the `backlog` label and project-board "Backlog" column come into force the moment slice 1 of PRD-D merges (the slice that runs `gh label create backlog` and adds the column). Earlier slices of PRD-D — by definition there are no earlier slices in this PRD — are not bound. PRD-D's own grill session and the joint critic gate gating this ADR ran before the convention existed; they are grandfathered.
- **D4 (per-agent prompt clauses):** each agent's prompt clause applies forward from the merge of the slice that adds it to that agent's file. Slice 1 ships the `/grill-me` clause. Subsequent slices ship the clauses for `slicer`, `slicer-critic`, `prd-critic`, `adr-critic`, `reviewer`, `/qa-plan`. Each agent gains canonical status at its respective merge. PRD-D's own slicer/critic/grill runs that necessarily precede these merges are grandfathered.
- **From PRD-D merge forward:** all future PRDs satisfy D1 + D4 from slice 1. The bootstrap exemption ends with PRD-D's last slice merging — one-way, one-time per mechanism, mirroring the pattern ADR-0004 D2 prescribes and ADR-0005 D4 demonstrated.

This decision legitimizes what would otherwise be silent policy violation during the construction phase. It mirrors ADR-0005 D4's structure verbatim — the recurring shape every ADR introducing new enforcement must include.

---

## Consequences

### Positive

- **Forward queue exists.** Grill-surfaced ideas, ADR-deferred items, and reviewer follow-ups now have a canonical home.
- **Aggregation view.** `gh issue list --label backlog` shows all queued work in one place; the project board's Backlog column visualizes it.
- **Zero new files in repo.** Aligns with the "fewer files" preference established during the grill; aligns with modern GitHub-native best practice.
- **Session continuity is documented.** New agent sessions know to reconstruct from live state — the procedure is in CLAUDE.md, not folklore.
- **Backlog → PRD flow is clean.** Relabel + `/grill-me` is one command pair. The issue retains its number, comment history, and any prior cross-references.
- **ADRs keep their job.** Future-direction sections remain the canonical "why" record; backlog issues record the actionable "what's-next." No duplication of rationale.

### Negative / accepted trade-offs

- **Cross-reference drift is possible.** ADR ↔ backlog links are manual; an ADR's Future-direction item might never get promoted to backlog (and that's fine), or a backlog item might lose its ADR link over time. Mitigation: cross-reading on demand; no mechanical sync.
- **Intent-capture for mid-task interruption is lost.** D2 accepts that mid-grill or mid-slice interruption loses conversational state regardless of mechanism. The alternative (formal handoff doc updated at every stage) was rejected for being heavier than the rare benefit justifies.
- **Discoverability of the convention by future agents** — a not-yet-built agent (e.g., a future `implementer`) won't automatically know to write backlog issues. Mitigation: a brief mention in CLAUDE.md's pipeline operational logic; future agents inherit the convention via prompt-edits when they ship.
- **Sorting / prioritization is manual.** The Backlog column shows items in GitHub's default order (typically creation date). Priority emerges from human (or future-grill-me) re-ordering during grill sessions, not from any mechanical priority field. Acceptable for the project's solo-dev scale.
- **No backlog item lifecycle automation.** Items close on promotion (label change) or manual won't-fix. No TTL, no automatic stale-flag. Backlog cleanup is a periodic human responsibility.

---

## Alternatives considered

### Alt-A: `BACKLOG.md` file in repo

Rejected per grill Q4 (4A). Familiar pattern, but adds a file against the user's "fewer files" preference and loses the project-board integration that GitHub Issues provide.

### Alt-B: `HANDOFF.md` file in repo (committed; updated at session end)

Rejected per grill Q3 (3C). High git churn for low value: live state already captures most of what handoff would record at natural pipeline milestones; mid-task interruption isn't solved by any handoff mechanism.

### Alt-C: Persistent memory file (`~/.claude/projects/.../memory/handoff.md`)

Rejected per grill Q2/Q3. Machine-local; doesn't travel with clone (against the project's clone-as-template DNA per ADR-0001 D1).

### Alt-D: Pinned GitHub Issue or Discussion for handoff/backlog state

Rejected per grill Q2. Not auto-loaded by Claude Code; manual fetch on every session start adds friction without clear benefit over the labeled-issue approach.

### Alt-E: Section in CLAUDE.md for backlog and/or handoff

Rejected per grill Q3/Q4. CLAUDE.md is for stable rules; high-churn state in CLAUDE.md bloats it and conflates "rules" with "live state." A "Session continuity" sub-section that describes the *procedure* (not the live state itself) is acceptable and is included in PRD-D.

### Alt-F: ADRs alone (no separate backlog)

Rejected per grill Q4 (4C). ADRs capture deferred-from-decision items but fall short for new ideas not tied to any decision and for aggregation across multiple ADRs.

### Alt-G: Hybrid (ADRs primary + `backlog` label as actionable index)

Considered per grill Q4 (4D). Defensible — but the bidirectional cross-reference convention in D3 achieves the same hybrid outcome with less ceremony. D3 IS the hybrid; just made minimal.

### Alt-H: Strict per-item schema for backlog-issue body shape

Rejected per PRD §3 + PRD §6 rabbit-hole. Free-form markdown matches how humans use TODO.md and how GitHub Issues work. Schema enforcement is overkill for solo-dev scale.

### Alt-I: Automated promotion from backlog to PRD

Rejected per PRD §3 + ADR-0006 D4. Promotion always involves human-supervised grilling (`/grill-me #<N>`) to refine the backlog body into a proper PRD per the 6-section template. Automation would skip the grilling step, which is where the design clarity actually happens.

### Alt-J: New reviewer hard-block rule R-BACKLOG enforcing backlog-issue creation

Rejected per PRD §6 rabbit-hole. The backlog convention is a *recommendation* in critic outputs, not a hard requirement. Hard-blocking on missing-backlog-issue would force false positives (every "we might also want to do X" inline thought becomes a tracked item). Discretion is the right discipline level.

---

## Open questions deferred

| Question | Deferred to |
|---|---|
| Whether "Backlog" column on project board should be leftmost (before Todo) or between Todo and In Progress | Slice 1 implementation; recommend leftmost |
| Whether promotion mechanic should be in-place relabel or new-issue-from-template | Slice 1 implementation; recommend in-place relabel |
| Whether non-canonical agents (future `implementer` and beyond) inherit the backlog-write convention automatically | When such agent ships; their prompt-spec PRD includes the clause |
| Whether to retroactively sweep ADR-0001 through ADR-0005 "Future direction" sections and create matching backlog issues | Manual; no mechanism required. Recommend creating at least PRD-C's backlog issue (post-PRD audit + boy-scout-rule) as a demonstration during slice 1 |
| Whether to introduce a `backlog-stale` label or TTL convention for items that linger | Future PRD if backlog grooming becomes a real problem (probably not for years at solo-dev scale) |

---

## Future direction

- **Backlog sorting / priority** — if backlog grows past 20-30 items, may warrant explicit priority labels (`priority:high` / `priority:medium`) or a dedicated priority field on the Project board. Premature today.
- **Auto-creating backlog issues from ADR commits** — a future tooling addition (GitHub Action when a new ADR ships) could auto-create backlog issues from each Future-direction bullet. Bigger investment; defer until ADR Future-direction items routinely get missed.
- **Backlog refinement skill** — a `/refine-backlog` skill that walks the human through deciding which backlog item to promote next, similar to `/grill-me` but for prioritization. Defer until the backlog has enough items to make refinement non-trivial.

---

## References

- [ADR-0001](0001-foundational-design.md) — D8 (orientation artifacts) is what this ADR extends
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) — D8 (ADR placement) is reinforced; backlog is complementary
- [ADR-0004](0004-bypass-prevention.md) — D1 (adr-critic) gates this ADR's draft in the joint critic loop; D2 (bootstrap-mode policy) is the source pattern this ADR's D5 cites
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) — D3 (cascade-doc check) applies — slicer identifies README as a cascade-doc; D5 names the items (PRD-C, item 3, etc.) that become this PRD-D's first backlog issues
- [`decisions/README.md`](README.md) — ADR conventions; immutability invariant
- PRD-D issue (TBD — to be created by `/to-prd` after joint critic approval)
- Grill session "Session state management" — 2026-05-14 (this conversation)
- Industry references: `github/roadmap` (issues + labels + project board pattern); `cli/cli`'s backlog handling; `github/docs` issue triage
