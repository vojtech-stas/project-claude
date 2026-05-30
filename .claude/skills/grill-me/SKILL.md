---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

## How to ask each question (clickable options)

Use the **AskUserQuestion** tool for every decision point so the options are clickable. For each question:

1. **Number the question** — put `Q<n> — <topic>` in the `header` (e.g., `Q3 — Auth method`). Keep numbering stable so I can refer to a choice as `<question><option>` shorthand (e.g., "3B", "4C").
2. **Give 2–4 options, sorted BEST → LEAST-preferable** (most-recommended option first). The tool labels them A/B/C/D in order.
3. **Mark the top option `(Recommended)`** in its `label`.
4. **Each option's `description` states its PRO and its CON** (and the key trade-off vs the alternatives) so I can compare at a glance — not just what the option is.
5. Resolve one decision (or a small batch of tightly-related decisions) per `AskUserQuestion` call; walk the dependency tree so my earlier answers constrain the later questions.
6. Always include your own recommendation and the reasoning; if a question can be answered by exploring the codebase, explore the codebase instead of asking.

## Optional doc-path argument (per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D6)

`/grill-me <path>` reads `<path>` before asking Q1. Use this when the grill is about an existing spec, PRD, or external doc that should anchor the questions. Single optional local path only — not multi-doc, not config-file, not URL.

- If `<path>` exists and is a readable file → `Read` it in full before Q1; reference its content throughout the grill.
- If `<path>` does not exist or is not readable → report the error in one line (`"path '<X>' not found — proceeding in no-arg mode"`) and continue with the no-arg flow. Do NOT abort.
- If no argument is supplied → existing no-arg behavior is unchanged (full backward compatibility per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D6).

## Glossary read mechanism (per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D1)

Project vocabulary lives in two tiers:

- **Key-zone** — the `## Glossary (key terms)` section inside `CLAUDE.md`. **Auto-loaded** by the runtime on every session; you already have it when the grill starts. Use these terms with their project-narrowed meanings without re-deriving them.
- **Long-tail** — `GLOSSARY.md` at repo root. **Read on-demand:** when an unfamiliar term comes up during the grill (yours or the user's), `Read GLOSSARY.md` and check before asking a clarifying question that the glossary already answers. If the term is missing from both tiers and looks glossary-worthy per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3 (categories a/b/c), inline a one-line suggestion: *"Heads up: '<X>' looks glossary-worthy — run `/glossary-add` to capture."* This surfacing is discretionary per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4, mirroring [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4's backlog surfacing pattern.

**End-of-session captured-tier sweep.** Per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2 (originating from [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4 write-convention pattern), at the end of each grill session, the agent MUST review items that surfaced but were deferred (out of scope, "we should also do X", deferred per ADR Future-direction, etc.) and create a `captured`-labeled GitHub Issue for each, then immediately invoke `/promote-to-backlog <N>` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 inline-firing convention so the autopilot's `backlog-critic` triages the item. Use `gh issue create --label captured --title "..." --body "..."`. The body briefly captures the item, the grill context where it surfaced, and optionally a link to the motivating ADR section.
