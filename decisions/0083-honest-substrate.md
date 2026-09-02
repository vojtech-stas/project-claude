---
id: "ADR-0083"
title: "Honest substrate: a signal may only assert what it can observe"
status: "accepted"
date: "2026-08-22"
scope: "verification"
rule_ids:
  - "VER-009"
  - "VER-010"
supersedes:
  - "ADR-0057 D2"
superseded_by: []
---

# 0083 — Honest substrate: a signal may only assert what it can observe

Status: Accepted
Date: 2026-08-22

> **Baseline.** Every line number, count and quoted output below was re-derived at
> **`origin/develop` = `c380bb3`** on 2026-08-22 (revision 3; the baseline sha is unchanged from
> revision 2, and revision 3's own additions — the resolved `beacon()` call graphs, the `error_count`
> verdict term, the `discovery.py:313` reader — were derived live at that same sha). `develop` is the
> correct baseline:
> slices branch from and merge to `develop` under ADR-0070's two-tier model, and `origin/main`
> (`f7378de`), against which revision 1 was derived, trails it. Four cites moved in the
> re-derivation and are corrected throughout: `.claude/skills/build/SKILL.md` is **DELETED** on
> develop (`0753aa7`, #1249, ADR-0081 D4), `ship/SKILL.md:235` is now `:264`,
> `tests/test_loc_cap_1162.py:180` is now `:174`, and `CLAUDE.md:133` is now `:132`.

> **Number is provisional.** `decisions/` tops out at 0081 at `origin/develop` c380bb3 — the next
> free number is 0082 — and a sibling draft (the standing-promotion-ack ADR) claims 0082 and lands
> first. If the landing order changes, the implementer re-derives this ADR's integer from
> `ls decisions/` at implementation time and updates the filename, the `id:` frontmatter key, the
> `# NNNN —` heading, and every `ADR-0083` self-reference below (including the `as amended by`
> pointers in `tools/gen_rules.py`). The companion PRD's §5 carries the identical escape for its own
> normative cite of D2. Nothing in this ADR depends on the specific integer 0083.

**Supersedes (per-decision):** **ADR-0057 D2** (PARTIAL — only its *three-outcome enumeration*
"ALLOW, DENY, ERROR". D1 below does **not** re-enumerate that list; it **relocates** it, because the
list conflates two orthogonal fields. ERROR is a *lifecycle* fact — the hook did not complete — and
belongs in `status`, which D2 closes. ALLOW and DENY are *gate decisions* and belong in the additive
`outcome` field, whose value set is per-gate and open. Central enumeration is what failed: the list
was already incomplete at authorship, since ADR-0023 D3 had specified `permissionDecision: "ask"`,
and it was overtaken again by **ADR-0079 D3**, which decided `outcome` = `deny`|`warn`|`allow` for
`pre-tool-bash` on 2026-08-20. Revision 1 of this ADR proposed widening the enumeration to four
(ALLOW/ASK/DENY/ERROR) and thereby minted a *third* vocabulary alongside the two already in the tree;
that proposal is withdrawn. D2's load-bearing claims **STAND UNTOUCHED**: on ERROR a gate fails open
for the user action and fails loud in telemetry; `stop-reviewer-gate.sh` reads stdin and honors
`stop_hook_active` before any other logic; fixture session ids are filtered at every reader and at
the gate hooks.) **ADR-0057 D1, D3, D4 and D5 STAND UNTOUCHED** — D1 in particular is *extended*,
not superseded: its four clauses (a) attempt-before-parse, (b) ERROR beacon on internal error,
(c) full-stdin python3 parse, (d) truncate-and-steer are byte-unchanged, and D1 gains a fifth
obligation (a terminal beacon at every terminal) rather than losing any.

**Extends:** ADR-0057 D1 (the fail-loud beacon contract — gains the terminal obligation, D1 below),
**ADR-0079 D3** (the `outcome`-carrying beacon — its `deny`|`warn`|`allow` vocabulary is adopted as
the one authority for gate-decision values rather than being replaced; D1 generalizes the field, D2
closes the neighbouring `status` field it sits beside), ADR-0023 D3 (the `ask` decision, the other
value already in the tree), ADR-0061 D1 (the route table and its verbatim union clause — D4 restores
code conformance to it and does **not** change it), ADR-0061 D2/D5 (the provenance and
artifact-existence controls, named as the forgery-resistance this ADR does *not* supply), ADR-0046
D3 / PIP-013 (the codebase-critic-before-reviewer ordering that D5's guard must stop contradicting),
ADR-0056 D1/D2 (rule #23 and the three-part mechanism-admission test — every decision below names its
mechanism, argues parsimony, and names its shadow; and every *general* obligation below either
carries a mechanism or is tagged `(advisory)` per D1's own escape), ADR-0056 D4 (a critic rubric is a
deterministic-enough mechanism — the authority D3's judgment half relies on, and its named weakness),
ADR-0067 D2/D3 (R-PROVE / the rule-#13 regression rider — every decision below fixes a code defect,
so every test commits before its fix), ADR-0004 D2 (bootstrap-mode), ADR-0073 D1/D3 (the generated
rule layer this ADR amends and extends).

**Bootstrap-mode (ADR-0004 D2):** every obligation binds forward from the merge of the slice that
ships it. The 59,838 beacon lines already in `.claude/logs/hook-fires.jsonl` are history, not
violations; no beacon is rewritten; the rolling 7-day window ages the non-conforming history out on
its own schedule. Merged PRs at or below the existing `_PROOF_PRESENCE_BOOTSTRAP_PR = 788` threshold
stay grandfathered, and PRs merged before this ADR's slices are judged by the tightened tokens only
because they fall inside a rolling window — that is a *reporting* change, not a retroactive verdict,
and D4's Consequences state the resulting number plainly.

> **Amendment mechanism — no implementer opens ADR-0057 (verified at c380bb3).** Rule *IDs* are
> declared in ADR frontmatter (`tools/gen_rules.py` parses `scope` at `:235` and `rule_ids` at
> `:236`, gating on both at `:240`) and are stable. Rule *statements* live in the `_RULE_STATEMENTS`
> dict inside `tools/gen_rules.py` (declared `:273`, consumed by `_get_rule_statement` at `:823`);
> HOK-008's statement is at `:523–527`. Amend-in-place has **six** precedents in that same file
> (`grep -c "as amended by" tools/gen_rules.py` = 6): three from ADR-0080 (`:380`, `:387`, `:438`)
> and three from ADR-0081 (`:600`, `:789`, `:817`). **None of them modified the amended ADR's file**,
> and `decisions/0057-hook-fail-loud-contract.md` has not been touched since `23479fb` (#896). D1 and
> D2 below are therefore applied by editing `_RULE_STATEMENTS["HOK-008"]` to carry the added
> obligations with an `(as amended by ADR-0083 D1/D2)` pointer, then running
> `python tools/gen_rules.py` to regenerate `.claude/rules/hooks.md`. **ADR-0057's own frontmatter is
> not modified either** — its `superseded_by` stays `[]`, exactly as ADR-0081 left
> ADR-0040/0038/0007/0012/0067/0034 (verified); setting it would drop HOK-008 and HOK-009 out of the
> active rule set entirely.

---

## Context

Six filed defects — #1246, #1237, #1233, #1234, #1028, #1250 — were captured independently over three
weeks and read as six unrelated repairs. They are one defect, stated six ways: **a signal in this
repo reports something it is not structurally capable of observing, and it does so in both
directions at once.** (Revision 1 listed five and omitted #1234, which is the "direction two" the
next section is entirely about and the defect D4 exists to settle. The omission is corrected here.)

**Direction one — false red.** `HOOK-INTEGRITY` has been un-PASS-able since `d9f6342` (#879,
2026-06-17), roughly two months. Re-derived live at c380bb3:

```
$ python dashboard/health.py --check HOOK-INTEGRITY
FAIL: HOOK-INTEGRITY - window=7d | ratios: auto:0/6304, pre-tool-edit:0/432,
session-start:36/48, session_start:30/30, session_stop:162/162, skill_invoke:5/1,
stop-reviewer-gate:118/162, user_prompt:123/123 | drift: auto(0/6304),
pre-tool-edit(0/432), session-start(36/48), stop-reviewer-gate(118/162)
```

Two of those four drift entries are artifacts of the check, not of the hook layer.

- **`auto(0/6304)` is a namespace collision.** `auto` is not a hook script. It is an argv sentinel:
  `.claude/settings.json` registers `log-tool-event.sh auto` on `PreToolUse(Agent|Skill)` and
  `PostToolUse(Agent|Bash|AskUserQuestion|Edit|MultiEdit|Write)`. The script writes its attempt
  beacon under that literal label *before* parsing (`log-tool-event.sh:71`; HOK-008(a), correctly),
  then reassigns `event_type` to a derived key, so the terminal lands under `bash_complete` /
  `post_tool` / `agent_start` / `agent_complete` / `skill_invoke` / `grill_qa` (`:91–100`).
  `check_hook_integrity` groups numerator and denominator on the same raw `obj["hook"]` string
  (`dashboard/health.py:2002`, counted at `:2015–2020`), so the pair can never meet. The fold
  reconciles over the live 7-day window: at the c380bb3 read, `auto` attempts **6,304** against
  derived terminals `agent_start 113 + agent_complete 113 + bash_complete 5,627 + grill_qa 2 +
  post_tool 430 + skill_invoke 5`. **The invariant is the claim, and it carries a stated tolerance:**
  because HOK-008(a) writes the attempt *before* the parse, a stream this size has a nonzero
  in-flight residue at essentially any read instant, so the invariant is *sum(derived terminals) ==
  auto attempts, modulo that residue* — never an exact equality asserted at an arbitrary moment.
  Revision 1's own ledger recorded the residue (5,878 vs 5,870, Δ=8, two reads seconds apart) and
  then reasoned as though the fold would produce an exact clear; it will not, and D3's Consequences
  now say so.
- **`pre-tool-edit(0/432)` is an invariant nobody owes.** `.claude/hooks/pre-tool-edit.sh` emits
  `attempt` (`:41`) and `ERROR` (`:105`) and nothing else (`grep -c '"status":"ok"'` = 0; 1,005
  attempt beacons all-time, zero terminals of any kind). It is not broken *against its contract*:
  HOK-008 and ADR-0057 D1 require an attempt beacon and an ERROR beacon on internal error.
  **Neither requires a terminal beacon on success.** The check has been enforcing an attempt↔ok
  pairing invariant the contract never stated, which is why the row scores 0/N forever no matter how
  healthy the hook is.

Two permanent false reds bury the genuine one — `session-start(36/48)` — and saturate the composite
they feed (`TELEMETRY-LIVE`, built by `_build_hook_trio_composite` at `dashboard/health.py:1705`,
returning its id at `:1751`), which is the only health surface left after ADR-0080 D1 reduced the
dashboard to the run-board plus a thin strip.

**Direction two — false green (#1234).** `PROOF-PRESENCE` credits a PR with hook evidence for
*naming the log file*. `_PROOF_TOKENS["hook-fire"] = [r'exit=', r'hook-fire', r'HOOK-FIRE']`
(`dashboard/health.py:2749`; the dict spans `:2747–2752`), searched case-insensitively at `:2780`.
The literal `hook-fire` is a substring of `hook-fires.jsonl` — the filename every hook PR mentions in
prose. Symmetrically, a pasted verbatim beacon line matches nothing: real beacon keys are
`{hook, ts, status, outcome, session_id, result, reason}` and
`grep -c "exit=" .claude/logs/hook-fires.jsonl` = **0** across 59,838 lines. The check therefore
*accepts prose about the evidence and rejects the evidence*. Adjacently, `_pr_has_proof_token`
(`:2774–2782`) returns `True` on **any** matching class — the loop at `:2777–2781` returns on first
hit at `:2781` — where ADR-0061 D1 states verbatim: *"A change matching multiple globs takes the
union of proof classes."* The code implements `any`; the contract says union. That is a defect, not a
decision.

**Two guards that do not guard.**

- **The cap guard under-counts.** `.claude/agents/reviewer.md:233` publishes the canonical R-LOC
  command as one `select(.path | …)` pipe, so every test inside receives the *string*, including
  `(.path == ".claude/settings.json")`, which asks for `.path` of a string. jq aborts that element
  and the stream truncates at the first non-runtime path. On PR #1245 it reported **165**; the true
  figure was **351**. The error is directionally unsafe — it under-counts, so an over-cap slice
  passes. #1237 records the same rule failing from the other side: orchestrator dispatch briefs
  paraphrase R-LOC as "additions only, deletions uncapped" while the canonical command sums
  `.additions + .deletions`.
- **The stop gate forges a crash and then misdiagnoses it.** `.claude/hooks/stop-reviewer-gate.sh`
  emits its attempt beacon at `:24` and reaches `exit 2` at `:107` with no terminal beacon, so
  every legitimate policy DENY produces exactly the attempt-without-`ok` signature ADR-0057 D1(a)
  reserves for *"a crash after the beacon"*. Live 7-day counts: 162 attempts, 118 `ok` — the 44-fire
  gap is deny traffic wearing a crash costume. Then, at `:105–106`, the same path asserts a cause it
  cannot see: it tells the orchestrator to dispatch a reviewer, when one of the two states consistent
  with its observation is a PR *correctly* waiting on its prerequisite `codebase-critic` pass
  (PIP-013 / ADR-0046 D3). It fired five times on PR #1249 in exactly that state on 2026-08-22.
  Following its advice would have reproduced the ordering miss recorded on #1205. And the datum that
  would distinguish the states is not visible from where the hook looks: `codebase-critic` posts on
  the **PRD issue**, not the PR (PR #1247 carries zero such comments).

**The beacon record has no schema, so every reader invented one.** This is the substrate under all
of the above. A live census of `hook-fires.jsonl` (59,838 lines) plus a static census of the 19
beacon-object emit sites across the 7 registered scripts **and the one `.py` helper they invoke** —
**each emit site resolved through its call graph, not stopped at the first runtime variable** —
shows eight mutually incompatible conventions in one file, one per row below:

| emitter | attempt record | terminal record | visible to `HOOK-INTEGRITY`? |
|---|---|---|---|
| `log-tool-event.sh auto` | `status:"attempt"`, label `auto` (`:71`) | `status:"ok"`, label = derived key (`:91–100`) | denominator only — never pairs |
| `log-tool-event.sh` (rotation) | — | `status:"rotation"` (`:303`) — a rotation record wearing a lifecycle field | no (0 live records; emitter exists) |
| `log-tool-event.sh` / `session-start.sh` (stdin-reject path) | — | `status:"error"` — **lowercase**, via `beacon("error", reason)` (`log-tool-event.sh:333`, `session-start.sh:308`) | counted by `health.py:2019` (`("ERROR","error")`), **not** by the closed set D2 publishes |
| `pre-tool-edit.sh` | `status:"attempt"` (`:41`) | none (ERROR only, `:105`) | denominator only — 0/N forever |
| `stop-reviewer-gate.sh` | `status:"attempt"` (`:24`) | `status:"ok"` (`:47`) — except the `exit 2` DENY (`:107`) | partly; DENY reads as crash |
| `pre-tool-bash.sh` / `-classify.py` | **no `status` field at all** (`:104`) | `status:"OK"` (uppercase) + `outcome` (`classify.py:166`) | **invisible** — 11,011 + 7,498 beacons in 7d, neither counted |
| `session-start.sh` | `status:"attempt"` (`:35`) | `status:"ok"` (`:323`), plus a third `status:"python3_selftest"` line (`:42`) | yes (the one genuine drift) |
| `dashboard-autostart.sh` (`:23`), `user-prompt-submit.sh` (`:24`) | **no `status` field** | none | **invisible** |

The `outcome` field in row six (`pre-tool-bash.sh` / `-classify.py`) is not an accident of
implementation — it is **ADR-0079 D3**
(accepted 2026-08-20), which decided that `pre-tool-bash`'s beacon "gains an `outcome` field
(`deny`|`warn`|`allow`), making real deny history measurable for the first time." That decision is
the existing authority for gate-decision values, and D1 below adopts it rather than competing with
it. Revision 1 of this ADR never cited ADR-0079 anywhere (`grep -c "ADR-0079"` on the draft = 0) and
proposed a conflicting enumeration as a result.

And two readers of the same field disagree: `dashboard/discovery.py:311` counts a status-less line as
an attempt (`if status in ("attempt", "")`, documented at `:277`), `dashboard/health.py:2015` does
not. `pre-tool-bash` is the largest single beacon stream in the log and is entirely dark to the check
that claims to report whether hooks are healthy.

**What actually needs deciding.** The PRD that carries this work makes code fixes; those need no
ADR. One thing here is a genuine contract change and three are general principles that will govern
every future check, guard and proof route:

1. HOK-008 does not require what `check_hook_integrity` enforces. Either the check stops, or the
   contract states it. (D1, D2.)
2. What a check may assert at all. (D3.)
3. What counts as evidence, as opposed to prose about evidence. (D4.)
4. Whether a signal may name a cause it cannot observe. (D5.)

---

## Decisions

### D1 — Every hook terminal owes a terminal beacon; DENY is a beaconed terminal; and the lifecycle fact and the gate decision live in separate fields

ADR-0057 D1 gains a fifth clause, applied to every hook script registered in `.claude/settings.json`:

> **(e)** Every terminal path MUST append exactly one terminal beacon before exiting. A terminal is
> `status:"ok"` when the hook ran to completion, or `status:"ERROR"` when it did not (D1(b),
> unchanged). A **deliberate policy decision is a completion, not a failure**: a DENY, an ASK, a WARN
> or a block exits with `status:"ok"` and records the decision in the additive `outcome` field.

`status` answers *did the hook execute to completion*. `outcome` answers *what did the gate decide*.
Collapsing the two is precisely the defect: today a policy DENY is indistinguishable in telemetry
from a hook that died mid-run, so the single signal ADR-0057 D1(a) built to reveal silent hook death
is saturated by ordinary correct traffic.

**The vocabulary question, settled once.** Three spellings for one concept were live in the tree and
the drafts before revision 2: ADR-0057 D2's `ALLOW/DENY/ERROR`, ADR-0079 D3's `deny|warn|allow`
(implemented at `pre-tool-bash-classify.py:158–166`), and revision 1's own `ALLOW/ASK/DENY/ERROR`
plus a companion-PRD `"outcome":"blocked"`. The settlement is:

- **`status` is closed and D2 owns it** — `{attempt, ok, ERROR}`, nothing else, ever. `ERROR` moves
  here permanently: an infrastructure failure is a lifecycle fact, not a gate decision, and ADR-0057
  D2 listing it alongside ALLOW and DENY is the category error this decision fixes.
- **`outcome` is additive, lowercase, and its value set is per-gate and OPEN.** D1 does **not**
  publish a central enumeration, because every central enumeration attempted so far has been
  overtaken within months: ADR-0057 D2's three were already incomplete at authorship (ADR-0023 D3's
  `ask`, `pre-tool-edit.sh:47–55`), and ADR-0079 D3 added `warn` afterwards. Each gate declares its
  own value set at its emission site; the four already decided — `allow`, `warn` (ADR-0079 D3),
  `ask` (ADR-0023 D3), `deny` (both) — are the starting vocabulary, and a new gate reuses them
  rather than minting synonyms. **That reuse obligation is `(advisory)`.**
  `stop-reviewer-gate`'s `exit 2` is therefore `outcome:"deny"`, **not** `"blocked"`.
  *Why that clause is tagged, per ADR-0056 D1's escape:* it is a recurring obligation on every
  future gate, and deciding whether a proposed new value is a *synonym* of an existing one is a
  semantic judgment no deterministic mechanism here can make — a membership check cannot be written
  against a set this decision deliberately leaves open. D1's Enforcement below asserts an `outcome`
  value is **present** and not duplicated into `status`; it does not and cannot assert membership.
  This is the third instance of one class: revision 2 gave D4(c) a mechanism and tagged D5's general
  clause, and missed this one; tagging is the honest disposition rather than shipping an
  unenforceable obligation. The
  clause is **not** carried into the HOK-008 amendment — only the terminal-beacon obligation and the
  closed `status` vocabulary are (see Propagation) — so no always-loaded rule text inherits an
  untagged version of it.
- **`pre-tool-bash`'s existing record is the reference pattern**, and this ADR's only change to it is
  the one-token `status` repair D2 mandates (`"OK"` → `"ok"`). Its `outcome` field is left exactly as
  ADR-0079 D3 decided it.

Revision 1 asserted that "D2 closes its vocabulary". That was wrong in a way worth naming, because it
is the same disease this ADR is about: **D2 closes `status` only, and explicitly leaves additive keys
open.** Reading D2 as closing `outcome` would have made D1 and D2 contradict each other inside one
document.

**Implementation shape (constraining, because the alternative regressed once already):** a single
`trap … EXIT` per hook that emits a terminal iff none was emitted, not a hand-edit at each exit site.
`pre-tool-edit.sh` has seven executable terminals (`:54`, `:66`, `:72`, `:108`, `:115`, `:124`,
`:129`) and `stop-reviewer-gate.sh` nine; #846 added `emit_ok_beacon` to the latter and the `exit 2`
path still slipped through. A trap cannot be regressed by a future terminal that forgets.

**Enforcement (rule #23).** A live-fire regression test in `tests/`: for each hook registered in
`.claude/settings.json`, drive the script with a synthetic payload and `WORKFLOW_LOG_DIR` pointed at
a scratch dir (rule #21 — nothing synthetic reaches `.claude/logs/`), and assert **exactly one**
terminal beacon per fire, with `status` inside `{ok, ERROR}` and, on gate terminals, an `outcome`
value present and *not* duplicated into `status`. Per REG-002 the test commits before the fix and
fails against c380bb3 on `pre-tool-edit` (0 terminals) and on `stop-reviewer-gate`'s `exit 2` path
(verified live: attempt written, terminal count 0; `grep -c '"outcome"'` = 0 in both scripts).
Companion-PRD criteria 6, 7 and 8 are the QA-side counterparts, criterion 8 being specifically the
verification of the field split this decision supersedes ADR-0057 D2's enumeration with.
**How this check can fail:** delete a trap, add a hook without one, emit two terminals on one path,
or encode a gate decision in `status`, and it goes red. It is not a static grep for `trap`, because a
trap can be present and wrong.
**Named weakness:** driving `stop-reviewer-gate` to its DENY path needs `gh`; the test must skip
**loudly** (an explicit skip that CI surfaces) rather than pass silently when `gh` is unavailable —
a silently-skipping test is the same disease as a vacuous check.
**Parsimony (ADR-0056 D2b).** No existing mechanism covers this. `HOOK-INTEGRITY` was *already*
enforcing the invariant, which is the whole problem — it enforced it without a contract. HOOK-LIVENESS
detects darkness, not terminal discipline. The fix is to give the existing check an authority, not to
add a second check.
**Shadow (ADR-0056 D2c).** *The crash signature forged by normal operation* — a policy denial
indistinguishable in telemetry from a hook that died, so the one instrument built to reveal silent
hook death is drowned by correct behaviour and becomes unreadable. A future audit tests this by
firing each gate's deny path and confirming the beacon carries a terminal `status` **and** an
`outcome` naming the decision; a deny that produces no terminal, or a terminal with no outcome, is
the shadow returned.

### D2 — The beacon record has a closed `status` schema, and one reader semantics

Every line appended to `hook-fires.jsonl` by a registered hook carries, at minimum, `hook`, `ts`,
and `status`. `status` is drawn from the closed set **`{attempt, ok, ERROR}`** — lowercase `attempt`
and `ok`, uppercase `ERROR` (the existing convention is preserved rather than churned; `ERROR` is
already load-bearing in `check_hook_integrity`'s `status in ("ERROR","error")` branch at `:2019`).
Any other decision, diagnostic or classification the hook wishes to record goes in an **additive**
field — `outcome` for a gate decision (per ADR-0079 D3 and D1 above), and any other named key for a
probe or maintenance record — never in `status`. **This decision closes `status` and nothing else:**
additive keys, including `outcome`, stay open by design, and readers treat unknown additive keys as
ignorable. No existing field changes meaning.

This is not cosmetic. `status` is the field two health readers already disagree about
(`dashboard/discovery.py:311` counts a status-less line as an attempt; `dashboard/health.py:2015`
ignores it), and it is the field three registered hooks do not emit at all, which is why
`pre-tool-bash` — the single largest beacon stream in the log, 11,011 status-less fire records and
7,498 terminals in the live 7-day window — is completely invisible to the check that claims to report
whether hooks are healthy. A contract whose subjects cannot be seen by its own instrument is not
being enforced.

**Scope, stated exactly, because "conform everything" is how this decision would become scope
creep.** Bringing the fleet to the schema is seven mechanical repairs and one named exception:

| emitter | repair | size |
|---|---|---|
| `pre-tool-bash.sh:104` | attempt printf gains `"status":"attempt"` | 1 line |
| `pre-tool-bash-classify.py:166` | `"status": "OK"` → `"ok"` (its `outcome` field is untouched) | 1 token |
| `dashboard-autostart.sh:23` | gains `"status":"attempt"` + an EXIT-trap terminal | ~4 lines |
| `user-prompt-submit.sh:24` | gains `"status":"attempt"` + an EXIT-trap terminal | ~4 lines |
| `log-tool-event.sh:303` | `"status": "rotation"` → `"status":"ok"` + additive `"event":"rotation"` | 1 line |
| `log-tool-event.sh:333` | `beacon("error", reason)` → `beacon("ERROR", reason)` | 1 token |
| `session-start.sh:308` | `beacon("error", reason)` → `beacon("ERROR", reason)` | 1 token |
| `session-start.sh:42` | **named exception, deferred** — see below | 0 lines |

`log-tool-event.sh:303` was **found during revision 2 and is absent from revision 1's table**, which
claimed four repairs and one exception and would therefore have shipped a CI check that reddened on
merge day against an emitter nobody had budgeted. It is the same shape as the `session-start`
exception — a maintenance record wearing a lifecycle field — but it is **repaired rather than
grandfathered**, because zero live records carry it
(`grep -c '"status": *"rotation"' .claude/logs/hook-fires.jsonl` = 0), the repair is one line in a
cold path, and adding a second exception literal would start the category the next paragraph rejects.

**The last two rows are revision 3's finding, and the *method* that missed them is the actual
defect.** Revision 1's census enumerated static `"status"` literals at each emit site, marked the two
sites that emit a runtime variable — `log-tool-event.sh:92` and `session-start.sh:235`, both the
`obj = {"hook": event_type, "status": status, …}` line inside a `beacon()` helper — as
undecidable, and stopped. That method let `"rotation"` through in revision 1 and lets a live
lowercase `"error"` through in revision 2. Both `beacon()` call graphs are small and closed, and are
now **resolved** rather than deferred:

- `log-tool-event.sh` — `beacon()` defined `:91`, called at `:166` `"ok"`, `:315` `"ok"`, `:333`
  `"error"`.
- `session-start.sh` — `beacon()` defined `:234`, called at `:290` `"ok"`, `:308` `"error"`.

Two of those five literals are `"error"` — lowercase, outside `{attempt, ok, ERROR}`. The emitter is
live code, and the log holds **12** such records
(`grep -oE '"status":"[^"]*"' .claude/logs/hook-fires.jsonl | sort | uniq -c` → `12 "status":"error"`),
all under the `agent_start` derived label and all timestamped 2026-08-01/02, hence outside the
current rolling window (in-window `error_count` = 0 at c380bb3, which is why the live
`HOOK-INTEGRITY` detail quoted in Context carries no `ERROR beacons:` part). They are repaired for
the same reason `rotation` is: `check_hook_integrity` already accepts both spellings at `:2019`
(`status in ("ERROR","error")`), so the repair is **counting-neutral** for that reader, and admitting
a second spelling of one concept into a closed set is the dialect problem this ADR exists to end.
**Known reader consequence, stated rather than discovered later:** `dashboard/discovery.py:313`
counts `status == "error"` only and has never counted the three uppercase-`ERROR` emitters
(`pre-tool-bash.sh:108`, `pre-tool-edit.sh:105`, `stop-reviewer-gate.sh:56`), so its `error_count`
goes from 2-of-5 emitters to 0-of-5. That is an already-partial count becoming a consistently-empty
one, not the loss of a working signal — and the signal it empties **reaches no rendered surface and
no verdict**: `dashboard/server.py` carries zero `discover_*` references (ADR-0080 D1 reduced the UI),
and `dashboard/readme_gen.py`, the only remaining production consumer of `discover_hooks()`, never renders the
field (`grep -c 'error_count'` = 0 in both). `health.py`'s same-named `error_count` (`:1992–2054`) is
a separate local counted straight off the log, not this one. Aligning `:313` with `health.py:2019` is
one line and is the obvious repair, but it would newly score the three grandfathered
uppercase-`ERROR` **emitters** — the identical rescoring hazard that keeps the neighbouring `""`
branch frozen — so it rides the same removal trigger the Propagation entry already carries, and
**#1264** is the filed tracker (triaged trivial-lane; a hotfix after the companion PRD lands). *The
count above is over emit sites, which are static and countable; do not restate it as a record count.
A grep census of the log reports `"status":"ERROR"` ×3 where every parser sees ×1, because five lines
are torn concurrent appends — **#1265**. Grep censuses of this log are approximations.*

`session-start.sh:42` emits a third line with `status:"python3_selftest"`, which is a probe record
wearing a lifecycle field. The correct repair is to move the probe out of `status`. It is
**deliberately deferred**, with a `captured` issue filed naming this ADR, because `session-start` is
the host of the `session-start(36/48)` drift that the PRD explicitly excludes as real and
undiagnosed (#1118 blocks its diagnosis): `:42` fires on **every** session-start — 102 records
all-time, 48 in the live window — in the same run as the `attempt`/`ok` pair the `36/48` ratio is
computed from, so re-labelling it changes what the check counts for that hook. **The deferral is
line-scoped, not file-scoped**, which is why the same file's `:308` is repaired two rows above — and
the reason is structural, not probabilistic. `:308` writes through the file's embedded-python
`beacon()` helper (`:234`), whose records carry `"hook": event_type`, and `event_type` is set to
`session_context_injected` at `:227`; the line therefore lands under a **different `hook` label
entirely** and cannot touch either counter the `session-start` ratio reads, however often it fires.
The `36/48` belongs to the `session-start` label, which is produced by the two shell printfs at `:35`
and `:323` that this repair leaves alone. That `:308` has also produced zero records in the log's
entire history is corroboration, not the argument. An implementer must not read this exception as
covering `session-start.sh`. The exception is **one grandfathered string
literal in the checker, carrying its issue number** — not an exemption *mechanism*. The distinction
matters and is the same one the PRD drew when it rejected "stop scoring hooks that declare no terminal
beacon": a category-shaped exemption lets a genuinely dead hook hide inside it; a single enumerated
literal cannot hide anything, and its removal is the deletion of one line.

**Falsifiable prediction, stated so it can be wrong — and with its known tolerance stated too.**
After D1 + D2, `pre-tool-bash`, `user-prompt-submit` and `dashboard-autostart` become visible to
`HOOK-INTEGRITY` for the first time and are predicted to pair 1:1 on **post-merge fires**, since each
has exactly one terminal path per fire once the trap is in place and historical status-less lines
stay uncounted. The prediction is *not* that their ratios read exactly `N/N` at an arbitrary read:
HOK-008(a) mandates the attempt beacon before any parsing, so a nonzero in-flight residue exists at
essentially any instant on a stream of `pre-tool-bash`'s size, and `check_hook_integrity` flags on
`ok < att` (`:2042`) with no tolerance. Expect these hooks to appear in `drift:` transiently. **If the
gap is persistent or large rather than a few records, a previously-invisible defect has surfaced —
that is the mechanism working, and it must be captured and diagnosed, not suppressed by narrowing the
check or widening the window.**

**Enforcement (rule #23).** A new `tools/ci-checks.sh` check (integer re-derived at implementation —
the last is CHECK 23 at `:1070` at c380bb3, and the sibling promotion-ack ADR claims 24) over every
beacon-object emit site in `.claude/hooks/*.sh` and `.claude/hooks/*.py`. It is **presence-side and
value-side**, and the presence leg is the load-bearing half:

1. **Presence:** every emit site that writes a JSON object to `hook-fires.jsonl` must carry a
   `"status"` key. A site that omits it FAILs, naming file and line.
2. **Value:** every literal `"status"` value must fall inside `{attempt, ok, ERROR}`, plus the single
   named `session-start.sh:42` grandfather. **A site that emits `status` from a runtime variable is
   resolved through its call graph, not exempted:** the two such sites (`log-tool-event.sh:92`,
   `session-start.sh:235`) are `beacon()` helper bodies, and a `beacon("<literal>", …)` call **is** a
   status literal for this leg. The check therefore extracts literals from emit sites *and* from
   helper call sites, which is one additional grep per helper. After the seven repairs above there is
   **no residual exempt site at c380bb3** — every `status` value in the fleet is statically
   resolvable. Revision 2 wrote this leg as an exemption and asserted that D1's live-fire test covered
   those values; it did not, because that test drives a synthetic payload down the success path to
   `beacon("ok")` and never reaches the stdin-rejection path where `"error"` is written. A value
   invisible to both named mechanisms is precisely the shape this ADR condemns, so the static leg is
   widened rather than the claim repeated. If a genuinely computed (non-literal) `status` is ever
   introduced, the check FAILs on it and the author must either make it literal or bring an explicit
   named exception — silent undecidability is not an outcome this leg has.

**Revision 1 specified the value leg alone, and that check could not redden on its own primary defect
class.** A status-less emitter contributes zero `"status"` literals, so a value-only extractor passes
it silently — and status-less emission is the dominant non-conformance by volume (11,011 + 132 + 13 =
11,156 in-window records at c380bb3, against 7,498 uppercase-`OK`). Revision 1 then claimed as its
falsifiability property that "add a hook that emits no `status` at all, and CI reddens", which was
false about its own mechanism. An ADR whose subject is checks that cannot fail must not ship one.
**How this check can fail:** add `"status":"OK"` or `"status":"skipped"` to any hook (value leg), add
a `beacon("<new-word>", …)` call to either helper (the same value leg, reached through the call
graph), or add a hook that writes a beacon with no `status` key at all (presence leg), and CI
reddens. Both legs
are demonstrated reddening at verification time — see the companion PRD's Production check (d), which
requires the presence leg to be shown failing against a deliberately-broken emitter, not merely
passing on the repaired tree.
It is static and on the *emitters*, deliberately not a scan of the live log — a log scan would
immediately red on the 59,838 grandfathered lines and force exactly the out-of-scope edits this
decision is scoping away.
**Parsimony (ADR-0056 D2b).** HOOK-INTEGRITY reads values; it cannot see an emitter that never writes
one, so it structurally cannot host this. CHECK 8 asserts hook-entry counts and payload paths in
`settings.json`, not record shape. Nothing else reasons about the beacon record.
**Shadow (ADR-0056 D2c).** *The unseen stream* — a hook that beacons diligently into a field shape no
reader understands, so its health is unknown while the dashboard reports on the hooks it happens to
be able to parse and calls that "hooks live". A future audit tests this by comparing the set of hooks
registered in `settings.json` against the set appearing in `HOOK-INTEGRITY`'s ratio list; a
registered hook missing from the ratios is the shadow.

### D3 — A check may only assert an invariant its subjects are contractually obliged to satisfy

A deterministic check — health row, CI check, pre-commit gate, guard — may FAIL a subject only on an
invariant that subject **owes**, where owing means: an accepted ADR decision, a generated rule id, or
a documented interface contract states it. If a check's invariant is not owed, **the check is wrong,
not the subject**. There are exactly two legitimate resolutions: amend the contract to state the
invariant and retrofit the subjects (what D1 does for HOK-008), or stop scoring that subject (what
D3's corollary does for the derived-key labels). Silently continuing to score is not a third option.

**Corollary — a check's subject set is defined, not assumed, and every registered subject is scored
under exactly one named label.** A check that scores "hooks" scores exactly the hook scripts
registered in `.claude/settings.json` (seven at c380bb3: `dashboard-autostart`, `log-tool-event`,
`pre-tool-bash`, `pre-tool-edit`, `session-start`, `stop-reviewer-gate`, `user-prompt-submit`).
`bash_complete`, `post_tool`, `agent_start`, `agent_complete`, `skill_invoke`, `grill_qa`,
`session_start`, `session_stop`, `user_prompt` and `session_context_injected` are event-type keys
`log-tool-event.sh` derives at runtime; **none of them is a subject of the hook contract and none is
scored as one.** `auto` is neither a hook script nor a derived key — it is the argv label under which
the registered script `log-tool-event.sh` writes every attempt beacon in auto mode, and it is
therefore that script's **stream identity**. `check_hook_integrity` folds the derived terminals back
onto it using the existing `dashboard/discovery.py:353 _auto_mode_derived_keys(event, matcher)` —
which `STREAM-LIVENESS` already imports (`dashboard/health.py:6265`, used at `:6291`), so
HOOK-INTEGRITY's raw `obj["hook"]` grouping at `:2002` is the outlier, not the norm.

**Stated flatly so the implementer does not guess, because revision 1 left it ambiguous and the
companion PRD read it the other way:** the folded stream is scored **under the `auto` label**.
`log-tool-event` does not appear in `ratios:` under its own script name. The
registered-hooks-minus-ratio-labels set difference therefore ends at exactly **1** — `log-tool-event`,
whose stream is present under `auto` — which is what the companion PRD's criterion 14 asserts. The
corollary's earlier phrasing ("`auto` … cannot be scored") described the *raw-grouping* status quo,
not the post-fix state, and is corrected here.

**The subject set governs `check_hook_integrity`'s *other* FAIL trigger too, which revision 2 left
ungoverned.** The row's verdict is `result = "FAIL" if (drift_hooks or error_count > 0)`
(`dashboard/health.py:2054`), and `error_count` accumulates at `:2019–2020` over **every** record
whose `status` is `ERROR`/`error`, with **no hook-label filter at all**. So a derived key this
corollary explicitly removes from scoring — `agent_start`, `bash_complete`, … — can still FAIL the
whole row through the second term, and the detail says only `ERROR beacons: N` (`:2049`), naming no
subject. The docstring states the trigger (`:1974`, *"ERROR beacons in any window → FAIL"*) but not
whose; that is the same defect in the same function: a verdict driven by a label that is not a
subject, with no `ratios:` entry a reader can trace it to. Every one of the 12 live `error` records
sits under exactly such a label (`agent_start`), so this is not hypothetical. The disposition is the
one this decision already mandates for the drift list: **`error_count` is attributed through the same
registered-subject fold**, an ERROR under a derived key counting against its registrar's stream
identity, and the detail names the label it was attributed to. A record whose label is neither a
registered hook nor a registered hook's declared stream identity is **not scored**, exactly as the
corollary says of the ratio list — it does not silently redden the row from outside the subject set.

The same principle read backwards names the class the PRD did not repair and this ADR does not either:
a check whose satisfaction condition is written by the act it gates cannot fail, and is a violation of
this decision in the opposite direction. #1251 is exactly that (`check_meta_tripwire` PASSes on a
marker `tools/promote.sh` writes on every promotion), and its repair is owned by the sibling
promotion-ack ADR's D4, not by this one. If that ADR is re-scoped or dropped, #1251 is still open and
still an instance of D3.

**Enforcement (rule #23) — deterministic half.** A regression test asserting that
`check_hook_integrity`'s drift list is a subset of the hooks registered in `.claude/settings.json`
(with `auto` admitted as `log-tool-event`'s stream identity per the corollary), and that a synthetic
log containing one `auto` attempt plus one matching derived terminal produces **no** `auto` drift.
Per REG-002 it commits before the fix and fails against c380bb3 (verified: with `_HEALTH_REPO_ROOT`
patched to a temp tree holding exactly `{"hook":"auto","status":"attempt"}` +
`{"hook":"bash_complete","status":"ok"}`, the function returns
`{'result': 'FAIL', 'detail': 'window=7d | ratios: auto:0/1 | drift: auto(0/1)'}`).
**Plus one assertion for the `error_count` term** (`:2054`), which the drift-list assertion above does
not reach: a synthetic log holding one in-window `{"hook":"agent_start","status":"error"}` alongside a
conforming registered pair must produce a detail that **attributes** that record to
`log-tool-event`'s `auto` stream identity, and a synthetic log holding one out-of-subject label must
**not** FAIL the row through `error_count` with no `ratios:` entry accounting for it. Against
c380bb3 the first assertion fails (the detail reads a bare `ERROR beacons: 1`) and the second fails
(`result` is `FAIL`), so this leg satisfies REG-002 on the same commit ordering as the rest.
**How this check can fail:** reintroduce raw `obj["hook"]` grouping, score any label that is
neither a registered hook nor a registered hook's declared stream identity, or let an unattributed
ERROR record drive the verdict, and it reddens.
**Enforcement — general half, and its honest weakness.** `.claude/agents/reviewer.md` gains a rubric
rule: a PR that adds or tightens a deterministic check must name, in the PR body, the contract clause
(ADR `D<n>` or rule id) the check enforces; a check with no citable authority is a BLOCK. Per
ADR-0056 D4 a critic rubric is a deterministic-enough mechanism. **This is the softest mechanism
ADR-0056 admits, and for an ADR about checks that assert unstated things, relying on judgment here is
uncomfortable. It is stated rather than dressed up:** the general half fails silently whenever a
reviewer does not notice, and its only backstop is D3's own deterministic instance plus the coverage
question a future audit can ask. The alternative — a registry-wide `authority` field with a CI
resolver over all 50 checks — is rejected below as disproportionate for this PRD, and is the
escalation if the rubric proves ignored.
**Parsimony (ADR-0056 D2b).** `adr-critic`'s AC-ENFORCEMENT already requires a *new ADR* to name its
mechanism; nothing requires a *new check* to name its authority, and checks are added by ordinary PRs
that never touch an ADR. That is the uncovered cell.
**Shadow (ADR-0056 D2c).** *The permanently-red row* — a check reporting a violation nobody can fix
because nothing was ever required, whose steady red trains every reader to stop reading the surface,
so the one genuine failure underneath is invisible. Its mirror is *the permanently-green row* (#1251).
A future audit tests both by asking, for each row: what input makes this FAIL, is that input reachable
in production, and which clause does the failing subject violate? A row with no citable clause, or no
reachable red, is the shadow.

### D4 — A proof token must match what the evidence produces, never what prose about the evidence says; and the route union is conjunctive

Three parts, one principle.

**(a) Admissibility.** A token in `_PROOF_TOKENS` must match a shape produced **by the artifact
itself, or by the mandated `PROOF:` trailer field of a real verification run**, and must **not** match
the ordinary prose used to *refer* to that evidence — a filename, a log path, a route name, a check
id. `hook-fire` fails on both counts simultaneously: it matches `hook-fires.jsonl` (the most common
way to describe hook evidence) and it matches nothing a hook actually writes. The replacement tokens
are shapes a beacon line or a verification transcript produces: a beacon's own key/value structure
(`"status"\s*:\s*"(ok|ERROR)"`, `"hook"\s*:\s*"`) and an exit code with a digit (`exit=\d`).

**Scope limit, stated because revision 1 mandated more than it budgeted.** This decision retokenizes
the **`hook-fire` class only**. Revision 1's Propagation additionally required that the `static`
class's `grep -c` and the `browser` class's `screenshot` token "must be justified or tightened" in
the same PR — an obligation with no acceptance criterion, no measured baseline and no slice budget,
and one that would move the 9/10 → 1/10 figure this ADR publishes as its measured consequence. It is
**descoped to an explicit follow-up**, recorded in the companion PRD's §3 non-goals. The evidence to
settle it is what D4(c)'s per-class detail is built to produce; deciding it now would be the guess
this ADR exists to forbid.

**(b) The union is conjunctive.** `_pr_has_proof_token` returns `True` only when **every** class in
the route union has a matching token. **This is conformance to ADR-0061 D1, not a change to it.** D1
reads verbatim: *"A change matching multiple globs takes the union of proof classes."* The `any`-over-
classes loop at `dashboard/health.py:2777–2781` is a defect. Recording this as a supersession would
falsely imply the contract moved; it did not, and the qa-tester prompt has stated the union rule
correctly all along (`.claude/agents/qa-tester.md:278`).

**(c) A signal that reports a miss must say what it missed.** `check_proof_presence`'s `detail` names,
per missing PR, which route class lacked a token. A bare PR number tells the reader a rule was broken
without telling them which — the reporting form of the same disease. **This clause is scoped to
`check_proof_presence` and carries its own mechanism** (the third corpus leg below); it is not a
general obligation on every check's detail string, because ADR-0056 D1 forbids shipping one of those
without a mechanism, and no mechanism over all 50 rows is proposed here.

**What this decision does not claim, stated because omitting it would make this ADR self-refuting.**
No token is forgery-proof. A token asserts only *"this text has the shape of evidence"*, never *"the
evidence exists"*. `exit=` is producible by a genuine transcript **and** by an author typing a
plausible number — it is weak-but-not-worthless because `.claude/skills/ship/SKILL.md:264` mandates
it in the `PROOF:` field, so its presence at least indicates the trailer contract was followed. The
real forgery-resistance already exists on paper and is **not applied by this check**: ADR-0061 D2's
`PROOF_SOURCE` validation against `workflow-events.jsonl` and D5's artifact-existence `stat`.
`check_proof_presence` performs neither. This ADR does not close that gap; it names it, and the
honest description of D4 is *"the check stops accepting descriptions"*, not *"the check now verifies
proofs"*.

**Enforcement (rule #23).** A **three-legged** fixture corpus in `tests/`, asserted in every
direction the decision has:
1. a reference-prose corpus (`"written to .claude/logs/hook-fires.jsonl"`, `"the hook-fire route"`,
   `"see the beacon log"`) must return `False` — D4(a)'s tightening leg;
2. a pasted-artifact corpus (a verbatim beacon line, a real `exit=0` transcript excerpt) must return
   `True` — D4(a)'s counterweight leg;
3. a partial-union corpus (`_pr_has_proof_token('ran it, exit=0', [], {'browser','command-run'})`)
   must return `False`, **and** the resulting `check_proof_presence` detail must name `browser` as
   the unsatisfied class for that PR — D4(b) and **D4(c)** together. The class-naming assertion is
   what gives D4(c) a mechanism instead of leaving it an untagged general obligation, and it is the
   same assertion the companion PRD's criterion 13 makes at QA time.

**How this check can fail — in both directions, which is the property that keeps it honest:**
over-tightening reddens the pasted-artifact corpus, over-loosening reddens the prose corpus, and
dropping the class name from the detail reddens leg 3. A token set that rejects a real pasted beacon
has replaced a false green with a false red and is the identical defect wearing the other sign. Per
REG-002 the corpus commits before the fix and fails against c380bb3 on all three legs (verified:
`_pr_has_proof_token('written to .claude/logs/hook-fires.jsonl', [], {'hook-fire'})` returns `True`;
the verbatim beacon line returns `False`; the partial union returns `True`; and the live detail
`missing: 1230` names no class).
**Parsimony (ADR-0056 D2b).** PROOF-INTEGRITY attests rendered DOM (ADR-0070 D5) and is a different
subject; CHECK 11 asserts that `qa-tester.md` *documents* `PROOF_SOURCE`, not that any PR carries it.
No existing mechanism judges token admissibility.
**Shadow (ADR-0056 D2c).** *Prose that grades itself as evidence* — a token satisfiable by describing
the artifact instead of showing it, so the verification rate measures how fluently agents write about
verifying. A future audit tests each token with one question: could an author who never ran the thing
type this while writing an honest sentence about it? If yes, the shadow is back.

### D5 — A guard reports what it observed and enumerates the states consistent with it; it never prescribes an action that is wrong in one of them

**The general principle is `(advisory)`.** *When any guard blocks or warns, its message states the
observation and the set of states consistent with that observation; it does not assert a single cause
it cannot distinguish, and it does not prescribe a remedy that is correct in only some of those
states.* This is tagged advisory under ADR-0056 D1's own escape clause, deliberately and with the
reason stated: judging whether an arbitrary guard's advisory text is correct *in every state
consistent with its observation* requires enumerating those states, which is exactly the judgment no
deterministic mechanism available here can perform. Revision 1 stated this clause as a bare general
obligation with a mechanism covering only one guard — the untagged-and-uncheckered shape ADR-0056 D1
forbids and the shape this very ADR condemns elsewhere. Tagging it is the honest disposition;
promoting it to a checked rule is a future decision with a real mechanism behind it, not a wish.

**The named instance is binding and deterministic.** For `stop-reviewer-gate.sh:105–106`: the
observation is *"open PR #N carries no comment matching `VERDICT: APPROVE`"*. At least two states
produce it — the reviewer has not been dispatched, **or** the PR is correctly awaiting its
prerequisite `codebase-critic` pass at a closing slice (PIP-013 / ADR-0046 D3). The message names
both, plus the `STOP_GATE_BYPASS=1` escape. It stops instructing "dispatch reviewer subagent before
declaring done", which was wrong on all five of its 2026-08-22 firings on PR #1249 and, if followed,
would have reproduced the #1205 ordering miss.

**The gate still blocks, and this is not a weakening.** The *decision* is correct under both states —
in both, the session must not declare itself done — so only the *diagnosis* is withdrawn. Making the
states actually distinguishable is a separate, larger change and is explicitly out of scope: the
distinguishing datum is not visible from where the hook looks, because `codebase-critic` posts its
verdict on the PRD issue rather than the PR (verified — PR #1247 carries zero such comments), so
diagnosis would require PR → slice → parent-PRD → issue-comment resolution on the session-stop path.

**Enforcement (rule #23) — for the named instance.** A regression test asserting the DENY-path stderr
names both states (greps for `codebase-critic` and for the not-yet-dispatched state) and contains no
bare single-cause imperative. **How this check can fail:** revert the wording, or add a third state to
the gate's logic without naming it, and the test reddens. Per REG-002 it commits before the fix and
fails against c380bb3 (`grep -c 'codebase-critic' .claude/hooks/stop-reviewer-gate.sh` = **0**).
**Parsimony (ADR-0056 D2b).** No mechanism reads guard advisories for correctness. `AS-AUDIT`
(CHECK 18) rates subagent-prompt quality, not hook stderr; `codebase-critic` judges cumulative PRD
drift, not a single message's logic. This is a per-guard textual invariant with no existing host.
**Shadow (ADR-0056 D2c).** *The confident wrong instruction* — a guard whose advice, followed, causes
the very defect it believes it is preventing, so the guard converts from a safety mechanism into a
delivery vector for the failure. A future audit tests it by enumerating, for each guard advisory, the
states consistent with its observation, and checking the advice is correct in all of them.

---

## Consequences

- **`HOOK-INTEGRITY` does NOT go green, no named hook is guaranteed to leave the drift list on merge
  day, and the ADR does not pretend otherwise.** Revision 1 claimed that after D1–D3 "`auto` and
  `pre-tool-edit` leave the drift list". That claim was false, and it was false for a reason worth
  recording, because this ADR reasoned correctly about the identical mechanism one paragraph away
  (D2's "historical status-less lines stay uncounted") and then inverted it here.
  `check_hook_integrity` flags on `ok < att` over a rolling 7-day window filtered only on `ts`
  (`:2007–2014`, `:2042`). The emitter-side repairs (D1) are **not retroactive**: `pre-tool-edit`'s
  432 in-window terminal-less attempts and `stop-reviewer-gate`'s pre-fix DENY traffic keep those
  hooks in drift until the history ages out on its own schedule. The `auto` repair (D3) **is**
  reader-side and does rescore the whole window at once, but HOK-008(a)'s attempt-before-parse
  ordering guarantees a nonzero in-flight residue on a stream that size at essentially any read, and
  any residue is `ok < att`. What the merge buys is that every affected numerator stops being
  *structurally* zero. The honest invariant is **"these hooks leave the drift list once the pre-fix
  window ages out"**, and the row **stays FAIL** meanwhile — also because `session-start(36/48)` is a
  real, undiagnosed drift deliberately out of scope (#1118 blocks its diagnosis). A slice that
  "verifies" by watching for a clean list will wait forever; a slice that widens
  `_HOOK_INTEGRITY_WINDOW_DAYS` to stop waiting has replaced the defect with a worse one.
  **The point of this work is that the remaining red becomes the true one** — what changes for
  `session-start(36/48)` is its *status*: it becomes the only drift entry that is neither an artifact
  of the check nor pre-fix history awaiting expiry. **No claim is made here about where any name
  appears in the rendered list, or in what order.** `drift_hooks` is built over
  `sorted(attempts.items())` (`:2039`) and D1/D2 newly admit `dashboard-autostart`, `pre-tool-bash`
  and `user-prompt-submit` into `attempts`, so any position assertion written before the merge is an
  assertion about merge-day state this ADR's own thesis forbids. Revision 2 carried one; it is
  withdrawn rather than re-derived.
- **`PROOF-PRESENCE`'s reported rate falls hard: 9/10 → 1/10** on the live 10-PR window
  (`[1249, 1247, 1245, 1243, 1230, 1223, 1222, 1220, 1203, 1201]`), re-simulated at c380bb3; the
  survivor is #1201. Seven of the nine losses fail on the `browser` class alone. That is not a
  regression; it is the compliance rate against the union rule ADR-0061 D1 has stated verbatim since
  2026-06-12. `check_proof_presence` has no FAIL branch (`:3074`), so the result stays `WARN` and the
  health strip does not redden — the number simply stops flattering us. D4(c)'s per-class detail is
  what makes the low number actionable rather than merely depressing.
- **Accepted loss — this ADR does not make proofs forgery-proof.** It makes them description-proof.
  The controls that would resist a fabricated proof (ADR-0061 D2 `PROOF_SOURCE` validation, D5
  artifact `stat`) exist on paper and are not wired into `check_proof_presence`. Named, not closed.
- **Accepted loss — D3's general half is a critic rubric, and D5's general clause is advisory.** For
  an ADR whose subject is checks that assert unstated invariants, having one governing principle
  enforced by the softest mechanism ADR-0056 admits and another carrying no mechanism at all is an
  uncomfortable result. It is the honest one: the deterministic escalation for D3 (a registry-wide
  `authority` field with a CI resolver) is specified in Alternatives and is what a future audit should
  reach for if the rubric proves ignored, and D5's general clause is tagged rather than pretended.
- **Accepted loss — one named non-conformance survives.** `session-start.sh:42`'s
  `status:"python3_selftest"` stays, behind one grandfathered literal carrying its issue number,
  because fixing it during this work would confound the out-of-scope `36/48` measurement: that line
  fires on **every** session-start (102 records all-time, 48 in the live window), in the same run as
  the `attempt`/`ok` pair the `36/48` ratio is computed from. It is the only exception, it is
  enumerated rather than categorical, and its removal is one line. The three further out-of-set
  literals found across revisions 2 and 3 — `log-tool-event.sh:303`'s `"rotation"`, and
  `log-tool-event.sh:333` / `session-start.sh:308`'s lowercase `"error"` — are **repaired instead of
  joining it**. `session-start.sh:308` is repaired despite living in the deferred hook because it is
  measurement-neutral where `:42` is not — and structurally so, not merely by volume: it writes
  through the embedded-python `beacon()` helper (`:234`), whose `"hook"` field is `event_type` =
  `session_context_injected` (`:227`), so it lands under a **different label** from the
  `session-start` printfs at `:35`/`:323` the `36/48` ratio is computed from and can touch neither
  the `attempt` nor the `ok` counter that ratio reads. Its **zero** records in the log's entire
  history (all 12 lowercase-`error` records are `log-tool-event`'s, under the `agent_start` label)
  corroborate that; they are not what establishes it.
- **Three previously-invisible beacon streams become visible** (`pre-tool-bash`,
  `user-prompt-submit`, `dashboard-autostart`). `HOOK-INTEGRITY`'s ratio list grows three names.
  Predicted to pair 1:1 on post-merge fires, with the in-flight-residue tolerance D2 states; a
  persistent or large gap means a real defect surfaced and must be captured, not suppressed.
- **Beacon volume rises.** `pre-tool-edit` fired 432 times in the live 7-day window and roughly
  doubles its line count; `dashboard-autostart` (13) and `user-prompt-submit` (132) likewise;
  `pre-tool-bash` gains no lines (it already writes two). This is within `LOG-ROTATION`'s remit — no
  new rotation machinery, and D2's `log-tool-event.sh:303` repair leaves the existing rotation record
  in place, only moving its label out of `status`.
- **The always-loaded rule surface grows by two statements** (VER-009, VER-010, GLOBAL scope, rendered
  into `.claude/generated/_global.md`), and HOK-008's path-scoped statement gets longer. Rule-id total
  moves by **+2** from the c380bb3 value of 86; absolutes are re-derived at implementation because a
  sibling ADR moves it concurrently.
- **#1251 stays open unless the sibling ADR lands.** D3 names it as an instance of the same principle
  in the opposite direction, but does not repair it. If the promotion-ack ADR is re-scoped or dropped,
  a vacuous gate remains vacuous, and the honest read is that this ADR's principle identified it
  without fixing it.

---

## Alternatives considered

- **Exempt terminal-less hooks from `HOOK-INTEGRITY` instead of making them beacon** (#1233's own
  second proposal). Rejected. An exemption mechanism lets a genuinely dead hook hide inside it, and
  ADR-0057 D1(a)'s stated purpose — *"a crash after the beacon is visible as attempt-without-ok"* —
  only holds if non-crash terminals beacon. Exempting would preserve the row's green at the cost of
  the property the row exists to measure.
- **Widen the enumeration to ALLOW / ASK / DENY / ERROR** (revision 1's own proposal). Rejected on
  discovering ADR-0079 D3: a *fifth* value (`warn`) was decided two days before this ADR's date and is
  live in `pre-tool-bash-classify.py:166`, so a central four-value list would have been stale on
  arrival — the third such list in the repo. Every attempt to enumerate gate outcomes centrally has
  been overtaken within months. D1 relocates instead: `status` closed and central, `outcome` additive
  and per-gate.
- **Delete `HOOK-INTEGRITY` and `PROOF-PRESENCE` outright** — #1251's phrasing, *"a deleted check is
  more honest than a vacuous one"*, is correct as far as it goes. Rejected here because it does not
  apply: deletion is right when the invariant is not owed **and cannot reasonably be made owed**.
  Both invariants here are real and, after D1 and D4, contractually owed. Deleting them would trade a
  lying instrument for no instrument.
- **Hand-edit each terminal instead of an EXIT trap.** Rejected: seven sites in `pre-tool-edit.sh`,
  nine in `stop-reviewer-gate.sh`, and #846 already proved the failure mode by adding `emit_ok_beacon`
  to the latter while the `exit 2` path slipped through unnoticed for two months.
- **Grandfather `log-tool-event.sh:303`'s `status:"rotation"` alongside `python3_selftest`.**
  Rejected: two enumerated literals is how a list becomes a category, and the reason for the
  `session-start` deferral (confounding an out-of-scope measurement) has no analogue here — the
  rotation path is cold, zero live records carry the label, and the repair is one line.
- **A value-side-only emitter check** (revision 1's mechanism for D2). Rejected on the finding that it
  cannot redden on the dominant defect class: a status-less emitter contributes no values to extract.
  See D2's Enforcement.
- **Admit lowercase `error` into the closed `status` set** (the alternative to D2's sixth and seventh
  repairs) — attractive because `check_hook_integrity:2019` already accepts both spellings, so
  nothing downstream would notice. Rejected: it puts two spellings of one concept inside a set whose
  entire purpose is that there is exactly one, and it would make `{attempt, ok, ERROR, error}` the
  fourth central vocabulary this ADR is trying to stop producing. The repair is two tokens.
- **Exempt runtime-variable `status` sites from the value leg and rely on the live-fire test**
  (revision 2's mechanism). Rejected on the finding that the live-fire test drives the success path
  and never reaches `beacon("error", …)`, so the value was invisible to both named mechanisms. The
  call graphs are closed and two greps wide; resolving them is cheaper than the exemption was.
- **Mint a new hooks-scope rule id (HOK-010) for the beacon schema.** Rejected on a verified
  structural constraint: `tools/gen_rules.py` parses exactly one `scope` per ADR (`:235`, gated
  `:240`), so a `verification`-scope ADR cannot declare a `hooks`-scope id, and splitting this into
  two ADRs to dodge that would fragment one decision across two files. `.claude/rules/hooks.md` is
  path-scoped to `.claude/hooks/**` — the correct, narrow audience for D1 and D2 — and is reached by
  amending HOK-008's statement in place, which has six precedents in that same generator file and
  touches no ADR.
- **Promote the honesty principle to a new numbered CLAUDE.md rule #24.** Rejected. DOC-003 makes
  numbered anchors permanent (never renumbered, never deleted, only retired), so a numbered rule is
  the most expensive slot in the repo. VER-009 is GLOBAL scope, rendered into
  `.claude/generated/_global.md`, and therefore reaches the identical always-loaded audience at a
  reversible cost.
- **A registry-wide `authority` field on all 50 health checks, resolved by a CI check.** This is the
  fully deterministic version of D3 and it is the right long-term shape. Rejected *for this PRD*: it
  is a 50-row retrofit plus a resolver, entirely outside this PRD's criteria and slice budget, and it
  would displace the six defects the PRD exists to fix. Recorded here as the named escalation, with
  the trigger stated in Open Questions.
- **Retokenize the `static` and `browser` classes in the same PR** (revision 1's Propagation
  mandate). Rejected as scope this ADR did not budget: no criterion, no baseline, no slice allowance,
  and it would move the 9/10 → 1/10 number published above. Descoped to a follow-up; see D4(a).
- **Loosen the proof tokens instead, to credit #1230/#1191/#1190's real evidence** (timing proofs,
  REG-002 fails-then-passes transcripts, `gh pr checks` output — all substantive, all intersecting no
  token). Rejected: it pulls the opposite way from D4 and would muddle a single-signed verdict. It is
  a real gap; D4(c)'s per-class detail is what will supply the evidence to settle it, and the return
  trigger is stated in Open Questions.
- **Record the conjunctive union as a supersession of ADR-0061 D1.** Rejected: D1 already mandates the
  union in those words. Recording a supersession would assert the contract changed when only the code
  was wrong — which is exactly the class of false statement this ADR is about.
- **Widen scope to #1251, #1252 and #1253.** Rejected per issue; see Open Questions for the reasoning
  and the disposition of each.
- **Teach `stop-reviewer-gate` to genuinely distinguish the two block states.** Rejected on measured
  cost, not principle: `codebase-critic` posts on the PRD issue, so the hook would need
  PR → slice → parent-PRD → issue-comment resolution — two or three extra `gh` round-trips on the
  session-stop path. D5 makes the gate stop asserting what it cannot see; making it observable is a
  design change, not a repair, and must not be smuggled into the small one.

---

## Open questions (operator decisions, not guesses)

1. **Is `PROOF-PRESENCE`'s honest 1/10 acceptable standing, or does the ADR-0061 D1 route table need
   recalibrating?** The dominant driver is `dashboard/** → browser`: seven of the nine losses in the
   c380bb3 window fail on that class alone, and any PR touching `dashboard/health.py` is held to a
   screenshot. Arguably correct (the health strip is the surface that changed) and arguably
   over-broad (a registry-only edit renders nothing new). Deliberately not pre-decided — D4(c)'s
   per-class detail is the instrument that will supply the evidence, and recalibration is a follow-up
   ADR with measurements in hand. The `static`/`browser` retokenization descoped in D4(a) rides the
   same decision.
2. **Should `session-start.sh:42`'s `python3_selftest` be fixed now instead of grandfathered?** This
   ADR defers it to avoid confounding the out-of-scope `36/48` measurement. The counter-argument is
   real: the deferral leaves one non-conforming emitter and one exception literal in a checker whose
   whole point is that exceptions hide things. Operator call. **Return trigger if deferred:** the
   `36/48` drift gets diagnosed (or #1118's session-boundary instrumentation lands), at which point
   the confound disappears and the deferral has no remaining justification.
3. **Does D3's general half need the deterministic version now?** It ships as a reviewer rubric rule,
   the softest mechanism ADR-0056 D4 admits. **Escalation trigger, stated over both directions of the
   shadow because a trigger blind to half its own subject is the defect this ADR is about:** two
   `captured` issues from distinct PRDs, each documenting **either** a check that FAILs a subject on
   an invariant no contract states (the permanently-red direction) **or** a check that cannot FAIL any
   reachable input — vacuous, self-satisfying, or asserting a condition the gated act itself writes
   (the permanently-green direction, #1251's class). Revision 1's trigger named only the first, which
   made it unreachable for the second: a vacuous check never FAILs anything, so it can never produce a
   qualifying capture, and the mirror D3 explicitly names could recur indefinitely without ever
   commissioning the escalation. Either direction, two captures, commissions the registry-wide
   `authority` field plus its CI resolver.
4. **Where does this ADR ship?** ADR-0003 D8 places a PRD's macro-ADR in slice 1's PR ("They ship
   together in slice 1 of the implementation", `decisions/0003-*.md:138`), and the PRD's slice 1 is
   operator-fixed as the R-LOC jq repair (#1246), which has nothing to do with beacon contracts or
   proof tokens. This is a decomposition call and therefore the slicer's, per rule #16 — flagged here
   so it is not silently resolved by whoever implements first.

---

## Propagation

Per-file disposition of every tracked-surface hit, with line numbers **derived at `origin/develop`
c380bb3**. `decisions/` archive, `qa-proof/` evidence, `.claude/logs/` history, and
`.claude/worktrees/**` copies are GRANDFATHERED throughout. The dying-name greps are `hook-fire`
(as a token literal), `"status":"OK"`, `"status": "rotation"`, `python3_selftest`, and
`_PROOF_TOKENS`; a second sweep runs on `ADR-0057 D2` since a cite need not spell a dying name.

**Rule layer (D1, D2 — the amendment mechanism, never ADR-0057 itself):**
- `tools/gen_rules.py:523–527` — `_RULE_STATEMENTS["HOK-008"]`: AMENDED to add the terminal-beacon
  obligation and the closed `status` vocabulary with the additive `outcome` field, closing with
  `(ADR-0057 D1, fail-loud contract, as amended by ADR-0083 D1/D2)`. Six precedents for this exact
  form at `:380`, `:387`, `:438`, `:600`, `:789`, `:817`.
- `tools/gen_rules.py` `_RULE_STATEMENTS` (declared `:273`, consumed by `_get_rule_statement` `:823`)
  — ADDED `VER-009` (D3 + D5) and `VER-010` (D4: evidence-shaped proof tokens; the route union is
  conjunctive; the detail names the failing class). Both `verification` scope → GLOBAL
  (`SCOPE_TARGET:103–118`) → rendered into `.claude/generated/_global.md`, always loaded.
  **VER-009 carries the `(advisory)` marker inline, on the D5 half only**, because that is the
  always-loaded text ADR-0056 D1 binds ("MUST be explicitly tagged `(advisory)` in its rule text") and
  revision 2 dropped the tag in the fusion. The statement renders as: *"A check may only FAIL a
  subject on an invariant that subject owes — an accepted ADR decision, a generated rule id, or a
  documented interface contract; if the invariant is not owed the check is wrong, not the subject, and
  a check's subject set is defined rather than assumed. **(advisory)** When a guard blocks or warns,
  its message states the observation and the states consistent with it, never asserting a single cause
  it cannot distinguish (ADR-0083 D3/D5)."* The marker is scoped to the second sentence rather than
  the whole statement because D3's half is mechanized (a deterministic regression test plus the
  reviewer rubric ADR-0056 D4 admits) and tagging it advisory would understate it. Splitting into
  three ids instead — VER-009 = D3, VER-010 = D5 `(advisory)`, VER-011 = D4 — is the cleaner
  factoring and was rejected only because it moves the **+2** rule-id invariant to +3 in the three
  places this ADR states it — the Consequences bullet, the `RULE_IDS_BASELINE` bump below, and
  `CLAUDE.md:9`'s `VER-001..010` id range — while a sibling ADR is concurrently moving the same
  counter. The slicer may take the split if it prefers, re-deriving all three with it.
- `tools/gen_rules.py:143` — `RULE_IDS_BASELINE: int = 86` → **88**. **The invariant is +2 for
  VER-009/VER-010**; both the literal and the next free `VER-0NN` are re-derived at implementation
  from the live constant and CHECK 17's reported total (`gen_rules.py --check` reports
  `CONSERVATION OK: rule_ids total 86 == baseline 86` at c380bb3), because the sibling promotion-ack
  ADR adds +1 concurrently. No `rule_ids` are removed — the ADR-0057 D2 supersession is per-decision,
  so ADR-0057 keeps `superseded_by: []` and HOK-008/HOK-009 stay in the active set. VER ids currently
  in use: VER-001..VER-008, no gaps; next free = VER-009.
- `tests/test_loc_cap_1162.py:174` — `self.assertIn("RULE_IDS_BASELINE: int = 86", self.text)`:
  UPDATED to the new value **in the same PR as the `gen_rules.py` bump**. This is the repo's standing
  moving-counter line; leaving it stale turns the bump into a red suite. **(Was `:180` at
  `origin/main`; the file lost five lines at `0753aa7` when the `/build` assertions were deleted.)**
- `.claude/rules/hooks.md:21` — GENERATED. Regenerates from the HOK-008 amendment; never hand-edited.
  CI CHECK 17 and CHECK 20 enforce freshness.
- `.claude/generated/_global.md` — GENERATED. Gains an `#### Source: ADR-0083` block under
  *Verification rules*.
- `CLAUDE.md:9` — the generated-atomic-rules note's id list: `VER-001..008` → `VER-001..010`. The
  `PIP-001..025` segment in the same sentence is the sibling ADR's edit, not this one's. Rule
  NUMBERS in §1 are untouched (DOC-003).
- `decisions/README.md` — a new ADR-0083 index row, AND a Status-column annotation on the ADR-0057 row
  recording the D2-partial supersession, matching the ADR-0080/0081 precedent. DOCS-8's known regex
  blind spot for the per-decision header form (#1195) persists, so the companion PRD should carry the
  grep as its interim check.

**Hook layer (D1, D2, D5):**
- `.claude/hooks/pre-tool-edit.sh` — `:41–43` attempt beacon UNCHANGED; a `trap … EXIT` ADDED after it
  that emits one `status:"ok"` terminal iff none was emitted, covering all seven terminals (`:54`
  `emit_ask`, `:66` `emit_deny`, `:72` subagent skip, `:108` ERROR, `:115` allowlist, `:124` empty
  path, `:129` untracked). `emit_ask` (`:47–55`) gains `outcome:"ask"`, `emit_deny` (`:58–67`) gains
  `outcome:"deny"`; the ERROR path at `:105–107` must suppress the trap's `ok` so exactly one terminal
  is written.
- `.claude/hooks/stop-reviewer-gate.sh` — `:104–108` the DENY path: gains one terminal beacon carrying
  `"status":"ok"` and `"outcome":"deny"` before `exit 2` (`:107`). `:105–106` stderr: REWRITTEN per D5
  to state the observation and name both states (reviewer not yet dispatched; PR correctly awaiting
  its prerequisite `codebase-critic` pass per PIP-013) plus the `STOP_GATE_BYPASS=1` escape. `:46–51`
  `emit_ok_beacon` and `:54–60` `emit_error_beacon` keep their mechanism; the trap must not
  double-emit after either. **Hazard carried from the PRD:** `check_hook_integrity` counts lowercase
  `"ok"` only (`:2017`) — an uppercase `"OK"` here would change nothing.
- `.claude/hooks/pre-tool-bash.sh:104` — the attempt printf `{"hook":"pre-tool-bash","ts":…}`: gains
  `"status":"attempt"`. This is what makes the largest beacon stream in the log countable. `:108`'s
  ERROR beacon already conforms.
- `.claude/hooks/pre-tool-bash-classify.py:166` — `{"hook": …, "status": "OK", …}` → `"ok"`. One
  token; the `outcome` field it already writes (`deny`|`warn`|`allow`, decided by ADR-0079 D3, written
  by `_write_outcome_beacon` `:158–170`) is UNCHANGED and is D1's reference pattern.
- `.claude/hooks/dashboard-autostart.sh:23` and `.claude/hooks/user-prompt-submit.sh:24` — each
  single status-less printf gains `"status":"attempt"` plus an EXIT-trap terminal.
- `.claude/hooks/log-tool-event.sh:302–308` — the rotation record's `"status": "rotation"` (`:303`)
  moves to `"status":"ok"` + an additive `"event":"rotation"`. NEW in revision 2; see D2's table.
  `:71` (attempt under the argv label) and `:91–100` (`beacon()`, terminal under the derived key) are
  **unchanged** — that behaviour is correct per HOK-008(a) and the fold is a reader-side change (D3).
- `.claude/hooks/log-tool-event.sh:333` and `.claude/hooks/session-start.sh:308` — `beacon("error",
  reason)` → `beacon("ERROR", reason)`, one token each, on the stdin-rejection paths. **NEW in
  revision 3.** These are the two literals the `beacon()` helper's call graph resolves to; the helper
  bodies themselves (`log-tool-event.sh:92`, `session-start.sh:235`) are UNCHANGED, as are the four
  conforming `beacon("ok")` calls (`log-tool-event.sh:166`, `:315`; `session-start.sh:290`). The
  `reject_obj` writes immediately above each (`log-tool-event.sh:324`, `session-start.sh:298`) target
  `workflow-events.rejects.jsonl`, not `hook-fires.jsonl`, and are NOT beacon records — no edit owed.
- `.claude/hooks/session-start.sh:42` — `"status":"python3_selftest"`: NOT CHANGED. The single named
  grandfather (D2), carrying its `captured` issue number in the new CI check's exception literal.
  `:35` (attempt) and `:323` (`ok`) already conform. Note this file is **partly** edited (`:308`) and
  partly grandfathered (`:42`); the two are separate lines on separate paths and the reasoning for
  each is in the Consequences bullet — an implementer must not read the grandfather as covering the
  file.

**Check layer (D3, D4):**
- `dashboard/health.py:1963–2055` `check_hook_integrity` — `:2002` raw `obj["hook"]` grouping REPLACED
  by a registered-subject fold using `dashboard/discovery.py:353 _auto_mode_derived_keys`, already
  imported at `:6265` for STREAM-LIVENESS and used at `:6291`; `:2015–2020` reads the closed `status`
  vocabulary; the drift list built at `:2039–2043` is constrained to hooks registered in
  `.claude/settings.json` (with `auto` admitted as `log-tool-event`'s stream identity per D3's
  corollary). **`:2019–2020`'s unfiltered `error_count` accumulator and the `:2054` verdict term it
  feeds are brought under the same subject set** (D3): an ERROR under a derived key is attributed to
  its registrar's stream identity, the `:2049` detail part names the label it was attributed to, and a
  label outside the subject set is not scored. **NEW in revision 3** — revision 2 constrained only the
  drift list and left the row's second FAIL trigger ungoverned. `:1964–1975` docstring: EDITED to
  state the invariant **and cite its authority** (HOK-008 as amended by this ADR), and to say *whose*
  ERROR beacons FAIL the row — `:1974` currently says only "ERROR beacons in any window → FAIL". The
  docstring is where D3's rule is made visible to the next reader. `:2027–2034`'s empty-window WARN branch is UNCHANGED but is called out in the companion
  PRD's Production check as the vacuity vector a live-feed precondition must close.
- `dashboard/health.py:2747–2752` `_PROOF_TOKENS` — the `hook-fire` list at `:2749` REPLACED per
  D4(a): `hook-fire` / `HOOK-FIRE` removed, beacon-shaped patterns added. **The `static` and `browser`
  classes are NOT touched in this PR** — descoped per D4(a). *(Revision 1 gave this anchor as
  `:2747–2760`; the dict ends at `:2752` and `:2760` is inside a later comment block.)*
- `dashboard/health.py:2774–2782` `_pr_has_proof_token` — the `any`-over-classes loop at `:2777–2781`
  (returning on first hit at `:2781`) → `all`-over-classes (D4b); returns the set of unsatisfied
  classes rather than a bare bool so `check_proof_presence` can name them. Docstring `:2775` EDITED —
  it currently reads *"contains a proof token for ANY route class"*, which is the defect written down.
  *(Revision 1 gave the loop as `:2778–2782` and the search as `:2791`; the case-insensitive
  `re.search` is at `:2780`, and `:2791` is inside `check_blind_dispatch_rate`'s docstring.)*
- `dashboard/health.py:3000–3076` `check_proof_presence` — `:3070–3073` detail string: gains the
  per-PR failing class (D4c). `:3074`'s `result = "PASS" if not without_proof else "WARN"` is
  UNCHANGED — the absence of a FAIL branch is why the falling rate does not redden the strip.
  *(Revision 1 gave the detail as `:3068–3073`; `:3068` is the `rate` computation.)*
- `dashboard/discovery.py:277`, `:311` — `if status in ("attempt", "")`, the second reader of the
  same field: BEHAVIOUR UNCHANGED, COMMENT EDITED to name D2 as the authority and to record that the
  `""` branch is now a legacy compatibility shim whose removal trigger is "no status-less beacon
  remains in the rolling window". Changing it now would silently rescore the grandfathered history.
  *(Revision 1 gave `:310`; that is the explanatory comment, the branch is `:311`.)*
- `dashboard/discovery.py:278`, `:313` — `elif status == "error"`, lowercase only: BEHAVIOUR
  UNCHANGED, COMMENT EDITED alongside `:277`. **NEW in revision 3.** This branch has never counted the
  three uppercase-`ERROR` emitters, and after D2's `:333`/`:308` repairs it counts none of the five.
  Aligning it with `health.py:2019`'s `("ERROR","error")` is one line and is the obvious repair, but
  it would newly score those three grandfathered uppercase **emitters** — the same rescoring hazard
  that freezes the `""` branch — so it rides the identical removal trigger, tracked as **#1264**
  (triaged trivial-lane; a hotfix after the companion PRD lands). The counter it empties reaches no
  rendered surface and no verdict — see D2's known-reader-consequence paragraph. Recorded here rather
  than left for an implementer to discover as an unexplained drop in `error_count`.
- `tools/ci-checks.sh` — a new CHECK (D2's presence-side + value-side emitter grep) added after the
  current last check. **Integer re-derived at implementation:** CHECK 23 is last at `:1070` at
  c380bb3 and the sibling ADR claims 24. `CLAUDE.md:132`'s *CI check script* Map row, whose
  enumeration currently ends at CHECK 23, is EDITED to include it. *(Revision 1 gave `CLAUDE.md:133`.)*

**Producer/consumer coupling for the proof tokens (must move with D4 or the two ends disagree):**
- `.claude/agents/qa-tester.md:269` — the hook-fire row of the ADR-0061 D1 route table
  (*"happy-path proof (exit= + log:) AND induced-failure beacon pair"*): EDITED so the mandated
  `PROOF:` shape is a **pasted verbatim beacon line** plus the exit code, i.e. exactly what D4's
  tokens now match. `:275` (ADR-0061 D4 negative-path row), `:521` (the `PROOF:` field spec) and
  `:540` (the hook-fire evidence summary) EDITED to the same shape. `:278`'s union statement is
  already correct and is GRANDFATHERED unchanged — it is the prose the code is being brought into
  conformance with. *(All five line numbers re-verified at c380bb3: the file's only develop-side
  changes were `:1` and `:549`.)*
- `.claude/skills/ship/SKILL.md:264` — *"`hook-fire` route: `PROOF:` MUST contain `exit=` AND
  `log:`"*: EDITED to require the beacon line as the `log:` content. **(Was `:235` at `origin/main`;
  `ship/SKILL.md` gained 53 lines net at `0753aa7` when `/build` was folded into it.)**
- `.claude/skills/build/SKILL.md:156` — **RESOLVED, NOT CARRIED.** Revision 1 listed this
  byte-duplicate as CONDITIONAL on `/build` still existing. It does not: `0753aa7` (#1249, ADR-0081
  D4) deleted `.claude/skills/build/` in its entirety, and `ls .claude/skills/` at c380bb3 returns
  six directories with no `build`. The hit is gone; no edit is owed.

**Reviewer rubric (D3's general half):**
- `.claude/agents/reviewer.md` — a new rubric rule ADDED: a PR adding or tightening a deterministic
  check must name the contract clause the check enforces. Separately and independently,
  `.claude/agents/reviewer.md:233` — the R-LOC jq command in the R-LOC section (`:219–238`): FIXED per
  #1246 (each path test wrapped in its own `(.path | …)`), which is the PRD's operator-fixed slice 1
  and is listed here only so the file's two edits are not mistaken for one.
- `.claude/agents/slicer.md`, `.claude/agents/implementer.md` — one contract line each per #1237
  (the brief never restates R-LOC; read the canonical definition in `reviewer.md`). Companion-PRD
  criterion 4; listed for completeness because it is the same file family. Note `slicer.md` contains
  **zero** references to `reviewer.md` today (`implementer.md` has two).

**Tests:**
- NEW: hook terminal + field-split live-fire (D1), beacon status presence/vocabulary (D2),
  HOOK-INTEGRITY subject-set / `auto` fold (D3), three-legged proof-token corpus including the
  class-naming leg (D4), stop-reviewer-gate message states (D5), R-LOC jq extraction (companion-PRD
  criterion 2, with its REG-002 ordering asserted by criterion 3). Every one commits **before** its
  fix per REG-002.
- `tests/test_hook_honesty_846.py` — asserts `stop-reviewer-gate` emits `ok` at success terminals:
  EXTENDED (not inverted) to cover the DENY terminal. Its subject decision is being extended, not
  superseded, so its existing assertions stand.
- `tests/test_loc_cap_1162.py:174` — see the rule-layer entry above; moves with any baseline bump.
- `tests/test_stream_liveness_beacon_drift_1106.py`, `tests/test_auto_hook_classification_1056.py`,
  `tests/test_hook_liveness_849.py`, `tests/test_hook_parsimony_877.py`,
  `tests/test_discovery_telemetry_root_1052.py` — read the same beacon
  surface. VERIFY at implementation that none asserts the status-less or uppercase-`OK` shapes; none
  is expected to change, but this is a check, not an assumption. The last of the five is listed with
  its disposition already established: it reads the surface through `discover_hooks()` but asserts
  `fire_count`, which counts `status in ("attempt", "")` (`discovery.py:311`), so all seven repairs
  leave it alone — a status-less emitter gaining `"status":"attempt"` moves a record between the two
  arms of that same condition, and no value-side repair touches either arm.
- `tests/quarantine.txt` — gained two entries at `c380bb3` (#1260) and #1261 records that the file
  deselects nothing (no conftest, no pytest config). Not this ADR's subject; noted so no implementer
  assumes quarantine will absorb a flaky live-fire test.

**Verified no-hits (so nothing is silently missed):**
- `README.md`, `README.template.md`: NO HITS for `HOOK-INTEGRITY`, `PROOF-PRESENCE`, `hook-fires`,
  `beacon` — nothing to regenerate on this axis.
- `dashboard/README.md`: NO HITS for the same four terms.
- `.claude/settings.json`: NO EDIT — hook registrations are unchanged; only the scripts' beacon
  emission changes.

---

## References

- Filed defects: [#1246](https://github.com/vojtech-stas/project-claude/issues/1246) (R-LOC jq
  truncation), [#1237](https://github.com/vojtech-stas/project-claude/issues/1237) (briefs paraphrase
  R-LOC), [#1233](https://github.com/vojtech-stas/project-claude/issues/1233) (HOOK-INTEGRITY
  un-PASS-able), [#1234](https://github.com/vojtech-stas/project-claude/issues/1234) (PROOF-PRESENCE
  token + `any`-union — *direction two*),
  [#1028](https://github.com/vojtech-stas/project-claude/issues/1028) (stop-reviewer-gate
  attempt-only), [#1250](https://github.com/vojtech-stas/project-claude/issues/1250)
  (stop-reviewer-gate asserts an unobservable cause). Also carried by the companion PRD:
  [#1255](https://github.com/vojtech-stas/project-claude/issues/1255) (HOOK-INTEGRITY blind to its
  three largest streams — D2's subject). Same-class, out of scope:
  [#1251](https://github.com/vojtech-stas/project-claude/issues/1251) (vacuous meta-tripwire — D3's
  mirror, repaired by the sibling promotion-ack ADR),
  [#1252](https://github.com/vojtech-stas/project-claude/issues/1252) (promote.sh docs vs code +
  CLAUDE.md miscite — DOC-005/CHECK 4/6 territory),
  [#1253](https://github.com/vojtech-stas/project-claude/issues/1253) (Decision Inbox concurrency —
  machine-wide personal tooling, outside this repo),
  [#1261](https://github.com/vojtech-stas/project-claude/issues/1261) (quarantine.txt deselects
  nothing), [#1262](https://github.com/vojtech-stas/project-claude/issues/1262) (root-worktree
  production-verify returns a false PASS — the reason the companion PRD's Production check names a
  detached worktree at the merged develop sha),
  [#1263](https://github.com/vojtech-stas/project-claude/issues/1263) (production-verify can count
  beacons written by pre-change hook bodies — the *emitter* axis of #1262, and the reason the
  companion PRD's Production check now separates reader-side assertions against the canonical log
  from emitter-side assertions through the scratch-log seam; `dashboard/health.py` has zero
  `WORKFLOW_LOG_DIR` references and `check_hook_integrity` reads the git-common-dir-parent log at
  `:1979`),
  [#1264](https://github.com/vojtech-stas/project-claude/issues/1264) (`discovery.py:313` counts
  lowercase `error` only — the deferred reader repair D2's known-reader-consequence paragraph and the
  Propagation entry both name as their tracker),
  [#1265](https://github.com/vojtech-stas/project-claude/issues/1265) (`hook-fires.jsonl` carries
  torn concurrent appends, so a grep census and a parser disagree about the same log — the reason
  every grep census in this document, the fact ledger below included, is an approximation).
  Blocked prerequisite:
  [#1118](https://github.com/vojtech-stas/project-claude/issues/1118) (session-boundary
  instrumentation, without which `session-start(36/48)` cannot be diagnosed).
- ADR-0057 D1 (extended, fifth clause) + D2 (three-outcome enumeration partially superseded →
  relocated across `status`/`outcome`); D3/D4/D5 stand. **ADR-0079 D3** (the `outcome` field and its
  `deny`|`warn`|`allow` vocabulary — adopted, not replaced). ADR-0023 D3 (the `ask` decision that
  pre-dates ADR-0057 D2's enumeration). ADR-0061 D1 (route table + union clause — conformance
  restored, contract unchanged), D2/D5 (the forgery-resistance this ADR names and does not supply),
  D4 (negative-path obligations the qa-tester hook-fire row carries). ADR-0046 D3 / PIP-013
  (codebase-critic-before-reviewer, the state D5's guard must name). ADR-0056 D1/D2/D4 (rule #23, the
  three-part admission test, critic-rubric-as-mechanism, and the `(advisory)` escape D5's general
  clause now takes). ADR-0067 D2/D3 (R-PROVE, the rule-#13 regression rider). ADR-0004 D2
  (bootstrap-mode). ADR-0073 D1/D3 (the generated rule layer). ADR-0070 (the two-tier topology that
  makes `develop` the correct baseline and the root worktree the wrong verification environment).
  ADR-0080/ADR-0081 (structural precedent: per-decision supersession header, propagation ledger,
  re-derivation escape-hatches, shadow-per-decision; ADR-0081 D4 is the `/build` retirement that
  resolved revision 1's conditional propagation entry). ADR-0070 D5 (PROOF-INTEGRITY — the adjacent
  check D4 argues parsimony against).
- Evidence re-derived at `origin/develop` c380bb3, 2026-08-22: 59,838 beacon lines in
  `.claude/logs/hook-fires.jsonl`; the live `HOOK-INTEGRITY` detail quoted verbatim in Context;
  `grep -c "exit=" .claude/logs/hook-fires.jsonl` = 0; `grep -c "as amended by" tools/gen_rules.py`
  = 6; `RULE_IDS_BASELINE` = 86 and `gen_rules.py --check` reporting
  `CONSERVATION OK: rule_ids total 86 == baseline 86`; `python dashboard/health.py --list | wc -l`
  = 50; last CI check = CHECK 23 at `tools/ci-checks.sh:1070`;
  `python dashboard/health.py --check PROOF-PRESENCE` → `WARN … 9/10 … missing: 1230`.

<!--
CITATION LEDGER (orchestrator: strip before landing)
Every ADR-NNNN D<n> cited above was verified by opening the file at origin/develop c380bb3 and
reading the literal heading. No cite was inherited from CLAUDE.md, from the briefing prompt, or from
the companion PRD. Revision 2 re-opened every one at the new baseline rather than carrying revision
1's verification forward.

ADR-0003 D8  "### D8: ADR-writing happens in two places in the pipeline"                   — decisions/0003-*.md:136-141,
               read first-hand. Its macro-ADR bullet reads verbatim at :138: "They ship together in slice 1
               of the implementation." Open Question 4's characterization matches. OK
ADR-0004 D2  "### D2: Bootstrap-mode policy explicit"                                      — bootstrap-mode. OK
ADR-0023 D3  "### D3: PreToolUse(Edit|MultiEdit|Write) hook mechanically escalates rule #10" — decisions/0023-*.md:59-67,
               read first-hand. Item 3 emits `hookSpecificOutput.permissionDecision: "ask"`, and :67 states it
               explicitly: 'The `"ask"` decision (NOT `"deny"`) preserves trivial-lane I3 ergonomics'. Direct
               textual support for D1's claim that ADR-0057 D2's list was incomplete at authorship. OK
ADR-0046 D3  "### D3: Cadence — once per PRD, at the last slice, before that slice's reviewer pass
               (supersedes ADR-0018's per-PR cadence)"                                     — the PIP-013 ordering D5 names. OK
ADR-0056 D1  "### D1 — Rule #23: every new rule ships with its check"                      — read verbatim at :16.
               Contains the escape D5's general clause now takes: "A rule whose enforcement is genuinely
               impossible or not yet worth building MUST be explicitly tagged `(advisory)` in its rule text."
               This is the authority for the (advisory) tag added in revision 2. OK
ADR-0056 D2  "### D2 — Mechanism-admission test in adr-critic (AC-ENFORCEMENT)"            — :20. (a) name the mechanism,
               (b) why no existing mechanism, (c) name the anti-pattern shadow. All three supplied per decision D1-D5. OK
ADR-0056 D4  "### D4 — Scope boundary"                                                     — :28, verbatim: "a critic rubric
               IS a deterministic-enough mechanism (dispatch + verdict are observable) for judgment-shaped
               concerns." The exact authority D3's judgment half leans on. Note it licenses a rubric for a
               JUDGMENT-shaped concern — which is why D5's *general* clause takes the (advisory) route instead. OK
ADR-0057 D1  "### D1 — Fail-loud beacon contract for all hooks"                            — clauses (a)-(d) read verbatim;
               NONE requires a terminal beacon on success or on a deliberate deny. Confirms the premise of D1/D3.
               EXTENDED, not superseded. Clause (a)'s attempt-before-parse ordering is also the source of the
               in-flight-residue tolerance D2's prediction and the Consequences now state. OK
ADR-0057 D2  "### D2 — Gate-hook failure semantics"                                        — literal text: "distinguish three
               outcomes: ALLOW, DENY (policy decision on successfully-parsed input), and ERROR (infrastructure failure)".
               PARTIALLY SUPERSEDED (enumeration RELOCATED across status/outcome, not widened — revision 2's
               correction). Its fail-open-loud, stop_hook_active and fixture-sid clauses STAND.
ADR-0057 D3  "### D3 — Capture-liveness gate in orchestrator skills"                       — stands, not cited in body.
ADR-0057 D4  "### D4 — Scope amendment: context injection (fifth category)"                — stands, source of HOK-009. Untouched.
ADR-0057 D5  "### D5 — Bootstrap-mode binding"                                             — stands. Untouched.
ADR-0061 D1  "### D1 — Verification-budget route table"                                    — literal text: "A change matching
               multiple globs takes the union of proof classes." Confirms D4(b) is CONFORMANCE, not a contract change. OK
ADR-0061 D2  "### D2 — Structured proof provenance: `PROOF_SOURCE:` and `ENV:` fields"     — the forgery-resistance D4 names
               as existing-but-unwired. OK
ADR-0061 D4  "### D4 — Negative-path proof obligations"                                    — hook PRs owe happy-path AND
               induced-failure proof; the qa-tester row D4 edits. OK
ADR-0061 D5  "### D5 — Artifact-existence assertion"                                       — the stat control. OK
ADR-0067 D2  "### D2 — R-PROVE: test-commit-precedes-fix-commit for fix-type slices"       — REG-002 ordering; also the
               authority for the companion PRD's criterion 3, split out of criterion 2 in revision 2. OK
ADR-0067 D3  "### D3 — Rule-#13 regression rider"                                          — applied to all five decisions. OK
ADR-0070     two-tier delivery (develop is the merge target; main trails) — the reason revision 2 re-baselines
               on origin/develop and the reason #1262's false-PASS vector exists. Heading family verified. OK
ADR-0070 D5  cited once as PROOF-INTEGRITY's source in D4's parsimony paragraph; heading verified in the
               sibling ADR's own ledger as "### D5 — Deterministic proof-integrity on rendered DOM". OK
ADR-0073 D1  "### D1" verified via CLAUDE.md:9's generated-rules note + tools/gen_rules.py's module docstring
               (GLOBAL/AREA classification, SCOPE_TARGET at :103-118). Used only for the rule-layer mechanics. OK
ADR-0079 D3  "### D3 — Hook overhead diet with an outcome-carrying beacon"                 — decisions/0079-*.md:39-43,
               read first-hand at c380bb3. Literal text at :41: "its beacon gains an `outcome` field
               (`deny`|`warn`|`allow`), making real deny history measurable for the first time." Accepted
               2026-08-20, scope pipeline, rule_ids [PIP-023]. NEW IN REVISION 2 — revision 1 cited this
               nowhere (grep -c "ADR-0079" on the draft = 0) while asserting a conflicting enumeration.
               This is the authority D1 now adopts for gate-outcome values. OK
ADR-0080 D1  "### D1 — The dashboard UI is the run-board plus a thin health strip; every other tab is deleted"
               — cited for "the only health surface left". OK
ADR-0081 D1-D4 — read in full; used as the structural model (per-decision supersedes header, propagation
               ledger, re-derivation escape-hatch, shadow-per-decision). Its D4 is the `/build` retirement,
               which at c380bb3 has LANDED (0753aa7) — revision 1's conditional propagation entry is
               resolved, not carried. OK
PIP-013 / PIP-020 / HOK-003 / HOK-008 / HOK-009 / VER-001..008 — rendered rule ids read from
               .claude/generated/_global.md and .claude/rules/hooks.md, not from memory.

FACT LEDGER (all re-derived at origin/develop c380bb3, 2026-08-22, by reading the files/logs directly.
Every line cite below was re-opened in revision 2; the four that were wrong in revision 1 are marked
[CORRECTED] with the old value, and three further errors found during the sweep are marked [CORRECTED*].
Revision 3 adds three entries marked [REVISION 3] and changes no prior entry: the prior integers were
re-checked at the same sha and all still hold.)
- Baseline: origin/develop = c380bb3 ("test: quarantine two flaky wall-clock timing assertions (#1260)").
  origin/main = f7378de, one merge behind (0753aa7 = the /build fold, #1249). 12 files differ.
- hook-fires.jsonl: 59,838 lines. 7d window census by (hook,status) produced the table in Context.
- Live `python dashboard/health.py --check HOOK-INTEGRITY` output quoted verbatim in Context
  (auto:0/6304, pre-tool-edit:0/432, session-start:36/48, stop-reviewer-gate:118/162).
- 7d auto fold, offline read seconds before the live one: attempts 6,290 == agent_start 113 +
  agent_complete 113 + bash_complete 5,627 + grill_qa 2 + post_tool 430 + skill_invoke 5 = 6,290.
  EXACT at that instant; the live check read 6,304 moments later. The INVARIANT plus its in-flight
  tolerance, not either integer, is the claim — and revision 1's own Δ=8 observation is now used as
  evidence FOR the tolerance rather than being recorded and then contradicted.
- pre-tool-bash: 22,706 status-less + 7,498 "OK" all-time; 11,011 status-less + 7,498 "OK" in 7d.
  Zero contribution to HOOK-INTEGRITY in either direction — verified by its absence from the ratio list.
- pre-tool-edit: 1,005 attempt (+16 legacy status-less) / 0 ok all-time; 432 attempt / 0 terminals in 7d.
  Seven executable terminals at :54 :66 :72 :108 :115 :124 :129 (line-numbered read). File is 170 lines.
- stop-reviewer-gate: 356 attempt / 230 ok / 1 ERROR all-time; 162 / 118 / 0 in 7d. `exit 2` at :107
  with no terminal beacon between :104 and :108 — read directly. File is 110 lines; nine terminals
  (emit_ok_beacon calls at :66 :71 :77 :92 :110, emit_error_beacon at :82 :85 :90, plus `exit 2`).
- session-start: attempt 48 / ok 36 / python3_selftest 48 in the 7d window. attempt :35, selftest :42,
  ok :323. NOT diagnosed — out of scope; the 48==48 coincidence is recorded, not interpreted.
- dashboard-autostart.sh:23 (13 records in 7d) and user-prompt-submit.sh:24 (132 in 7d) each emit
  exactly one status-less printf and no terminal.
- log-tool-event.sh: attempt :71 under the argv label; beacon() :91-100 writes the terminal under the
  derived key; rotation record :302-308 emits `"status": "rotation"` (:303). Live count of that literal
  in hook-fires.jsonl = 0. [NEW FINDING — absent from revision 1; now D2's fifth repair.]
- Static emitter census: 19 beacon-object emit sites across the 7 registered scripts plus the one .py
  helper they invoke (18 in the .sh files, of which 2 are reject_obj writes to
  workflow-events.rejects.jsonl rather than hook-fires.jsonl, + classify.py:166). Status literals
  emitted: attempt x4, ok x2, ERROR x3, "OK" x1, "rotation" x1, "python3_selftest" x1. Three sites
  carry no status key (pre-tool-bash.sh:104, dashboard-autostart.sh:23, user-prompt-submit.sh:24);
  two carry a runtime variable (log-tool-event.sh:92, session-start.sh:235).
- [REVISION 3 — CALL GRAPHS RESOLVED, the correction to the census METHOD, not just to its result.]
  The two runtime-variable sites are `beacon()` helper bodies with closed, enumerable call graphs.
  Resolved by direct read: log-tool-event.sh `def beacon` :91, called :166 "ok", :315 "ok", :333
  "error"; session-start.sh `def beacon` :234, called :290 "ok", :308 "error". Resolved literal
  census therefore adds ok x3 and error x2 — and lowercase "error" is OUTSIDE D2's closed set.
  Revisions 1 and 2 stopped the census at "runtime variable", which is the same method failure that
  let "rotation" through in revision 1. Live: `grep -oE '"status":"[^"]*"' hook-fires.jsonl | sort |
  uniq -c` -> attempt 15,280 / ok 14,108 / "OK" 7,601 / python3_selftest 102 / error 12 / ERROR 3.
  [#1265 CAVEAT — that is a GREP census, i.e. an approximation. The log holds 5 unparseable lines
  from torn concurrent appends, so text counts and record counts diverge: a parser sees ERROR x1
  (stop-reviewer-gate) where grep above sees x3. The "error" x12 figure IS parser-confirmed (#1264's
  own by-(hook,status) parse). Treat every grep census of this log in this document as approximate,
  and re-derive with a parser any argument that turns on an exact count.]
  All 12 "error" records carry hook label `agent_start` (a log-tool-event derived key) and are
  timestamped 2026-08-01T23:15Z..2026-08-02T01:00Z — OUTSIDE the current 7d window, so in-window
  error_count = 0 at c380bb3, consistent with the quoted live detail carrying no "ERROR beacons:"
  part. session-start.sh:308 has produced ZERO records in the log's entire history.
  The reject_obj writes at log-tool-event.sh:324 and session-start.sh:298 target
  workflow-events.rejects.jsonl, NOT hook-fires.jsonl — they are not beacon records.
- [REVISION 3] health.py error_count: accumulated :2019-2020 on `status in ("ERROR","error")` with NO
  hook-label filter; surfaced as a bare `ERROR beacons: N` detail part at :2049; drives the verdict
  at :2054 (`result = "FAIL" if (drift_hooks or error_count > 0)`). Docstring :1974 states the trigger
  ("ERROR beacons in any window -> FAIL") but names no subject. This is the second, previously
  ungoverned FAIL trigger D3 now disposes of.
- [REVISION 3] discovery.py:313 `elif status == "error"` — LOWERCASE ONLY. It has never counted the
  three uppercase-ERROR emitters (pre-tool-bash.sh:108, pre-tool-edit.sh:105, stop-reviewer-gate.sh:56)
  and after D2's :333/:308 repairs counts none of the five. health.py:2019 accepts both spellings, so
  the repair is counting-neutral THERE and only THERE. Recorded in Propagation.
- health.py: check_hook_integrity :1963-2055 (grouping :2002, counting :2015-2020, empty-window WARN
  :2027-2034, ratio/drift loop :2039-2043, FAIL :2054, return :2055).
  _ROUTE_TABLE :2729-2743 [CORRECTED* — revision 1 said :2729-2745].
  _PROOF_TOKENS :2747-2752, hook-fire entry :2749 [CORRECTED — revision 1 said :2760 and gave the dict
  span as :2747-2760 as an edit anchor].
  _pr_has_proof_token :2774-2782, docstring :2775, loop :2777-2781, re.IGNORECASE search :2780
  [CORRECTED — revision 1 said :2791, which is inside check_blind_dispatch_rate's docstring; and gave
  the loop as :2778-2782].
  check_proof_presence :3000-3076, detail :3070-3073 [CORRECTED* — revision 1 said :3068-3073; :3068 is
  the rate computation], no FAIL branch (`result = "PASS" if not without_proof else "WARN"`) at :3074.
  TELEMETRY-LIVE is built by _build_hook_trio_composite :1705, id literal :1751 [CORRECTED* — revision 1
  cited :6925, which is the purpose-group substitution set _hook_ids, not the composite].
  Purpose-group exclusion comment :1533-1541. discovery import :6265, used :6291.
- discovery.py:311 `if status in ("attempt", "")` — the second, divergent reader of `status`; the
  explanatory comment is :310 and the docstring line is :277 [CORRECTED — revision 1 said :310].
  _auto_mode_derived_keys :353.
- reviewer.md:233 is the broken jq one-liner; R-LOC section :219-238; runtime-artifact list :223-229;
  BLOCK message :236. Fixture reproduction at c380bb3: prints 15 (true total 30) with
  `jq: error (at files.json:6): Cannot index string with string "path"` on stderr.
- gen_rules.py: _RULE_STATEMENTS declared :273, HOK-008 :523-527, _get_rule_statement :823
  [CORRECTED* — revision 1 said :825], RULE_IDS_BASELINE :143 = 86, scope parsed :235 / rule_ids :236 /
  gated :240 [revision 1 said ":236, :240" for the ID declaration — the scope key is :235],
  SCOPE_TARGET :103-118 [revision 1 said :103-119; the dict closes at :118].
  `gen_rules.py --check` -> "CONSERVATION OK: rule_ids total 86 == baseline 86", all outputs clean.
- Per-decision supersession leaves the target untouched: ADR-0040/0007/0067/0034 all still carry
  `superseded_by: []` after ADR-0081 superseded decisions inside them. Verified by reading frontmatter.
- VER ids currently in use: VER-001..VER-008 (no gaps). Next free = VER-009.
- CLAUDE.md:9 live text ends "PIP-001..025" and carries "VER-001..008". CI-check Map row is :132
  [CORRECTED — revision 1 said :133].
- tests/test_loc_cap_1162.py:174 asserts the literal "RULE_IDS_BASELINE: int = 86" [CORRECTED — revision
  1 said :180; the file lost 5 lines at 0753aa7 with the /build assertions].
- ci-checks.sh last check = CHECK 23 (:1070). `grep -ci 'status' tools/ci-checks.sh` = 0.
  health.py --list = 50 rows.
- qa-tester.md :269 (hook-fire route row), :275 (negative-path row), :278 (union statement), :521
  (PROOF field spec), :540 (hook-fire evidence summary) — ALL UNCHANGED on develop; the file's only
  develop-side diff is :1 (description) and :549 (orchestrator name). Verified by diffing f7378de..c380bb3.
- ship/SKILL.md:264 is the hook-fire PROOF line [CORRECTED — revision 1 said :235, its origin/main
  position; the file gained 53 lines net at 0753aa7].
- .claude/skills/ at c380bb3 contains six directories: grill-me, promote-to-backlog, qa-plan, ship,
  to-issues, to-prd. NO build/ [CORRECTED — revision 1 carried a conditional entry for
  build/SKILL.md:156 on the assumption it might still exist].
- settings.json registers 7 hook scripts: dashboard-autostart, log-tool-event, pre-tool-bash,
  pre-tool-edit, session-start, stop-reviewer-gate, user-prompt-submit. Ratio-list labels at c380bb3:
  auto, pre-tool-edit, session-start, session_start, session_stop, skill_invoke, stop-reviewer-gate,
  user_prompt. Registered-minus-labels difference = 4 (dashboard-autostart, log-tool-event,
  pre-tool-bash, user-prompt-submit); post-fix must be exactly 1 (log-tool-event, scored under `auto`).
- Fixture reproductions, all run at c380bb3 with _HEALTH_REPO_ROOT patched to temp trees (rule #21 —
  zero synthetic lines reached .claude/logs/):
    auto fold fixture      -> FAIL, "window=7d | ratios: auto:0/1 | drift: auto(0/1)"
    three-hook shapes      -> PASS, "window=7d | ratios: session_stop:1/1" (none of the three appears)
    40-day-old-only log    -> WARN, "no attempt beacons in last 7d window; dark-detection deferred to
                              HOOK-LIVENESS" — NO ratios: list, NO drift: list. This is the vacuity
                              vector the companion PRD's live-feed precondition closes.
    _pr_has_proof_token('written to .claude/logs/hook-fires.jsonl', [], {'hook-fire'})   -> True
    _pr_has_proof_token('{"hook":"stop-reviewer-gate","status":"ok","ts":"..."}', [], {'hook-fire'}) -> False
    _pr_has_proof_token('ran it, exit=0', [], {'browser','command-run'})                 -> True
- PROOF-PRESENCE re-simulation at c380bb3 over the live window [1249,1247,1245,1243,1230,1223,1222,
  1220,1203,1201]: current tokens + any-union = 9/10; D4(a)+(b) tokens + all-union = 1/10, survivor
  #1201. Seven of the nine losses miss on `browser`, one on `command-run`, one (#1230) on `hook-fire`.
  Identical to revision 1's figure despite the moved window.
-->
