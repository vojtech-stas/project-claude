# 2026-08-21 — decide skill (renamed from human-qa)

Operator decisions from the decision-inbox v1 card (checkpoint pasted 2026-08-21). Convention bootstrap:
this file is the first entry of docs/decision-log/ — operator decisions recorded in git per N4 below,
one dated file per problem, chosen options ticked, append-only (a reopened decision gets a new dated
file citing this one, ADR-style).

- [x] N1: skill name = `decide` — batch review becomes one decision type, not the headline
- [x] N2: fires ALWAYS — every decision owed to the operator lands on the card; chat answers stay valid.
      Boundary: prefillable options → /decide; open design space → /grill-me
- [x] N3: hybrid card model — standing Decision Inbox (stable URL) + per-problem cards named by the
      problem; labels `<problem-slug>-v<N>`; knowledgebase-grade history
- [x] N4: pipeline decision points feed the inbox; decided outcomes captured in git via this log
      (trivial/docs lane in this repo per rule #10)

Pointers: card label decision-inbox-v1; skill file `~/.claude/skills/decide/SKILL.md` (personal, untracked);
related repo surfaces: promotion acks (PROMOTE_OK flow), I5 escalations (`needs-human`), QA residuals.
