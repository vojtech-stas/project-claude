# 0064 — Rule-layer integrity: supersession propagation, one rubric implementation, ask-first enforcement paths

- **Status:** Accepted (joint APPROVE per ADR-0004 D1; shipped with PRD #794 slice 1)
- **Date:** 2026-06-12
- **Extends:** ADR-0048 D2 (complete-class revision discipline / rule #19 — extended from revision-time to supersession-time); ADR-0045 D1 (rule #18's consult-before-cite at WRITE time — this ADR covers what happens when the cited decision later DIES); ADR-0017 D2 and D3 (the structure-audit and docs-currency rubrics — their implementations become single-sourced)

## Context

The rule layer rots through two measured channels. First, supersession without propagation: rule #18 (ADR-0045 D1) polices citations at write time, and rule #19 (ADR-0048 D2) sweeps defect classes at revision time — but when an ADR decision is superseded, nothing sweeps the prompts and docs that cite it: the retired 6-critic cap was cited as live authority in 6 files (#734), and DOCS-8 WARNs about missing supersession annotations sat unactioned (#599). Second, rubric triplication: the audit rubric exists as SKILL.md prose, `dashboard/health.py` code, AND `tools/ci-checks.sh` greps — and they drifted until 6 of 8 Health-tab FAILs were false positives (#728, #614, #625), the skill defined 11 checks while the dashboard implemented a different 10, and a fake-slug allowlist existed in two verbatim copies (#701's constant class is the same disease). Separately, the audit proved the enforcement layer itself can be silently modified through normal review: the stop-gate that ignored its own loop guard shipped unnoticed (#726's class) — nothing distinguishes PRs that change the policing machinery from PRs the machinery polices.

## Decisions

### D1 — Supersession propagation: the Propagation section + AC-PROPAGATION

A superseding ADR MUST carry a `## Propagation` section enumerating every tracked file that cites the superseded D-IDs (mechanical grep at drafting time) with a per-file disposition: update-in-this-wave or grandfather-with-reason. `adr-critic` gains rubric rule AC-PROPAGATION: a draft whose Supersedes header names D-IDs but whose Propagation section misses grep hits is BLOCKed. Per ADR-0004 D2 (bootstrap-mode), binds forward from the adr-critic prompt-update merge; previously-accepted ADRs are not retroactively re-gated (the D2 check owns the steady state).

### D2 — DOCS-11: the standing dead-citation check

A new docs-currency check (DOCS-11, implemented in the D3 library): zero citations in `.claude/` runtime prompts of ADR decisions whose ADR carries Superseded status in `decisions/README.md`, unless the citing line also names the superseding ADR or appears in the documented grandfather allowlist. The check reports current offenders honestly from day one (seeding the allowlist with dispositioned legacy hits is the first implementing slice's job). Per ADR-0004 D2, binds forward; the allowlist IS the grandfather mechanism.

### D3 — One rubric implementation: health.py as the check registry

All grep-class doc/structure checks (DOCS-*, AS-*) are implemented exactly once, in `dashboard/health.py`, exposed through a CLI entry (`python dashboard/health.py --check <id>` / `--list`) usable headlessly. `tools/ci-checks.sh` and the audit skills become thin consumers: CI checks that duplicate registry checks are DELETED in favor of registry calls; `audit-meta`/`audit-subagents` SKILL.md documents intent and points at the registry instead of restating mechanics. A parity check (registry IDs == skill-declared IDs == CI-consumed IDs) becomes a standing health row so the triplication class cannot regrow silently. Per ADR-0004 D2, binds forward from the registry slice's merge; check semantics are preserved during migration (verdict-identical for unchanged checks).

### D4 — R-SENSITIVE: ask-first paths over the enforcement layer (deferred activation)

PRs touching the declared enforcement-layer path set — `.github/workflows/**`, `.claude/settings.json`, `.claude/hooks/**`, `tools/ci-checks.sh`, `.githooks/**` — require an explicit human acknowledgment (a `human-ack` label or an owner comment on the PR) before reviewer APPROVE: agents must not silently modify the machinery that polices them. Reviewer rule R-SENSITIVE enforces; a dashboard violation count (merged enforcement-path PRs without ack) is the standing detector. **Activation is deferred**: per ADR-0004 D2 the rule text and detector ship now, but R-SENSITIVE begins BLOCKING only after the workflow-v2 wave-4 closing slice merges (recorded activation point) — the v2 program itself must modify these paths under its critic-gated ADR obligations, and a mid-program gate would deadlock the autonomous run that ships it. Until activation the detector reports advisory counts.

## Consequences

- Decision death propagates instead of rotting; the rubric has one implementation and a parity alarm; the enforcement layer gains a human tripwire with an honest activation point.
- adr-critic drafting cost rises slightly (Propagation greps); ci-checks.sh shrinks (deleted duplicates).

### Enforcement (rule #23)

Deterministic, per decision: D1 — AC-PROPAGATION (adr-critic rubric; observable in verdicts); D2 — the DOCS-11 registry check (dashboard row + CI-consumable); D3 — the parity health row (registry/skill/CI ID-set equality); D4 — the enforcement-path violation count row + R-SENSITIVE in the reviewer rubric. Parsimony — mechanisms considered: rule #18/ADR-0045 covers write-time only (verified: its D1 is "never cite from memory" — nothing fires at supersession time); rule #19/ADR-0048 D2 sweeps at critic-BLOCK revision time only; DOCS-8 checks index annotations, not citing prompts; the existing CHECK 4/5+health duplication IS the disease D3 removes — no existing mechanism owns any of the four concerns; all four land inside existing surfaces (adr-critic rubric, health registry, reviewer rubric) with no new agent. Shadow: dead decisions cited as law; rubric forks; silently self-modified gates.

## Alternatives considered

- **Periodic manual supersession audits:** rejected — the audit that found #734 was a one-off 70-agent sweep; a standing check is cheaper than re-running it.
- **Single-sourcing into ci-checks.sh instead of health.py:** rejected — the dashboard needs structured per-check results for rows; bash exits lose granularity; python already implements the richest versions.
- **Immediate R-SENSITIVE activation:** rejected — would deadlock the autonomous v2 program mid-flight; deferred activation with an advisory detector is honest about the window.
- **Branch-protection path rules instead of R-SENSITIVE:** rejected — unavailable granularity on this plan; the reviewer rule + detector deliver the same property observably.

## References

- ADR-0048 D2 (rule #19), ADR-0045 D1 (rule #18), ADR-0017 D2/D3 (rubric origins), ADR-0042 D1 (the CI gate consuming the registry), ADR-0004 D2 (bootstrap-mode), issues #728 #734 #614 #625 #599 #701 #726, workflow-v2 synthesis §B7/§C8 (2026-06-12).
- Numbering note: this draft is co-submitted with the upstream-spec-contract ADR (two numbers above it) in this wave's joint gate; both ship together in slice 1 per ADR-0003 D8. The number between them is reserved for the prompt-schema-v2 draft, which hit a round-3 strict-stop in the same gate and is escalated via needs-human #793 — an intentional, documented gap pending human adjudication, mirroring the ADR-0021 precedent recorded in decisions/README.md.
