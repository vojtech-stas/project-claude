---
name: grill-me
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Use when user wants to stress-test a plan, get grilled on their design, or mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

**End-of-session backlog sweep.** Per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4, at the end of each grill session, review items that surfaced but were deferred (out of scope, "we should also do X", deferred per ADR Future-direction, etc.) and create a `backlog`-labeled GitHub Issue for each. Use `gh issue create --label backlog --title "..." --body "..."`. The body briefly captures the item, the grill context where it surfaced, and optionally a link to the motivating ADR section.
