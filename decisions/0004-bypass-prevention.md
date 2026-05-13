# ADR-0004: Bypass prevention — workflow enforcement, adr-critic, and meta-output discipline

- **Status:** Accepted (drafted by `/to-prd` alongside PRD-B; reviewed by `prd-critic` in this bootstrap transition; `adr-critic` ships in PRD-B slice ≥2 and gates future ADRs)
- **Date:** 2026-05-13
- **Extends:** ADR-0003 (autonomous pipeline) — adds the bypass-prevention layer
- **Supersedes:** ADR-0003's supersession-header D-ID miscite (D5a); ADR-0003 D4/D6 contradiction on `to-prd` skill semantics (D5b); ADR-0003's missing bootstrap-mode policy (D5c); ADR-0003 D2's silent assumption of simultaneous 5-stage shipping (D5d). Does NOT supersede ADR-0001 or ADR-0002 (frozen)
- **Decided in:** Grill session "ADR-0004 backlog" (2026-05-13)

---

## Context

PRD #3 successfully shipped the autonomous pipeline (ADR-0003). Two failure modes surfaced during that PRD's own implementation, plus one observed retroactively against ADR-0003 itself:

1. **Main-agent hand-authored tracked files mid-conversation.** The main agent wrote `decisions/0003-autonomous-pipeline-with-critics.md` and `decisions/README.md` directly into the working tree before any GitHub issue existed and before the work was visible to the `reviewer` subagent. Only post-hoc human attention caught the gap. Nothing in the pipeline blocked it.

2. **No `adr-critic` exists.** ADR-0003 D2 mandated "critics at every generation stage" but ADR generation was implicitly delegated to `prd-critic`. An ad-hoc `adr-critic` run against ADR-0003 after PRD #3 shipped surfaced 4 real defects — validating that ADRs need their own dedicated critic.

3. **ADR-0003 has 4 retroactively-discovered defects** that this ADR corrects via D5 (per strict immutability convention in `decisions/README.md` — ADR-0003 file is never edited).

This ADR is the architectural response. It is intentionally narrow: bypass prevention only. PRD-A (subagent output-shape standardization, slicing methodology depth) is a separate PRD that ships after PRD-B.

---

## Decisions

### D1: `adr-critic` subagent exists

A new subagent `.claude/agents/adr-critic.md` mirrors `prd-critic`'s role for ADR files. Same 3-round APPROVE/BLOCK loop, same I5 escalation surface (`needs-human` label + parent-context comment on round-3 BLOCK), same output shape.

**Rubric (ADR-specific):**
- ADR convention compliance — Status / Date / Context / Decisions / Consequences / Alternatives sections present per `decisions/README.md`
- Cross-ADR consistency — no silent contradiction with accepted ADRs (D1, D2, ...); contradictions require an explicit `Supersedes:` header entry
- Supersession explicit and accurate by D-ID — the exact defect found in ADR-0003 ("Supersedes: ADR-0001 D3 (PRDs as repo files)" — D3 is about visibility, not PRDs)
- No scope creep beyond the ADR's stated theme
- Bootstrap-mode policy acknowledged when introducing new enforcement mechanisms (per D2 below)
- Immutability respected — never proposes edits to existing ADR files; only proposes new ADRs that supersede

**Wiring:** `/to-prd` skill invokes `adr-critic` on any macro-ADR drafted alongside the PRD, in parallel with its existing `prd-critic` invocation on the PRD body. Both critics must APPROVE before posting.

### D2: Bootstrap-mode policy explicit

When an ADR ships new enforcement mechanisms, the slices that *build* those mechanisms cannot themselves satisfy them — the mechanisms do not yet exist when those slices run. The bootstrap-mode policy resolves this:

> **Each enforcement mechanism in an ADR applies forward from the moment the slice that ships it merges. Earlier slices of the same PRD operate under whichever rules were in force at their branch-creation time. Once a mechanism is in force, bootstrap mode does not reopen for that mechanism — future PRDs satisfy it from slice 1.**

PRD #3 used an ad-hoc bootstrap (the main agent hand-authored ADR-0003 before adr-critic existed). That was a one-time transition acceptable because there was no prior state to enforce against. PRD-B's bootstrap is similar but smaller in scope — ADR-0004 itself is hand-drafted in this conversation because `adr-critic` does not yet exist; `prd-critic` reviews it in the bootstrap. From PRD-B slice ≥2 onward (whichever slice ships `adr-critic`), all subsequent ADRs go through `adr-critic`.

