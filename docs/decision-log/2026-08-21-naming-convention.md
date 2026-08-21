# 2026-08-21 — naming-convention (decide-skill artifacts)

**Context.** The decide-skill's artifact publish labels used bare version counters (`decision-inbox-v4`). The operator rejected them: a counter says nothing about content, and the v4 card itself carried a stale hardcoded `v2` composer header — a bug the convention invited.

**Decision — one naming rule everywhere:**

- [x] `<yyyy-mm-dd>-<slug>` labels (date = chronology, slug = content) + ONE global never-reused `D<n>` decision-id sequence shown with its slug — **chosen** (operator: "figure out a better convention"; delegated, applied same day)
- [ ] Keep per-batch letter prefixes and `-v<N>` counters

**Outcome.** Encoded in the decide skill 2026-08-21. Inbox labels: `<date>-inbox-<headline-slug>` or `<date>-inbox-clear`; per-problem cards `<date>-<problem-slug>`; same-day revision appends `-2`. Grandfathered ids: N1–N4 = D1–D4, P1–P5 = D5–D9; next id D10. Checkpoint headers carry the date; answers parse by globally-unique id, so a stale header cannot misroute (proven same day: a "v2" header on the v4 card applied cleanly). Decision-log filenames already followed `<yyyy-mm-dd>-<slug>` — labels now share the same DNA.

**Pointers.** decide skill (personal, `~/.claude/skills/decide/`); Decision Inbox card; prior records `2026-08-21-decide-skill.md`, `2026-08-21-operations-batch.md`.
