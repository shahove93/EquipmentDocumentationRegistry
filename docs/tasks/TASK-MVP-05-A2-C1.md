# TASK-MVP-05 A2/C1 — frozen approach addendum

Authority MVP05_C3_A2_AUTHORIZED_20261026. R1, same Run run_68046cea3eb4, main/current D:/Antigravity/EquipmentDocumentationRegistry, HEAD/baseline318e6336737ee635abf593c2643f26daba273f86. C3 RCA docs/workflow/evidence/TASK-MVP-05-A1-C3-RCA.md completed read-only. A1 FAIL/FAIL/review2/2 unchanged, no third review.
Actual baseline28965861 input/calls8; next Luna accounting call9, Sol call10. Usage accounting only: NO caps/reserves/checkpoint asks/pauses. Stop actual provider refusal/limit or explicit user stop; no reset-credit/account/plan/session bypass.

## Ownership and scope
One Codex gpt-6-luna medium implementer; coordinator workflow-only. After matching worker_done and evidence separate gpt-6.1-sol medium reviewer A2 review1/2. A2/C1 FAIL=>STOP, no automatic C2/A3/fixes/diagnosis. No next TASK/stage acceptance. Worker no commit; coordinator local commit only routed PASS. No push/merge/deploy.
Frozen original TASK-MVP-05.md AC001..007 and TASK-MVP-05-C2.md F01..F04 unchanged. Read original scope/allowlist/AC and C1/C2 findings only, ignore obsolete caps/history holds. Preserve all current partial product code/old artifacts; no broad repo reads/redesign.
Product allowlist: frontend/src/api/batches.ts, pages/BatchesPage.tsx, components/BatchForm.tsx, optional hooks/useBatches.ts; Batch-only types/api.ts, App.tsx, components/Nav.tsx, styles.css, vite.config.ts; optional frontend/README.md/docs/PROJECT_STATUS.md. No app/tests/alembic/API/DB/deps/env/storage/auth/Document links changes.
New harness/logs/screenshots/reports docs/workflow/evidence/TASK-MVP-05-A2-* only. Do not edit old C1/C2 fixtures/evidence/hashes. Preserve unrelated work/user-owned listeners/terminals; use fresh unused isolated ports, don't kill them.

## Materially distinct evidence method
Replace permissive mock/alias recorder with contract-enforcing isolated fixture, immutable serialized wire oracle separate from mutable store, and one verified coherent browser CRUD trace. Prefer actual BatchCreate/BatchUpdate validators in WSL .venv without DB access; otherwise exact bounded validator implementation with source provenance. Quantity finite positive Decimal<=99999999.99, scale<=2, null allowed; preserve exact strings without float. POST/PATCH invalid Quantity rejected without mutation.
Record actual request and response serialized snapshots/status at send time. Decoded snapshots must not alias mutable rows. Show initial snapshots stay identical after edit/clear. This is the repaired evidence method, not new product AC.

## Frozen observable checklist carry-forward
- AC001: Batch navigation/direct URL/reload and actual SPA HTML/API JSON URL/status/content-type.
- AC002: all6 fields/null/date/quantity, list/detail, limit/offset/end, loading/empty/error/retry.
- AC003: existing variant POST201 with nonnull future ISO date and valid exact Decimal string e.g.12345.67; subsequent GET same record; invalid input not success, pending guard.
- AC004: separate PATCH requisite change, then separate nullable null clear; omitted fields preserved, variant required; no uniqueness/PUT/DELETE.
- AC005: no float, independent quantity/unit/futuredate, safe404/422/network, delayed POST/PATCH/unmount/selection/form no stale overwrite.
- AC006/F01: real browser list→detail→create→detail GET→separate edit→clear null→explicit detail GET AFTER clear, SAME created ID. Full immutable request/response/status each step, valid quantity/date and preserved other fields after clear. Don't stitch different records. Actual browser actions through installed Orca browser help; MOCK labelled, no DB writes.
- F02/F03 closed A1/C2: reuse relevant original bounded evidence when affected product files unchanged and hashes match. If changed, collect only necessary relevant new evidence. Keep delayed callback, refresh/html/error/retry/pagination proof.
- AC007/F04: final scope diff and identities; reuse complete C2 typecheck/build0 when product code unchanged with hash proof. If changed run final WSL typecheck/build once. One new relevant targeted mock/browser smoke for replacement harness/full trace; no backend tests/deps.
- Bounded invalid Quantity rejection and immutable snapshot assertions prove repaired oracle, not new backend tests/features. Log actual failures honestly.
- Report/logs FIRST, final A2 hash manifest LAST; exclude manifest itself and never change hashed files afterward.