This is the policy lacuna that should have been in ADR-0003. D5c records it as a correction.

### D3: Workflow enforcement stack

Three layers protect against the "edit a tracked file outside the pipeline" failure mode:

1. **Pre-commit hook** in tracked `.githooks/pre-commit` (portable shell script). Checks: branch name matches the regex `^(feat|fix|chore|refactor|docs|test|perf|style|build|ci|hotfix)/[0-9]+-[a-z0-9-]+$` AND branch is not `main`. Nothing else. Per user's explicit "as simple as possible" instruction during the grill. Installation via `.githooks/install.sh` running `git config core.hooksPath .githooks` (idempotent).

2. **Branch protection R1 + R2** on `vojtech-stas/project-claude:main`. R1 = no direct push; R2 = require pull request. Configured via `gh api -X PUT repos/vojtech-stas/project-claude/branches/main/protection` with a tracked JSON payload. R3 (required approving reviews) and R4 (required status checks) are explicitly NOT enabled here — both require bot-identity or GitHub Actions setup that is deferred to a future PRD.

3. **Reviewer rule R-CLOSES** (already shipped in PRD #3 slice 4). BLOCKs PR if no `Closes #N` referencing a valid `slice`-labeled issue.

The three layers are independent failure-domain defenses: layer 1 catches local mistakes, layer 2 catches server-side bypass attempts, layer 3 catches malformed PRs even when layers 1 and 2 are bypassed (e.g., `--no-verify`).

### D4: Main-agent meta-output discipline

A new cross-cutting rule in `CLAUDE.md` (rule #10, after the existing 9):

> **Main agent never hand-authors tracked files. All edits to `decisions/`, `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, or `README.md` flow through the PRD/slice/PR pipeline — via `/to-prd`, `/to-issues`, `/ship`, or an implementer Agent invocation.**

Mechanical enforcement is heuristic: `reviewer` gets an additive rule R-META that BLOCKs if PR diff *adds* a file in `decisions/` and the PR body/commit chain lacks provenance evidence (the exact detection signal is an open question — see PRD-B §6). False positives are recoverable via an explicit `R-META-OVERRIDE: <rationale>` line in PR body, which the reviewer surfaces in its verdict comment for human visibility.

This rule is the policy companion of D3's mechanical enforcement: D3 stops bypass at git operations; D4 stops bypass at intent.

### D5: Errata corrections to ADR-0003

ADR-0003 has four retroactively-discovered defects. **ADR-0003 file is never edited.** The corrections live here, with the original ADR retained for audit-trail purposes per `decisions/README.md` immutability convention.

#### D5a — supersession header miscites ADR-0001 D-IDs

**ADR-0003 says:** "Supersedes: ADR-0001 D3 (PRDs as repo files) and parts of D6 (slicing convention)"

**Correction:** ADR-0001 D3 is "Visibility: public on GitHub" — not "PRDs as repo files". The correct claim is: ADR-0003 supersedes **ADR-0001 D5** (the 8-stage workflow pipeline, replaced by ADR-0003 D2's 5-stage pipeline) and **parts of D6** (the original agent topology, refined by ADR-0003 D6). ADR-0001 D3 is unchanged and still in force.

#### D5b — D4/D6 contradiction on `to-prd`'s skill semantics

**ADR-0003 says:** D4: "No human gates between pipeline stages." D6 (row 1 of the skill-vs-subagent table, rationale column): "Skills consume conversation context — conversation history, user interaction."

Reading them together suggests `to-prd` (classified as a skill in D6) needs user interaction *during* its run, contradicting D4's "no human gates after grill-me." The contradiction is real and was acknowledged in the grill but never fixed in ADR-0003.

**Correction:** Skills consume the *persisted* conversation context that exists after the human's `/grill-me` session ends. They run *without* the human actively present, against the conversation history. The "user interaction" wording in ADR-0003 D6 should be read as "consumes the user-produced context"  — not "requires live user input." `/to-prd` and `/ship` are non-interactive once invoked.

#### D5c — missing bootstrap-mode policy

**ADR-0003 silently failed to address** the recursive paradox: critics gate generation stages, but the critics themselves had to be generated by *something* — and at the moment of ADR-0003's drafting, none of the critics existed. PRD #3 navigated this with ad-hoc judgment ("we'll add critics as we build them"), which worked but left no policy for future PRDs introducing new enforcement.

**Correction:** Bootstrap-mode policy lives in D2 of this ADR. ADR-0003's PRD #3 implementation is grandfathered (the ad-hoc transition was acceptable). All future PRDs follow D2.

#### D5d — implementer-stage incremental rollout undocumented

**ADR-0003 D2 says:** "5-stage pipeline... 4. implementer + reviewer..."

But PRD #3 only shipped 4 of the 5 stages — `implementer` is deferred to a future PRD (after PRD-A). ADR-0003 does not acknowledge this incremental rollout, so a reader of ADR-0003 alone would expect a fully-shipped 5-stage pipeline.

**Correction:** ADR-0003's 5-stage pipeline is shipped incrementally. `reviewer` ships from ADR-0002. `prd-critic`, `slicer`, `slicer-critic`, and `/ship` ship in PRD #3. `implementer` is a separate future PRD after PRD-A. The ADR-0003 D2 5-stage list describes the *target* shape, not the snapshot of any given moment.

---

## Consequences

### Positive

- **Hard floor on workflow bypass.** Pre-commit (D3 layer 1) + branch protection (D3 layer 2) + reviewer R-CLOSES (D3 layer 3) + R-META heuristic (D4) collectively make it materially harder to land tracked-file changes outside the pipeline. Each layer has a different failure domain.
- **ADRs become first-class critic-gated artifacts.** D1's `adr-critic` catches the same class of bugs `prd-critic` catches for PRDs. ADR-0003's 4 defects would have been caught at draft time had `adr-critic` existed.
- **Bootstrap-mode policy is explicit.** D2 gives future PRDs introducing enforcement a clear policy to cite, rather than reinventing the explanation each time.
- **ADR-0003 audit trail preserved.** Errata via supersession (D5) maintains the historical "what we believed at the time" signal. Future readers see ADR-0003 as it was canonized and ADR-0004 as the correction.
- **Strict immutability convention validated.** `decisions/README.md`'s rule held up on its first real test (ADR-0003 fixes). Sets a strong precedent.

### Negative / accepted trade-offs

- **Pre-commit hook bypassable via `--no-verify`.** Layer 3 (reviewer R-CLOSES) catches PR-level bypass; nothing catches `--no-verify`-then-no-PR-then-no-push. Accepted: would require server-side enforcement (branch protection R3) which is deferred.
- **Branch protection R1+R2 do NOT block API-level push** with appropriate PAT scopes. Real protection requires R3 + bot identity. Documented limitation. Mitigation: human notices on next session; reviewer R-CLOSES catches at PR time.
- **R-META heuristic produces false positives.** When the detection signal isn't perfect, legitimate ADR additions may be BLOCKed. Mitigation: `R-META-OVERRIDE: <rationale>` line in PR body for explicit human-approved exceptions; reviewer surfaces in verdict comment.
- **One-time bootstrap accommodation.** ADR-0004 itself is hand-drafted by the main agent before `adr-critic` exists. `prd-critic` reviews it in this transition. The bootstrap exception is one-way and one-time: from PRD-B slice ≥2 onward, all ADRs go through `adr-critic`.
- **ADR-0003 read in isolation gives stale info.** A reader opening ADR-0003 alone (e.g., via `git show <past-sha>:decisions/0003-...md`) sees the defective content. Mitigation: `decisions/README.md` index row for ADR-0003 is updated by PRD-B to flag the corrections; modern readers see the index first.
- **`/ship` orchestrator chain diagram doesn't yet mention `adr-critic`.** Cosmetic; flagged as open question in PRD-B §6.

---

## Alternatives considered

### Alt-A: Edit `decisions/0003-...md` directly with errata
Rejected. Breaks the `decisions/README.md` immutability convention established in slice 5 of PRD #3. Sets the precedent "rules apply until inconvenient." Strict supersession via this ADR's D5 preserves the audit trail.

### Alt-B: Bundle PRD-A items (output-shape standardization, slicing methodology depth) into PRD-B
Rejected during the grill. Different theme (quality lever, not bypass prevention). Bundling would inflate the slice count past the 5-7 budget and mix concerns. Sequencing PRD-B before PRD-A means PRD-A operates under enforced workflow from slice 1.

### Alt-C: Run PRD-B and PRD-A in parallel
Rejected during the grill. PRD-A's meta-outputs (output-shape standardization touches subagent files, possibly drafts its own ADR) would themselves be vulnerable to the bypass that PRD-B is preventing. Sequencing avoids chicken-and-egg.

### Alt-D: Enable branch protection R3 + R4 in this PRD (full server-side protection)
Rejected. R3 requires bot identity to satisfy "can't approve own PR" failure mode. R4 requires GitHub Actions setup. Both significantly grow PRD-B scope. Deferred to a future PRD that bundles CI + bot identity. Documented in PRD-B §3 non-goals.

### Alt-E: Pre-commit hook also checks issue state (open/closed) and labels
Rejected per user's explicit "as simple as possible" instruction during the grill. Branch-name regex is the minimum useful local enforcement; richer checks belong to `reviewer` at PR time, where the issue/label data is already available.

### Alt-F: Skip D4 (meta-output discipline) and rely on D3 alone
Rejected. D3 catches the *git-operation* failure mode but not the *intent* failure mode (main agent intends to bypass and uses a properly-named branch). D4's CLAUDE.md rule + R-META heuristic is the only mechanism for that.

### Alt-G: Defer item 3 (N=3 vs single-slicer-with-critic empirical evaluation) into a follow-up issue, not a PRD
Accepted into PRD-B's non-goals list. Item 3 needs 3-5 real PRD runs of comparable data to answer empirically; running it as an experiment now would generate noise, not signal. Reopen after PRD-A ships.

---

## Open questions deferred

| Question | Deferred to |
|---|---|
| Exact mechanism for R-META heuristic provenance detection (PR body keyword vs commit trailer vs explicit `Generated-By:` line) | Slice implementation; document choice in `.claude/agents/reviewer.md` |
| Pre-commit hook behavior on detached HEAD, initial branch creation, rebase-merge in worktrees | Slice implementation; recommend fail-open with warning |
| Whether `/ship` orchestrator chain diagram needs cosmetic update to include `adr-critic` | CLAUDE.md rollup slice; treat as cosmetic |
| Whether bot-identity setup belongs in its own PRD or bundled with CI setup | Future PRD planning after PRD-A |
| Whether D5d's incremental-rollout note should retroactively appear in ADR-0003 as a Future direction (would require editing ADR-0003 — currently rejected by immutability rule) | No — leave as ADR-0004 D5d only |
| Whether ADR-0001/ADR-0002 should also get retrospective `adr-critic` passes once `adr-critic` ships | Probably yes, as a small follow-up issue; not in PRD-B |

---

## Future direction

- **Branch protection R3 + R4 with bot identity** — a future PRD adds a dedicated GitHub bot account, switches the reviewer subagent's `gh pr merge` to use that bot's PAT, enables R3 (required reviews from non-author identity) + R4 (required CI checks). This closes the API-level bypass gap acknowledged in Consequences.
- **`adr-critic` ensemble** — same future direction as `reviewer` ensemble (ADR-0002) and `prd-critic`/`slicer-critic` ensembles (ADR-0003). Multiple model-diverse critic runs for high-stakes ADRs (those touching foundational architecture), require unanimous APPROVE. Selective opt-in via a `requires-ensemble-adr` label.
- **Retroactive `adr-critic` pass on ADR-0001 and ADR-0002** — after `adr-critic` ships, run it against the two grandfathered ADRs. Any findings → write ADR-0005+ with corrections. Likely small or empty findings, but worth checking once.

---

## References

- [ADR-0001](0001-foundational-design.md) — foundational design; D5 is what ADR-0003 actually superseded (corrected by D5a here)
- [ADR-0002](0002-autonomous-merge-policy.md) — autonomous merge policy; the implementer-reviewer loop pattern this ADR generalizes further
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) — extended (D1) and partly corrected (D5) by this ADR
- [`decisions/README.md`](README.md) — ADR conventions (one-pattern-per-file, immutability, supersession-via-new-ADR)
- PRD-B issue (TBD — will be created by `/to-prd` after this ADR + the PRD-B body are both approved by `prd-critic`)
- Grill session "ADR-0004 backlog" — 2026-05-13 (this conversation)
