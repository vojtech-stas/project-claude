# 2026-09-02 — queue-drain mode (whole-queue autonomous runs on /ship)

**Context.** The operator returned from a quota pause to a large open queue and a standing goal: fix or close every open issue before tagging v1.0.0. The pipeline could already run one grilled feature to done, and `/ship`'s Conduct section even claimed "ship everything in the backlog" run-to-done semantics — but nothing defined how a whole-queue run actually works. Six things were undefined: how the queue assembles, which items genuinely need the operator, what happens when one does, how the run survives a quota cut, how much runs at once, and where small fixes discovered mid-run land. The operator named the last one explicitly: *"when we figure out some small fix we push it to issue and not solve it afterwards"* — the pipeline was manufacturing backlog out of its own findings. The grill settled all six forks; they are recorded below and encoded in [ADR-0085](../../decisions/0085-queue-drain-mode.md).

## Triage-cluster grounding

The drainability claim is not an assumption — it came from triaging the full open queue before designing anything. Two snapshots, both measured, neither load-bearing (the mode re-counts live at every run start and records the count in its own `run_start` record):

| Snapshot | total open | `prd` | `slice` | `backlog` | `captured` | open non-draft PRs |
|---|---|---|---|---|---|---|
| PRD post time | 172 | 1 | 4 | 67 | 100 | 1 |
| Slice-1 landing | 177 | 2 | 6 | 72 | 96 | 1 |

(Per-label counts do not sum to the total: labels are neither exhaustive nor mutually exclusive, and the drift between rows is mostly this PRD's own artifacts.)

The triage clustered every open item into three buckets, and the shape of that result is what made an autonomous mode worth building at all:

| Cluster | Size | Why it lands there | How the drain routes it |
|---|---|---|---|
| **Autonomous** | the overwhelming majority | a reasonable senior engineer would not need to ask before doing it | straight through the existing pipeline, unattended |
| **Operator-owed** | ~2 genuine design forks | a real fork where a wrong guess costs rework | labelled `needs-human-check`, recorded, **run continues** |
| **Class-ack** | 1 bulk-close class | one coherent class of obsolete items, not N decisions | ONE class-level ack; never closed unilaterally |

The missing piece was therefore orchestration contract, not capability — which is why no new skill, subagent or critic was created.

## Decisions

**Q1 — Where does the whole-queue run live?**

- [x] An **entry mode on `/ship`** — **chosen**. `/ship` is already the single lifecycle orchestrator, and the last time a second conductor existed it produced drift serious enough to retire it. Every step a drain needs already lives in `/ship`.
- [ ] A new dedicated drain/goal orchestrator skill — rejected: recreates exactly that two-orchestrator drift.

**Q2 — Where is the autonomy boundary?**

- [x] The **reasonable-engineer litmus** — *would a reasonable senior engineer need to ask the owner before doing this?* — resolved per item into three buckets, with the classification recorded in the ledger — **chosen**. The boundary is a judgment, so the checkable obligation is the *recording*, not the verdict.
- [ ] An enumerated list of item types that always escalate — rejected: the list would be wrong at the edges and stale within a wave.

**Q3 — What happens when an item does need the operator?**

- [x] **Label-and-continue on a two-label split** — **chosen**. Triage-time escalations get `needs-human-check` (the existing non-blocking residual queue); the strict-stop label `needs-human` is reserved for round-3 critic BLOCKs. The run never waits for an answer.
- [ ] Stop and ask — rejected: kills run-to-done and reintroduces the blocking human gate the pipeline was built to remove.
- [ ] One label for both — rejected on a mechanical consequence discovered during the grill: the release gate counts open `needs-human` items, so parking ordinary design forks there would freeze promotion for the entire drain and until every fork was answered — the exact opposite of the goal.

**Q4 — How does a run survive being killed?**

- [x] A **durable run ledger**, one append-only JSONL per run at the shared repo root, with a closed record-kind set — **chosen**. A park writes the remaining items in resume order; a resumed session reads the ledger instead of reconstructing intent from memory.
- [ ] New kinds on the existing pipeline span ledger — rejected: that ledger's closed enum and its reader contract exist to keep it small and trustworthy, and keeping it free of drain records is precisely what lets it serve as the *independent* witness that a plan-only run dispatched nothing.

**Q5 — How much runs at once?**

- [x] **File-overlap lanes with a concurrency cap of 3**, unknown overlap serializing — **chosen** (operator's initial setting: a modest cap). Motivated by observed platform rate-limiting and by review quality degrading when too much is in flight. The cap is enforced deterministically from the ledger, and revisited on evidence rather than taste.
- [ ] Unbounded parallelism — rejected on both grounds above.
- [ ] A static file-overlap analyzer — rejected as a rabbit-hole: the prediction is coarse by design, and a wrong guess costs a merge conflict caught at the PR gate.

**Q6 — Where do small fixes discovered mid-run land?**

- [x] **Fix-in-run** — a discovery that fits the trivial lane is appended to the *current* run and lands as its own hotfix PR before the run ends — **chosen**, answering the operator's complaint directly. If it does not land, it is captured then, and the ledger must reference that capture before the run's terminal record; the check FAILs otherwise, so nothing is silently lost.
- [ ] File it and defer, as before — rejected: this is the behaviour that turned findings into queue.

**Outcome.** Encoded as ADR-0085 (six decisions, rules PIP-026..PIP-029), with the mode's prose in the `/ship` skill and its enforcement in a health-registry row plus a CI check. What is deliberately *not* settled here, and is tagged advisory in the ADR with an evidence trigger apiece: triage-classification correctness, the cap's specific value, mutation pacing, and how a run detects that a quota cut is coming — no interface exposes that last one, so the checkable obligation is the park record, not the prediction.

**Pointers.** [ADR-0085](../../decisions/0085-queue-drain-mode.md); PRD #1326; slice #1329. Deferred siblings: headless/scheduled drain runs (#1320), mutation pacing evidence (#1073), ledger retention.
