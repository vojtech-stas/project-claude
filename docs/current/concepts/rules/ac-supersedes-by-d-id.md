---
title: AC-SUPERSEDES-BY-D-ID — adr-critic criterion 3, every Supersedes citation is verified to exist and substance-match
summary: The adr-critic rule that every `Supersedes:` header entry must cite a D-ID that (a) exists in the cited ADR and (b) says what the draft claims it says; also gates the referenced-but-missing ADR sub-check.
tags: [rule, adr-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md criterion 3
  - decisions/0003-autonomous-pipeline-with-critics.md (historical defect — wrong D-ID cited)
  - decisions/0004-bypass-prevention.md D5a (correction)
---

# AC-SUPERSEDES-BY-D-ID

**AC-SUPERSEDES-BY-D-ID** is criterion 3 in the [`adr-critic`](../../../.claude/agents/adr-critic.md) rubric. For every `Supersedes:` (or equivalent) header entry on the draft, the cited D-ID must:

- **(a) Exist** in the cited ADR — open the file and verify the D-ID appears.
- **(b) Say what the draft claims it says** — open the file and verify the substance matches the draft's summary.

This is the specific check that catches **ADR-0003's historical defect**: ADR-0003's header read "Supersedes: ADR-0001 D3 (PRDs as repo files)" but ADR-0001 D3 is actually "Visibility: public on GitHub". The wrong D-ID was cited; ADR-0004 D5a corrected it post-merge. AC-SUPERSEDES-BY-D-ID catches this class of error at draft time, eliminating the corrective-ADR round-trip.

## What

The rule fires on every `Supersedes:`-bearing draft ADR AND on every ADR-NNNN reference in any section. Mechanics:

- **Main check (D-ID verification):** for each `Supersedes: ADR-NNNN D-X` entry, `Read decisions/NNNN-*.md` and locate the cited D-ID. If absent → FAIL with `"supersession-miscite: <ADR-NNNN D-X> does not exist in <ADR-NNNN>"`. If present but substance mismatched → FAIL with `"supersession-miscite: <ADR-NNNN D-X> exists but is about '<actual>', not '<claimed>' as the draft asserts"`.
- **Sub-check (referenced-but-missing):** if the draft references `ADR-XXXX` anywhere (Supersedes, Extends, Context, Decisions, Alternatives, References) and `decisions/XXXX-*.md` is absent → FAIL with the literal message `"ADR-XXXX referenced but not present"` (substituting the actual number). Mirrors `prd-critic`'s analogous sub-check exactly.

**Stale-worktree mitigation.** ALWAYS use `gh api repos/{owner}/{repo}/contents/decisions/<file>.md` to check ADR file existence on origin/main, NOT local `ls decisions/`. The worktree's local `decisions/` may be stale (a common stale-worktree false-alarm pattern observed 3+ times 2026-05-20/21). Only trust `gh api` results.

## Why

This rule exists because a wrong D-ID cited in a `Supersedes:` header **silently rewrites history**. Future readers trust supersession headers as authoritative; an inaccurate header means a decision was either un-superseded (the cited D-ID doesn't say what the draft claims) or over-superseded (the wrong D-ID was named, leaving the actually-overridden D-ID still on the record).

The historical defect is the standing example: ADR-0003 claimed to supersede ADR-0001 D3 ("PRDs as repo files") but D3 was actually "Visibility: public on GitHub". The substantive override of ADR-0001 D6 went undeclared; the supposed override of D3 was meaningless. The defect persisted until ADR-0004 D5a fixed it as a corrective ADR. Cost: one extra ADR plus the audit-trail noise. AC-SUPERSEDES-BY-D-ID closes the defect at draft time.

The referenced-but-missing sub-check exists for the same reason as `prd-critic`'s analogous sub-check: auto-creating a missing ADR is a side-effect outside the critic's read-only contract; surfacing the dangling reference is the cheaper failure mode — the generator either drafts the missing ADR or fixes the reference.

## How to check

For each draft ADR:

1. Parse all `Supersedes:` / `Extends:` header entries; extract each `ADR-NNNN D-X`.
2. For each, `Read decisions/NNNN-*.md` and locate D-X verbatim.
3. If absent → FAIL with the literal "supersession-miscite" message naming the missing D-ID.
4. If present, compare the draft's summary of D-X against the file's D-X body. If substance mismatched → FAIL with the literal "supersession-miscite: ... exists but is about" message.
5. **Sub-check:** parse all sections for `ADR-XXXX` regex matches; for each, `gh api repos/{owner}/{repo}/contents/decisions/XXXX-*.md` to verify existence on origin/main. If missing → FAIL with `"ADR-XXXX referenced but not present"`.

## Examples

- **Draft header `Supersedes: ADR-0001 D3 (PRDs as repo files)`; ADR-0001 D3 is actually "Visibility: public on GitHub"** → FAIL (supersession-miscite: substance mismatch — the historical defect).
- **Draft header `Supersedes: ADR-0005 D99`; ADR-0005 only has D1-D4** → FAIL (supersession-miscite: D99 does not exist).
- **Draft Context cites `ADR-0099`; `decisions/0099-*.md` does not exist on origin/main** → FAIL (referenced-but-missing sub-check).
- **Draft header `Supersedes: ADR-0006 D4`; ADR-0006 D4 substance matches the draft's summary** → PASS.

## Edges

- **part_of:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/rules/ac-cross-adr-consistency]]
- **related_to:** [[concepts/rules/ac-immutability-respected]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/supersession]]
