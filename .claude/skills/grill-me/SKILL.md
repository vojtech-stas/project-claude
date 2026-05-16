---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Optional doc-path argument (per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D6)

`/grill-me <path>` reads `<path>` before asking Q1. Use this when the grill is about an existing spec, PRD, or external doc that should anchor the questions. Single optional local path only — not multi-doc, not config-file, not URL.

- If `<path>` exists and is a readable file → `Read` it in full before Q1; reference its content throughout the grill.
- If `<path>` does not exist or is not readable → report the error in one line (`"path '<X>' not found — proceeding in no-arg mode"`) and continue with the no-arg flow. Do NOT abort.
- If no argument is supplied → existing no-arg behavior is unchanged (full backward compatibility per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D6).

## Glossary read mechanism (per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D1)

Project vocabulary lives in two tiers:

- **Key-zone** — the `## Glossary (key terms)` section inside `CLAUDE.md`. **Auto-loaded** by the runtime on every session; you already have it when the grill starts. Use these terms with their project-narrowed meanings without re-deriving them.
- **Long-tail** — `GLOSSARY.md` at repo root. **Read on-demand:** when an unfamiliar term comes up during the grill (yours or the user's), `Read GLOSSARY.md` and check before asking a clarifying question that the glossary already answers. If the term is missing from both tiers and looks glossary-worthy per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3 (categories a/b/c), inline a one-line suggestion: *"Heads up: '<X>' looks glossary-worthy — run `/glossary-add` to capture."* This surfacing is discretionary per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4, mirroring [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4's backlog surfacing pattern.

**End-of-session backlog sweep.** Per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4, at the end of each grill session, review items that surfaced but were deferred (out of scope, "we should also do X", deferred per ADR Future-direction, etc.) and create a `backlog`-labeled GitHub Issue for each. Use `gh issue create --label backlog --title "..." --body "..."`. The body briefly captures the item, the grill context where it surfaced, and optionally a link to the motivating ADR section.