## Commands, outputs and lifecycle
Windows repo CWD; if product changed final checks:
wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'
wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'
Use WSL .venv/bin/python for schema-based fixture if practical, no installs. git diff/check/status scope evidence, no backend pytest. Reuse complete checks, no unnecessary reruns.
Report docs/workflow/evidence/TASK-MVP-05-A2-C1-evidence.md: actual identity/task/dispatch/model, commands/CWD/exits/logs, AC/F mapping, inherited/current hashes, complete trace index, failed attempts/limitations. Final TASK-MVP-05-A2-C1-hashes.json covers product/harness/evidence/report, excludes itself. No project PASS claim.
Use live Orca preamble and real CLI. No upfront blocking asks: work starts now; ask only actual blockers, never token checkpoints. Read mailbox naturally and before worker_done; emit matching worker_done and end. No other workers/reviewer launches by implementer.

## A2/C1 implementation settlement — 2026-10-26T18:39Z
Matching worker_done msg_b142517ece06, task_0fdf463a7de1/ctx_11a366a6c3d4, outcome succeeded at18:39:10Z; evidence/TASK-MVP-05-A2-C1-evidence.md. No project PASS. Native gpt-6-luna medium input11840541 (cached11673728 included), output49639; prior28965861 => cumulative40806402. Calls9 settled, prior A1 attempts unchanged; receipt evidence/TASK-MVP-05-A2-C1-implementer-usage-final.json. Provider primary56%, secondary40%, no refusal.
Worker-release state released/closed_agent_terminal/transcript captured; receipt evidence/TASK-MVP-05-A2-C1-implementer-release.json. delivery_c2dd87e4a14d ACKed. A2 report claims schema-based fixture, immutable wire snapshots, valid record29 fulltrace and unchanged product139 inherited hashes; independent review pending. A2 full-review1/2 reserved, call10 accounting-only; FAIL=>stop without C2/A3.

## 2026-10-26T18:46Z — routed TASK-MVP-05 A2/C1 PASS
Independent gpt-6.1-sol/medium task_36ad667176f9/ctx_90f25030eaee worker_done msg_e550b99b5d97 at18:45:51Z, report reviews/TASK-MVP-05-A2-C1.md. All AC001..007 PASS, F01 closed via actual schema-backed immutable same-ID trace, F02/F03/F04 confirmed. No open in-scope findings;46 A2+139 inherited hashes/sizes matched; no routine reruns. A1 FAIL/FAIL/review2/2 remain unchanged; A2 used review1/2, total fullreviews3, failed2, C3 diagnostics1. A2/C2/A3 not started.
Reviewer final input1853222 (cached1738112 included), output10030; prior40806402=>cumulative42659624 input/calls10 settled. Receipt evidence/TASK-MVP-05-A2-C1-reviewer-usage-final.json. Provider primary64%,secondary41%; no refusal; accounting-only remains. Reviewer released closed_agent_terminal/transcript captured; delivery_399fedfe6d41 ACKed. No push/deploy/merge/stage acceptance/next TASK. Local product commit authorized after this routed PASS; workflow/evidence and all history preserved.
Local product commit after routed PASS: 06f58065022db9c58524909027ddc2d454f7071f. No push/deploy; no successor/stage acceptance.
