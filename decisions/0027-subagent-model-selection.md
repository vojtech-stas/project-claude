# ADR-0027: Subagent model selection — Sonnet 4.6 / Haiku two-tier assignment policy + capability truth-doc

- **Status:** Accepted
- **Date:** 2026-05-26
- **Supersedes:** none
- **Extends:** [ADR-0001](0001-foundational-design.md) D6 (subagent definition + tool boundaries — this ADR adds `model:` selection alongside tool boundaries as a frontmatter convention); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer + role classification — model assignment respects critic vs generator role); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule honored per D8 below — no new critic added); [ADR-0011](0011-subagent-quality-framework.md) D4 (audit-subagents 10-check rubric — future PRD may extend with model-field presence check); [ADR-0022](0022-docs-first-kb-pattern.md) D1 (per-topic on-demand-load — capability truth-doc auto-loads via topic-nudge hook per ADR-0026 D4); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1 (truth-doc surface — this ADR ships the `subagents` topic's truth-doc alongside per D7 bootstrap-mode forward); [ADR-0026](0026-knowledge-architecture-truth-docs.md) D2 + D5 (R-TRUTH-DOC enforcement — this PR self-satisfies by touching both `decisions/0027-*.md` and `docs/current/subagents.md`).

## Context

User stated (2026-05-26): *"I feel that the implementers should be Sonnet 4.6 and some small tasks can be even Haiku model so we increase the speed of the workflow"* and *"we should have some table of subagents and skills that will tell me who can do what and why we have chosen what model."*

Current state on `origin/main`:
- 10 subagents total (6 critics + 4 generators per ADR-0008 D7 6-critic-cap)
- All 10 already have `model:` frontmatter (the field exists; ADR-0001 D6 implicitly established it via existing agents)
- 8 use `model: opus`; 2 use `model: sonnet`
- No ADR codifies WHICH model goes where or WHY

Three pains:
1. **Opus dominates → autonomous runs slow.** 5+ subagent dispatches per PRD pipeline × ~2-5x Opus latency vs Sonnet = wall-clock multiplier on autonomous runs (10hr → ~5hr if right-sized).
2. **No documented rationale for model selection.** New subagents added in future have no anchor.
3. **No single-page capability reference.** Auditors + new contributors must grep 10 files to see who-does-what.

This ADR codifies a two-tier model assignment policy (Sonnet 4.6 reasoning-tier / Haiku mechanical-tier; Opus reserved for future explicit justification), and ships a `docs/current/subagents.md` capability truth-doc as the canonical "who can do what + why this model" reference. The capability truth-doc is the FIRST topic backfill PRD per ADR-0026 D7 bootstrap-mode forward — `subagents` is the second `docs/current/<topic>.md` topic (qa-automation was the first per PRD-K).

## Decisions

### D1: Frontmatter `model:` field is mandatory + explicit per subagent

Per ADR-0001 D6 subagent definition (which establishes the frontmatter convention), every `.claude/agents/<name>.md` MUST declare `model:` in its frontmatter. The value MUST be one of: `sonnet`, `haiku`, or `opus` (short aliases for forward-compat as model versions revise). Implicit-default / inherited-from-main model is NOT acceptable.

All 10 current agents already satisfy this (existing baseline). Future agents added must include `model:` per this ADR.

### D2: Two-tier assignment policy (Sonnet reasoning-tier / Haiku mechanical-tier)

The policy: assign Sonnet OR Haiku per the role's reasoning load.

**Sonnet 4.6 reasoning-tier** when the subagent:
- Performs multi-file judgment (multi-criterion rubric scoring, cross-file consistency analysis)
- Requires reasoning chains ≥3 steps
- Generates substantive new content (code, decompositions, ADR critiques)
- Drives complex orchestration (slicer N=3 decompositions, implementer file-editing)

**Haiku mechanical-tier** when the subagent:
- Executes structured single-item audit (single-term, single-issue, single-file)
- Performs mechanical retrieval + structured output (file-read + ≤15-line synthesis)
- Bounded ≤5-criterion rubric on a single artifact

**Opus reserved tier** — not used in current assignments. Future ADR may promote a subagent to Opus only with explicit justification meeting bar: "Sonnet 4.6 has been observed underperforming on this specific role with concrete evidence."

### D3: Per-agent assignment (10 agents → 7 Sonnet + 3 Haiku)

**Sonnet 4.6 (7):**
- `reviewer` — multi-file PR diff + 12-rule rubric + cross-ADR consistency
- `prd-critic` — 6-section template + 9-criterion rubric + ADR cross-consistency
- `adr-critic` — convention compliance + cross-ADR consistency + supersession + D-ID verification
- `slicer-critic` — 10-criterion rubric × N decompositions + INVEST analysis
- `slicer` — N=3 decomposition generation + INVEST + cascade-doc identification
- `implementer` — code-editing + multi-file judgment + commit/PR plumbing (per user req #8)
- `qa-tester` — dual-mode: bash-mode mechanical + ui-mode Playwright + LLM-judge screenshots; model = max-of-modes

**Haiku (3):**
- `glossary-critic` — 5-rule rubric on a single term — structured single-item audit
- `backlog-critic` — 4-criterion rubric on a single item — structured single-item audit
- `current-state-reader` — single-file read + ≤15-line synthesis — structured output

Critic vs generator distribution: 6 critics (4 Sonnet + 2 Haiku); 4 generators (3 Sonnet + 1 Haiku).

### D4: `docs/current/subagents.md` truth-doc — capability table

Per ADR-0026 D1 truth-doc format. Single H1 / Status / Date / Active synthesis (markdown table) / Sources. Table columns: name | role | model | tools | when invoked | why this model. Lists all 10 subagents.

Per ADR-0026 D7 bootstrap-mode forward: this is the second per-topic truth-doc (after `qa-automation.md` from PRD-K). The `subagents` topic is the second `docs/current/<topic>.md` to ship; backfill continues organically per future PRDs touching their respective topics.

### D5: `.claude/topics.json` gains `subagents` entry

Per ADR-0026 D4 topic-nudge hook. New entry:
```json
"subagents": ["subagent", "subagents", "agent capability", "which model", "haiku vs sonnet", "tool boundaries"]
```
Implementer judgment on exact keyword list (precision tradeoff per PRD-LM OQ-3).

Wires the topic-nudge hook to dispatch `current-state-reader` with topic=`subagents` whenever those keywords appear in a user prompt.

### D6: R-TRUTH-DOC self-satisfaction (per ADR-0026 D2 + D5)

This PR introduces ADR-0027 (`decisions/0027-subagent-model-selection.md`) AND introduces the corresponding truth-doc (`docs/current/subagents.md`) in the same commit. Per ADR-0026 D2 + D5: ADR change + truth-doc change in same PR → R-TRUTH-DOC SATISFIED.

This is the inaugural application of R-TRUTH-DOC on a new-topic ADR (PRD-K's PR was the rule's introduction; PRD-LM's PR is the first to exercise it for a topic backfill).

### D7: Bootstrap-mode acknowledgment (per ADR-0004 D2)

Model assignments bind FORWARD from the slice that ships them:
- All 10 current agents updated in slice 1 of PRD-LM (forward = immediate at merge)
- Future agents added MUST specify `model: sonnet` or `model: haiku` (or `opus` with explicit justification per D2) in frontmatter
- No retroactive promotion / demotion sweep beyond the 10 current agents
- `/audit-subagents` rubric extension to check `model:` field presence is FUTURE PRD (captured if drift observed)

### D8: 6-critic-cap honored per ADR-0008 D7

This ADR adds NO new critic. The 6 critics on main remain: reviewer, prd-critic, adr-critic, slicer-critic, glossary-critic, backlog-critic. Model assignments don't change critic count.

`current-state-reader` was already the 4th generator per ADR-0026 D8 (count of generators moved from 3 to 4); ADR-0027 doesn't add a generator either. Total subagent count remains 10 (6 + 4).

### D9: Cascade-doc updates

- `.claude/agents/<all 10 names>.md` — `model:` field update per D3 (one-line edit each; 10 files)
- `decisions/0027-subagent-model-selection.md` — this ADR file (NEW)
- `decisions/README.md` — ADR-0027 index row appended in numerical order
- `docs/current/subagents.md` — NEW truth-doc per D4
- `.claude/topics.json` — new `subagents` entry per D5
- `CLAUDE.md` — Map row updates optional per PRD-LM OQ-4 (recommend NO; truth-doc is canonical reference; CLAUDE.md slim is PRD-R territory)
- `README.md` — NOT updated (truth-doc surface generically mentioned by PRD-N; per-topic mentions belong in truth-docs themselves)

### D10: Relationship to existing surfaces

- **ADR-0001 D6 subagent definition + tool boundaries** preserved unchanged. ADR-0027 ADDS `model:` as a mandatory frontmatter field alongside tool boundaries; doesn't change tool sets.
- **ADR-0008 D7 6-critic-cap** preserved unchanged per D8.
- **ADR-0011 D4 audit-subagents 10-check rubric** unchanged; rubric extension for `model:` field check is FUTURE PRD per D7.
- **ADR-0026 truth-doc surface** EXTENDED — `subagents.md` is the second `docs/current/<topic>.md` topic to ship.
- **`/best-practice-subagents` skill (per ADR-0022 D3)** unchanged. The skill answers "what does Anthropic recommend for subagent design?" (external distillation); this ADR + truth-doc answers "what's our current subagent capability + model assignment?" (internal state synthesis). The two surfaces coexist per ADR-0026 D10.

## Consequences

### Positive

- **Autonomous runs 2-5x faster** for Sonnet-assigned subagents vs prior Opus default.
- **Model selection codified** — new subagents have anchor for choosing tier.
- **Single-page capability reference** — `docs/current/subagents.md` answers "who can do what + why this model" without grepping.
- **Bootstrap-mode forward** — clean policy boundary; no retroactive churn beyond current 10.
- **6-critic-cap preserved** — no new critic; no subagent role change.
- **R-TRUTH-DOC inaugural exercise on topic backfill** — proves PRD-K's mechanism works for the second topic.
- **Cost reduction** — Haiku assignments cut per-dispatch cost ~10x for the 3 mechanical agents.

### Negative / Accepted

- **Quality risk on Haiku-assigned agents.** Single-term/single-item audits at Haiku may produce lower-quality verdicts than Sonnet equivalents. Mitigated by D2 explicit tier criteria + OQ-5 escalation path (re-promote to Sonnet via follow-up PRD if observed). Accepted given speed/cost benefit.
- **Tier-criteria edge cases.** Some subagents straddle the tier boundary (e.g., glossary-critic at 5-rule rubric is borderline). Mitigated by D2 explicit policy + OQ-5 escalation if Haiku underperforms.
- **`qa-tester` model = max-of-modes** — ui-mode forces Sonnet even though bash-mode could be Haiku. Accepted; per-mode model selection is YAGNI per PRD-LM §3.
- **No retroactive Opus removal** — Opus tier reserved but unused. Future ADR may remove the tier entirely if no use case materializes.
- **Migration burden if Anthropic deprecates Sonnet 4.6** — short alias `sonnet` would resolve to whatever Sonnet version is current. Forward-compatible; no per-ADR version pinning.
- **Truth-doc maintenance overhead** — any subagent role/tool/model change requires updating `docs/current/subagents.md` per R-TRUTH-DOC. Captured cost; small per change.

## Alternatives considered

- **Alt-A: Keep everything on Opus.** Rejected per user req #8: workflow speed dominates over marginal quality gain.
- **Alt-B: Everything on Haiku.** Rejected — multi-file reasoning rubrics (reviewer, slicer-critic, etc.) require Sonnet-level reasoning to maintain quality.
- **Alt-C: Three-tier policy with Opus as a third tier for "highest-stakes" agents.** Rejected — no current subagent's role demonstrably needs Opus over Sonnet; introducing a 3-tier policy without a current use case is YAGNI. Reserved per D2.
- **Alt-D: Per-mode model selection within a single subagent** (e.g., qa-tester bash-mode = Haiku, ui-mode = Sonnet). Rejected per PRD-LM §3 as YAGNI; max-of-modes per D3 chosen.
- **Alt-E: Skip the truth-doc; just update frontmatter + ADR.** Rejected — user req #9 explicitly calls for a capability table; ADR alone is too dense for quick reference; truth-doc is the right surface per ADR-0026 D1.
- **Alt-F: Skill-based capability reference (`/list-subagents` skill).** Rejected — truth-doc is the canonical pattern per ADR-0026; a separate skill duplicates without adding query convenience (current-state-reader subagent already provides slim-context query).
- **Alt-G: Empirical benchmarking before assignment.** Rejected — design-intent decision per D2 policy; benchmarking gates ARE captured (OQ-5 escalation if Haiku assignment underperforms in dogfood).
- **Alt-H: Extend `/audit-subagents` 10-check rubric to verify `model:` field in same PRD.** Rejected — separate concern; captured for future PRD if drift observed. PRD-LM scope is model assignment + truth-doc only.
- **Alt-I: New 7th critic for model-selection-correctness.** Rejected per D8 — breaches ADR-0008 D7 6-critic-cap; `/audit-meta` rule extension is the right home if mechanical drift-check ever needed.
- **Alt-J: README.md edits referencing model tier.** Rejected — README ships once-per-week-ish; truth-doc surface (per ADR-0026) is the canonical drift-resistant reference. PRD-LM §3 explicitly OUT.

## Open questions deferred

- **OQ-1: Model name format.** Implementer judgment (recommend short alias `sonnet` / `haiku` for forward-compat).
- **OQ-2: Truth-doc table column order.** Implementer judgment.
- **OQ-3: topics.json keyword list precision.** Implementer judgment.
- **OQ-4: CLAUDE.md Map row model notation.** Recommend NO; truth-doc is canonical.
- **OQ-5: current-state-reader Haiku quality.** Implementer dogfoods; if synthesis quality drops, captures per rule #13.
- **OQ-6: qa-tester model.** Stays Sonnet (ui-mode dominates).

## Future direction

- **`/audit-subagents` rubric extension** — add a CRIT-N / ALL-N check for `model:` field presence (mechanical grep); fits the 10-check rubric pattern.
- **`docs/current/skills.md` truth-doc** — companion to subagents.md; covers the 14 skills (similar table shape: name / model-N/A / tools-implicit / when invoked / what it does).
- **Per-mode model selection in qa-tester** — if bash-mode runs prove slow at Sonnet, future PRD may add per-mode `model:` field semantics.
- **Empirical benchmarking** — future PRD may run controlled comparisons (Sonnet vs Haiku on same input) for the 3 Haiku-assigned agents; promote/demote based on results.
- **Opus tier activation** — future ADR may promote a specific subagent to Opus with concrete justification (e.g., adr-critic if D-ID accuracy drops; reviewer if multi-file judgment errors increase).
- **Model alias semantics in Claude Code** — if Anthropic ships explicit version aliases (e.g., `sonnet-4.6`, `sonnet-4.7`), this ADR may be amended to pin specific versions where stability matters.

## References

- 2026-05-26 user request (verbatim cited in §1) — design provenance
- [ADR-0001](0001-foundational-design.md) D6 — subagent definition + tool boundaries (this ADR extends with `model:`)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR / CRITIC role classification (model assignment honors)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule (preserved per D8)
- [ADR-0011](0011-subagent-quality-framework.md) D4 — audit-subagents 10-check rubric (future PRD may extend per D7)
- [ADR-0022](0022-docs-first-kb-pattern.md) D1 — per-topic best-practice skill pattern (`best-practice-subagents` is the external-distillation sibling)
- [ADR-0026](0026-knowledge-architecture-truth-docs.md) D1+D4+D5+D7 — truth-doc surface, topic-nudge hook, R-TRUTH-DOC enforcement, bootstrap-mode forward (all extended)
- [decisions/README.md](README.md) *"What an ADR is"* — ADR immutability convention
- `.claude/agents/<all 10 names>.md` — files edited by PRD-LM slice 1
- `docs/current/subagents.md` — file created by PRD-LM slice 1 per D4
- `.claude/topics.json` — file edited by PRD-LM slice 1 per D5
- `decisions/README.md` — file edited by PRD-LM slice 1 per D9
