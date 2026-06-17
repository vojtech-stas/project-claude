---
id: "ADR-0008"
status: "accepted"
supersedes: []
superseded_by: []
scope: "capture"
rule_ids:
  - "CAP-003"
  - "CAP-004"
---
# ADR-0008: Workflow polish — auto-log captured→backlog autopilot + bootstrap.sh + naming convention

- **Status:** Accepted
- **Date:** 2026-05-16
- **Extends:** [ADR-0001](0001-foundational-design.md) D8 (orientation artifacts); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (critic per generation stage — extended here to consumption stage); [ADR-0006](0006-backlog-and-session-continuity.md) D4 (write convention pattern — target shifts to captured tier)
- **Supersedes:** none. [ADR-0006](0006-backlog-and-session-continuity.md) D1's "backlog = single GitHub-Issues queue" is REFRAMED with the two-tier architecture introduced here, but D1 remains operationally correct — it just describes only the curated (post-promotion) tier under the new architecture.

## Context

PRD-workflow bundles three concerns the user surfaced during the 2026-05-15 session and the 2026-05-16 grill:

1. **Auto-log to backlog.** [ADR-0006](0006-backlog-and-session-continuity.md) D4 established that agents discretionarily *surface* deferred work to the backlog. In practice this requires user-attention-as-bottleneck: the user must decide-per-item to capture. The user's stated desire — *"everytime we find some new thing to implement it will automatically log it to the backlog"* — demands more automation. Pure automation without judgment, however, floods the backlog with noise. A two-tier mechanism with an autopilot critic resolves the tension.
2. **bootstrap.sh.** A fresh clone of this repo currently requires manual configuration of labels, git hooks (`.githooks` install), project board v2 with columns, and branch protection rules. The user explicitly asked: *"If we clone this repo, will someone that doesnt have setup github, will he be able to set everything up the same as I did simply by some simple installation guide?"*
3. **Naming convention.** The user observed an inconsistency: *"I see the backlog is called PRD-C not sure why the naming convention is different."* Posted PRDs followed the canonical `PRD: <title>` pattern; the backlog item #47 carried a session codename `PRD-C —` prefix. During the grill the user identified the deeper problem — codenames in backlog titles biased candidate selection ("PRD-C reads like 'this WILL be next'"). The fix is to keep codenames in conversation only.

The user explicitly chose to bundle all three into one PRD (PRD-workflow grill Q1 = 1A) over the recommendation to split. The multi-feature-PRD smell from `CLAUDE.md` is acknowledged on the record. The three concerns share the theme *"workflow polish around forward-looking work and onboarding"* and are bundled accordingly.

The grill traversed a sub-decision arc on the auto-log critic location: starting from "critic at promotion" (Q3 = 3A), the user asked whether this matched human best practice. Investigation showed that mature workflows (GTD, Linear/Jira triage, Shape Up, OSS-project triage) all use *human* triage at promotion — no team uses a "promotion critic" with an APPROVE/BLOCK rubric. But the user's *automation* intent + tolerance for captured-tier noise + observation that *"some information that is not that important won't destroy the work"* pushed toward an autopilot pattern (Q5 = 5E): the critic auto-promotes silently, captured tier becomes a *graveyard of critic-rejects* rather than an inbox.

## Decisions

### D1: Two-tier captured → backlog architecture

The backlog mechanism is split into two GitHub-labeled tiers:

- **`captured` tier** — low-friction. Agents (and the user) auto-write items via `gh issue create --label captured`. No bar at write time. After auto-promotion by D2's critic, this tier contains only critic-rejects (items the autopilot found insufficient).
- **`backlog` tier** — curated. Items here have passed the autopilot critic. This is the pool consumed by `/grill-me` when selecting the next PRD candidate.

The tiers are GitHub Issues distinguished by label; promotion is a label swap. Both tiers render as columns on project board v2 #2 (new `Captured` column alongside existing `Backlog`).

**Inverts the usual inbox-queue semantics.** Captured ISN'T the inbox of new ideas — it's the graveyard of items the autopilot rejected. The end-state of a healthy system is: backlog has the items worth considering; captured has items the critic was uncertain about, awaiting lazy human review (cull or rescue). This is non-obvious and the source of the architecture's leverage.

### D2: Critic auto-promotes (autopilot)

A new subagent `backlog-critic` evaluates every newly-written captured item:
- **APPROVE** → the invoking context immediately swaps labels `captured` → `backlog` via `gh issue edit --remove-label captured --add-label backlog`. The item lands in the curated backlog pool.
- **BLOCK** → the critic's verdict is posted as a comment on the issue; the item stays labeled `captured`. The user reviews the captured tier on whatever cadence they prefer (no mandatory ritual) and decides per-item: cull (close) or rescue (manually relabel to `backlog`).

