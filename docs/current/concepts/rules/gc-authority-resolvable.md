---
title: GC-AUTHORITY-RESOLVABLE — glossary-critic rule 4, authority field present and well-formed
summary: The glossary-critic rule that the authority field is non-empty and matches one of three accepted shapes — `ADR-NNNN D-X` (with the ADR file existing and the D-ID present), a URL (syntax-validated only), or the literal string `external`; missing, malformed, or dangling authority FAILs the rule.
tags: [rule, glossary-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/glossary-critic.md rule 4 (authority field)
  - decisions/0007-vocabulary-glossary-and-grill-me-extension.md D2
---

# GC-AUTHORITY-RESOLVABLE

**GC-AUTHORITY-RESOLVABLE** is rule 4 in the [`glossary-critic`](../../../.claude/agents/glossary-critic.md) rubric. It enforces that every draft entry's authority field is non-empty and matches one of three accepted shapes per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2:

- `ADR-NNNN D-X` — a project decision (e.g., `ADR-0003 D1`). The ADR file must exist on origin/main AND the D-ID must be locatable inside it.
- A URL — an external named source. Syntax-validated only; the critic does NOT fetch.
- The literal string `external` — industry-standard term with no project-specific authority worth pinning.

Missing, malformed, or dangling authority FAILs the rule.

## What

The rule fires on every draft entry's authority field. Mechanics:

- Locate the `*Authority:*` field. If empty/missing → FAIL with `"authority: required field missing per ADR-0007 D2"`.
- Classify by shape:
  - **`ADR-NNNN D-X`**: verify the file `decisions/NNNN-*.md` exists AND open it and locate the D-ID heading or marker. If file absent → FAIL with `"authority: <ADR-NNNN D-X> ADR file not found"`. If file present but D-ID not present → FAIL with `"authority: <ADR-NNNN D-X> does not exist in <ADR-NNNN>"`.
  - **URL**: verify URL syntax (scheme + host). No HTTP fetch. If malformed → FAIL with `"authority: URL '<X>' is malformed"`.
  - **`external`**: literal match only. Anything else with the word `external` embedded in a sentence does NOT count.
- Any other free-form string (e.g., "see Gojko's book", "the docs", "obvious") → FAIL with `"authority: '<X>' is not a recognized shape (ADR-NNNN D-X | URL | external)"`.

**Stale-worktree mitigation:** for `ADR-NNNN D-X` shape, use `gh api repos/{owner}/{repo}/contents/decisions/<file>.md` to verify file existence on origin/main when local worktree may be stale (mirrors the prd-critic `pc-adr-consistency` sub-check pattern; common stale-worktree false-alarm class).

## Why

The authority field is the **anchor that prevents the glossary from drifting into folk-etymology**. Every entry must point to a primary source — a project ADR for jargon and narrowed terms, an external spec for adopted standards, or an explicit `external` declaration for genuinely-standard background terms.

Without authority enforcement, entries silently re-define terms with the author's recollection ("a slice is... whatever I think it is today"). With authority enforcement, every entry has a traceable bedrock — the reader can open the linked ADR and read the source-of-truth.

The "no fetch" carve-out for URLs is a deliberate trade-off: external URL rot is not the critic's problem to solve (would require WebFetch tool grant + introduces flakiness). The author owns external-link freshness; the critic enforces shape only.

The "does not exist in" sub-check for `ADR-NNNN D-X` exists because dangling D-IDs are the most common authority failure mode — the author cites `ADR-0007 D9` from memory when the actual section is `D8`. The critic catches this mechanically.

## How to check

For each draft entry:

1. Locate the `*Authority:*` field. Absent → FAIL.
2. Classify shape (ADR / URL / `external` / other).
3. If ADR: `gh api` (or `Read`) the named file; grep for the D-ID heading. Either missing → FAIL with the specific message.
4. If URL: regex-validate (`^https?://[^\s]+$`). Malformed → FAIL.
5. If `external`: must be literal; trailing/leading whitespace OK.
6. Any other shape → FAIL.

## Examples

- **`*Authority:* ADR-0003 D1`** → PASS (file `decisions/0003-autonomous-pipeline-with-critics.md` exists; D1 heading present).
- **`*Authority:* ADR-0007 D9`** → FAIL (ADR-0007 only has D1-D8 on origin/main).
- **`*Authority:* https://www.conventionalcommits.org/en/v1.0.0/`** → PASS (URL syntax valid; no fetch).
- **`*Authority:* external`** → PASS (literal match for industry-standard term).
- **`*Authority:* see Gojko's book`** → FAIL (not a recognized shape; the author should cite a URL or `external`).
- **Field missing entirely** → FAIL.

## Edges

- **part_of:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/rules/gc-canonical-shape]]
- **related_to:** [[concepts/rules/gc-citation-threshold]]
- **related_to:** [[concepts/rules/pc-adr-consistency]]
