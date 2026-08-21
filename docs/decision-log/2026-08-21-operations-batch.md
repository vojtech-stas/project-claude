# 2026-08-21 — operations batch (decision-inbox v2)

Operator checkpoint answered 2026-08-21; all four executed the same day.

- [x] P1: Promote now — EXECUTED: main 97adce8 → 4988c7a (4th recorded promotion span,
      2026-08-21T12:10:08Z), root ff-synced, deploy-handshake OK; deploys PRs #1190 #1191
      #1200 #1201 #1203 (record-green sha attribution, identity liveness probes, ADR-0079
      evidence chain, deny-guard single-spawn + outcome beacons, session-start concurrency)
- [x] P2: PRD-B residuals → option B — MERGED-WITHOUT-VERDICT wired into CI in the same PRD
      (criterion 3c); escalation #1196 closed; drafts re-entered a fresh joint gate
- [x] P3: repo auto-merge ENABLED (allow_auto_merge=true via gh api); #1146 closed resolved
- [x] P4: F:/sreality squatter on 8765 stays; #1204 (probe consolidation) prioritized next

Pointers: card label decision-inbox-v2; promotion span sha=4988c7a in trace-v3.jsonl;
issue comments on #1196/#1146/#1204 carry the per-decision acts.