No human is in the loop on the APPROVE path. The user has full control on the BLOCK path. This matches the user's *"automatic"* intent while preserving signal in the curated backlog.

**The autopilot's bias.** `backlog-critic` defaults to BLOCK if uncertain (per D4 rubric criterion default). False-positives pollute the backlog directly and force the user to cull from the curated tier (high friction). False-negatives stay in captured and are recoverable by lazy review (low friction). Conservative-default is the asymmetric correct choice.

### D3: Inline firing in same agent context

The `backlog-critic` fires inside the same agent invocation that wrote the capture. Operationally: whatever agent (subagent, skill, or main Claude) runs `gh issue create --label captured`, that same agent — in the same turn — invokes `backlog-critic` against the freshly-created issue and acts on the verdict.

No external infrastructure: no webhook, no GitHub Actions, no daemon, no polling. The mechanism uses only tools that already exist (`Agent` invocation + `gh issue edit`).

Captures originating outside an active agent context (e.g., the user runs `gh issue create --label captured` directly from terminal; future webhook integrations) are NOT auto-processed by this mechanism. They sit in the captured tier until either (a) the user manually triggers the critic against them, or (b) a future session-start sweep skill is added (noted as future direction in Open questions deferred).

### D4: `backlog-critic` rubric

Four criteria; default-conservative (BLOCK if any uncertain):

1. **Actionable** — the item describes something *doable*, not just an observation. "We should improve testing" is BLOCK; "Add property-based tests for the SPIDR-split logic in `slicer.md`" is PASS.
2. **Scoped** — the item is PRD-size or a sub-feature, not a one-line tweak (those belong in the I3 trivial lane, not the backlog). And not so large it requires multiple PRDs to even sketch.
3. **Not duplicate** — `grep` against open `backlog` + `captured` issues finds no semantic duplicate. The critic states the search performed in its verdict.
4. **Clear** — a future `/grill-me` session has enough purchase to begin grilling without re-asking what the item is. Implicit context from the source conversation must be made explicit in the issue body.

