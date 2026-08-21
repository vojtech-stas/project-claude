# 2026-08-21 — cut-promotion (D9)

**Context.** PRD #1214 (frontend cut: run-board becomes the dashboard; batch-plan retired, ADR-0080) closed with `PRODUCTION_VERIFY: PASS`. develop `c54a92ed` stood 6 PRs ahead of main `4988c7a` — the cut (PRs #1220/#1223/#1222), both decision-log records (#1210/#1213), and the PIP-022 currency fix (#1227). Guardrail paths in the batch (tools/ci-checks.sh, ship/reviewer prompts) required the operator promotion ack.

**Decision D9 — promotion ack (was P5 on the Decision Inbox):**

- [x] Promote now — **chosen** (operator checkpoint 2026-08-21; recommendation followed)
- [ ] Hold — work continues on develop; deploy gap stays open

**Outcome.** Executed 2026-08-21: `.claude/PROMOTE_OK` ack sentinel → RELEASE-READY PASS from a develop worktree → `tools/promote.sh` → main = `c54a92ed` (5th recorded promotion span, ts=2026-08-21T20:23:22Z) → root ff-synced, deploy-handshake OK. The reduced dashboard, CHECK 23 verdict-presence gate, and both decision logs now run on the root system.

**Pointers.** Card label `2026-08-21-inbox-cut-promotion` (Decision Inbox); ADR-0080; PRD #1214; promotion span sha `c54a92ed9cab3e87b2badf9f2d256f664469680f`.