`backlog-critic` outputs the canonical 5-section verdict + CRITIC trailer per [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1. Round counter omitted (the autopilot runs at most once per item — there is no loop). Escalation surface is non-applicable in autopilot mode; the user is the escalation path (manual rescue from captured).

### D5: Backlog issue titles are descriptive only

Backlog-labeled issues use descriptive titles only. No codename prefixes (`PRD-C —`), no topical classifiers (`PRD-qa-automation:`). The single pattern is: a clear short noun phrase that names what the item IS.

Session codenames (PRD-A, PRD-B, PRD-C, PRD-D, …) are conversation/transcript shortcuts only. They never appear in tracked artifact titles. On promotion `backlog` → `prd`, the title becomes the canonical `PRD: <descriptive title>` form per existing convention.

Rationale: the user identified that codenames in backlog titles pre-bias candidate selection — they read as "this WILL be next" rather than "this is a candidate". The backlog must function as a neutral pool from which `/grill-me` picks based on current priorities, not based on historical codename ordering.

### D6: bootstrap.sh scope

A `bootstrap.sh` at repo root that a contributor runs after `git clone` to bring the local environment to a usable state. Scope:

- Create GitHub labels: `prd`, `slice`, `backlog`, `captured`, `trivial`, `needs-human` (idempotent: `gh label create` skips existing)
- Install git hooks: `git config core.hooksPath .githooks`
- Create / configure GitHub Project v2 board with columns `Backlog`, `Captured`, `Todo`, `In Progress`, `Done` (skips if board already exists)
- Apply branch protection rules R1+R2 to `main` via `gh api` (R1 = require PR; R2 = no force-push). Warn-and-proceed if the contributor lacks admin permission rather than hard-fail.
- Sanity checks: verify `gh auth status` passes; verify the script is being run from the repo root; warn if not.

Shell: **bash** (for cross-platform contributor portability — Windows contributors can run via Git Bash). Idempotency: every action wraps in a "check first, act if missing" pattern. Failure mode: best-effort with explicit per-step warnings; the script never aborts on a single-step failure.

**Explicitly NOT in scope:**
- Matt Pocock skills installation (user-level concern, not project-level)
- MCP server configuration (user-level)
- CI / GitHub Actions / bot identity creation (deferred to PRD-CI)
- Any modification of user-global git config (`--global`)
- Branch protection R3 (require status checks) or R4 (require non-author review) — both depend on CI infrastructure deferred to PRD-CI

### D7: Meta-rule on critic count

`backlog-critic` is the 6th critic in the project (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`). [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md)'s Negative Consequences explicitly stated *"a 6th would warrant explicit pushback"*. We pushed back during the grill (Q5 asked "how do humans do this? is it best practice?") and concluded that the autopilot pattern's leverage — automatic at promotion, asymmetric-default-BLOCK rejecting to a recoverable captured tier — justifies the count breach.

To prevent open-ended critic proliferation, this ADR establishes a **meta-rule**: promoting a 7th critic requires a new ADR that explicitly justifies why an existing critic's rubric cannot absorb the concern. The default disposition for future critic-shaped problems is "extend an existing critic"; net-new subagents are the exception, not the rule.

### D8: Bootstrap-mode acknowledgment (per [ADR-0004](0004-bypass-prevention.md) D2)

The new enforcement mechanisms introduced in this ADR bind FORWARD from the slice that ships them. Earlier slices/PRDs are grandfathered. Specifically:

- **D2's autopilot critic enforcement and D3's inline-firing convention** bind forward from PRD-workflow slice 1. Captures written before slice 1 lands (none expected; the captured tier doesn't exist yet) would not be retroactively processed.
- **ADR-0006 D4's existing surfacing convention is amended forward:** the enumerated agents (`/grill-me`, `slicer`, `slicer-critic`, `prd-critic`, `adr-critic`, `reviewer`, `qa-plan`, plus `glossary-critic` and `main Claude`) will, in subsequent slices or future PRDs that touch their prompts, have their target shifted from `backlog` (per ADR-0006 D4) to `captured` (per this ADR) plus the inline-critic-invocation step. No retroactive prompt sweep across pre-existing prompts.
- **D5's title convention** binds forward from PRD-workflow slice 3 (the naming-convention CLAUDE.md edit). Existing tracked titles in `backlog` issues at the moment of slice-3 merge have been brought into compliance during the 2026-05-16 grill (#47 and #57 renamed to drop codename/classifier prefixes); no retroactive sweep beyond that.
- **D6's bootstrap.sh** doesn't enforce anything against existing repo state — it only sets up state for a fresh clone. Idempotent operation means re-running on an existing clone is safe.
- **D7's meta-rule on critic count** binds forward — applies to any 7th-critic proposal from this ADR's acceptance onward.

## Consequences

**Positive:**
- Auto-log delivers on the user's *"automatic"* intent without flooding the curated backlog (D2's autopilot + D4's default-conservative critic).
- The captured tier as graveyard-of-rejects is a recoverable failure mode — false-negatives don't lose data, they just sit in a place the user can rescue from.
- `bootstrap.sh` makes the project usable from a clean clone in one command (per the user's stated onboarding goal).
- Backlog as neutral candidate pool (D5) preserves selection neutrality — `/grill-me` picks based on current priorities, not historical codename ordering.
- The 6-critic meta-rule (D7) makes critic-count expansion intentional rather than incremental.

**Negative:**
- 6 critics is a real maintenance burden; the meta-rule (D7) helps but doesn't eliminate the cost.
- The two-tier architecture (D1) is non-obvious — the captured tier's semantics (graveyard, not inbox) requires reading this ADR to understand.
- `backlog-critic` false-positives pollute the curated backlog with no automatic recourse — user has to manually cull from `backlog`. The default-conservative rubric mitigates but doesn't eliminate this.
- Inline-firing (D3) leaves a gap for non-agent captures (e.g., user creates a `captured`-labeled issue manually) — those won't be auto-processed without explicit action.
- Multi-feature PRD-workflow (Q1=1A) deviates from the "Multi-feature PRDs are a smell" rule. Bundling is a deliberate user choice; the smell is on record.

**Neutral:**
- `bootstrap.sh` adds a new top-level repo artifact but only at the cost of one file (one Map row in CLAUDE.md, no skill or subagent created).
- Branch protection R3+R4, CI, bot identity — explicitly deferred to PRD-CI; no scope creep here.

## Alternatives considered

- **Alt-A: Single-tier backlog with stronger automation (no captured tier).** Rejected per grill Q2: floods curated backlog with noise; defeats signal value. The user explicitly preferred two-tier even when offered the simpler one-tier.
- **Alt-B: Two-tier with critic gating promotion via user-invoked skill (not autopilot).** Rejected per grill Q5: doesn't match the user's *"automatic"* intent; just moves user-attention from "decide to capture" to "decide to invoke `/promote`".
- **Alt-C: No critic — pure manual triage of captured tier.** This is human-team best practice (GTD, Linear, Shape Up). Rejected per grill Q5 + the user's *"I want this automatic"* clarification: the user explicitly wants the autopilot, not a triage ritual.
- **Alt-D: `CAPTURED.md` file at repo root instead of labeled issues.** Rejected per grill Q4 on rule-#10 conflict — agents cannot hand-author tracked files, so file-append would require PR ceremony defeating low-friction.
- **Alt-E: Comments on a single "captures" tracking issue.** Rejected per grill Q4: comments aren't individually labelable, assignable, or boardable; doesn't fit project-board model.
- **Alt-F: GitHub Actions webhook on label-change.** Rejected per grill Q6 + multiple prior PRD §3 non-goals on CI: out of scope; PRD-CI is the explicit successor.
- **Alt-G: Drop codename concept entirely.** Rejected per grill Q8: codenames are useful as session-local shortcuts. Solution is to scope them to conversation, not eliminate them.
- **Alt-H: Codenames in PRD title prefix derived from issue number (e.g., `PRD-3:`).** Rejected per grill Q8: redundant ("PRD-3" reads ambiguously as either codename or issue number); doesn't actually solve the backlog-title inconsistency the user raised.
- **Alt-I: Extend an existing critic (`reviewer` with `R-BACKLOG-PROMOTE`) instead of a new subagent.** Reviewer fires on PRs, not label-changes; the promotion is a label swap with no PR. Either we'd force the promotion through a PR (heavy ceremony for a label swap), or invent a label-change-reviewer hook (not the reviewer's contract). A dedicated `backlog-critic` invoked from the autopilot is the cleaner mechanism.
- **Alt-J: bootstrap.sh as `--minimal | --standard | --full` tiered command.** Rejected per grill Q7: decision-fatigue for the contributor; standard scope is right-sized.
- **Alt-K: Include Matt Pocock skills install in bootstrap.sh.** Rejected per grill Q7: blurs project-bootstrap with user-env setup; those concerns should stay separable.

## Open questions deferred

- Whether the captured tier needs a cull/stale-close mechanism (e.g., auto-close after N days). Defer until we have data on pile growth — if captured stays small organically, no mechanism needed.
- Whether the bootstrap.sh idempotency-check pattern should be exposed as a `--check` mode (dry-run / verify-current-state) for diagnostic use. YAGNI for slice 2; can be added later.
- Whether the `backlog-critic` should validate the promotion target's title against D5's "descriptive only" rule (i.e., reject promotions whose titles contain codenames or classifiers). Currently the rubric doesn't enforce title shape — only content. Defer until we see whether the issue is real in practice.

## Future direction

- **Session-start sweep skill (`/triage-captured`)** — fallback for the inline-firing gap (D3). Scans the captured tier for items lacking a critic-verdict comment, runs `backlog-critic` against each. Promote from future-work to implementation if we observe orphan captures in practice.
- **Cull/stale-close mechanism** — auto-close `captured`-labeled issues older than N days that haven't been rescued. Implement only if captured tier grows uncurated.
- **`bootstrap.sh` extensions** — once PRD-CI ships, extend bootstrap to create a CI bot identity, configure GitHub Actions secrets, and apply R3+R4 branch protection. This will be additive (new flags or always-on steps) and won't break existing bootstrap invocations.
- **`backlog-critic` rubric tuning** — D4 is the initial calibration; future data on autopilot false-positive and false-negative rates may justify rubric edits via a superseding ADR.

## References

- [ADR-0001](0001-foundational-design.md) D8 — orientation artifacts pattern (this ADR adds a new orientation artifact via the captured tier and bootstrap.sh)
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (critic per generation stage — D2 here extends to a consumption stage); D4 (no human gates between pipeline stages); D8 (ADR placement at grill→PRD boundary — why this ADR is drafted alongside PRD-workflow)
- [ADR-0004](0004-bypass-prevention.md) D1 (joint critic gate — pattern this D2 follows); D2 (bootstrap-mode policy — D8 mirrors this)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (canonical critic verdict template + CRITIC trailer — D4's critic conforms); D2 (canonical home of methodology depth); D3 (cascade-doc check — slicer-relevant)
- [ADR-0006](0006-backlog-and-session-continuity.md) D1 (backlog as GitHub Issues + label — reframed by D1 here); D2 (live-state reconstruction — augmented by the captured tier); D4 (write convention pattern — target shifts to captured tier)
- [ADR-0007](0007-vocabulary-glossary-and-grill-me-extension.md) — Negative Consequences pushback on 6th critic; D5 critic-rubric template followed here
- Grill session: PRD-workflow Q1–Q9 (2026-05-16)
- `decisions/README.md` — ADR conventions
