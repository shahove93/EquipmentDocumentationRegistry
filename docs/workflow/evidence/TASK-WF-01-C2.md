# TASK-WF-01-C2 — operational setup evidence

Date: 2026-10-26 (Moscow). Baseline: `main`, `a405968401eefe6bcbbc2ca3302d14072eb63509`.
Task/Dispatch: `task_d93200c5b6b2` / `ctx_eba8fecff71e`; worker terminal: `term_f2e42ac1-07ef-40bf-8517-f2ae394998f4`.
Run: `run_68046cea3eb4`; current coordinator handle `term_f2e42ac1-07ef-40bf-8517-f2ae394998f4`, generation 7, verified by live `run-show`. Run binding is confirmed; this evidence does not establish exclusive process ownership or WF-01 PASS.

## Approval and routing

The prior approval row for the alternate `terminal create` launch had been accidentally relabeled `CODEX_NEMOTRON_20261026`. Its date/source cell is restored to the actual 2026-10-26 OpenCode session reply, “Разрешить альтернативный запуск (Recommended)”; its decision, hashes, scope and restrictions remain intact. A separate new approval row records the actual Codex + Nemotron user instruction and later model-routing addition. Baseline and prior approved ADR/ROADMAP revisions are identified there; hashes of the edited current documents are recorded in the final hash snapshot below.

The temporary exception expires 2026-10-27 00:00 Europe/Moscow. Local Nemotron alone coordinates; cloud OpenCode is disabled. Separate Codex agents may implement/review. AC IDs and functional requirements remain unchanged; AC-005/009 specify the approved route substitution. Dedicated external local profile/launcher/diagnostics are within WF-01 operational scope. After WF-01 acceptance, already approved MVP tasks may continue without routine start confirmation. Actual provider exhaustion stops dependent work pending a new user decision even after reset. No global model/account/plan changes, credit reset/purchase, push/merge/deployment, product-code or product-data changes are allowed.

Model routing recorded from the explicit user instruction: this setup/documentation worker was assigned GPT-6 Luna, medium; WF-01 independent review is reserved for GPT-6.1 Sol, medium; MVP-04 implementation is GPT-6.1 Sol, medium; MVP-04 R2 review is GPT-6 Astra, high. The actual Codex quota helper reads rate-limit metadata, not a dollar cost or a per-worker allocation.

## Launch, model, cost and binding facts

- External launch receipt `D:/AI/NemotronBoltE4B/logs/edr-experiment-20261026-launch.json` identifies this terminal handle, local Windows host and project worktree. The receipt belongs to this worker; it is not a reviewer launch.
- Bounded `Get-CoordinatorMetadata.py` reported local Nemotron session `ses_e88db33d9ffe7MQijTub3mPnb6`, model `local-nemotron/nemotron-bolt`, 47 messages, cost 0, cloud provider count 0. The requested coordinator model and local-only status agree with the dedicated launch profile. No credentials or session transcript were printed.
- The live server check returned `/health = ok`; `/v1/models` returned only `nemotron-bolt`, `n_ctx=32768`; process PID 8304 runs `D:\AI\NemotronBoltE4B\bin\llama-server.exe`.
- Dedicated `Open-EDR-Coordinator-v2.ps1 -CheckOnly` returned `CONFIG_VALIDATED`, model `local-nemotron/nemotron-bolt`, `launched=false`, `run_mutated=false`. This checks the profile configuration; it is not a production handover test.
- Global OpenCode config SHA-256 remains `31032AD46AB3230E75B9A9B0EE9CB255630D188C25949438C76AD9940A5CAE81`. Dedicated profile: `53A6ED22B52CC0966D876F36375363330FC82836562932EFC36679BD05D23C09`; bootstrap: `E28B5EB8E58065765F12FC9F3AC2F6324C792810830CF38C8F2B857B28AF9411`; launcher: `047BA20544FF7DD5A6F2D50710B7098A379158265687688286B9EFBBEC61E47B`.
- Earlier diagnostic runs in `checks/coordinator-20261026-100202/results.json` showed six bounded diagnostics (real Orca read, bounded worker projection, recall, UTF-8 temp-file read/edit/readback, deliberate edit failure with unchanged readback, and blocked gate), context 2.8K–5.0K per run and cost 0. The actual-profile diagnostic read STATE and verified generation 6 before this later generation-7 handover. These synthetic diagnostics do not prove long-duration reliability.

## Failures and corrections retained

- Earlier Nemotron coordinator attempts had five failed edits but asserted success, then fabricated worker/session identifiers without Orca calls; their factual record remains in C1 and `TASK-WF-01-local-failure.md`. The tuning report also records a truncated context/compaction and omitted identifiers. Those false success statements are not accepted as evidence.
- The coordinator's handover record says the initially rejected reviewer-start mutation did not start a reviewer; its mutation request ID is not a Dispatch and is not counted as a review. No reviewer has been started by this setup submission.
- A later malformed PowerShell `Select-Object` dotted-property projection returned nulls. Null fields from that malformed projection do not prove that no workers existed and are not used for that conclusion.
- The old DeepSeek dispatch `task_efc8f84abfbc` / `ctx_c254370b2df1` / `term_54cfac1f-2d78-432f-9675-f5ee1e7d9376` was positively reported exited/failed by execution-host `worker-show` at 10:37:39 Moscow. No product code was written; no fabricated `worker_done` is recorded.
- The independent review report became available after this setup packet was first written. `docs/workflow/reviews/TASK-WF-01.md` reports **FAIL**, finding `WF01-AC004-001` (BLOCKER): current coordinator screen said the old Dispatch was heartbeating/investigating while live Orca says failed/exited; AC-008 also fails on that same fact-handling gap. It reports AC-001/002/003/005/006/007 PASS, AC-009/010 not fully verified. Its actual reviewer model is `gpt-6-luna`; the user-approved route for WF-01 review was `gpt-6.1-sol` / medium. No review Task/Dispatch IDs are established by that report. Do not treat this report as PASS or fabricate missing lifecycle IDs.
- Review worker quota metadata in that report: 29%, primary 300 minutes, reset `1793013647` (same baseline primary window); secondary 5%, 10080 minutes, reset `1793600447` is separate. The review rollout reports 639022 input, 568576 cached input, 7011 output, 3478 reasoning output, 646033 total tokens. Setup + reviewer call exhaust the bounded WF-01 allowance 2/2; any additional review requires coordinator reconciliation and, if unavailable, a new user decision. Do not refund the wrongly routed call.
- A later read-only usage-helper snapshot at 11:09 Moscow reported 31% primary, 300 minutes, reset `1793013647`; secondary 5%, 10080 minutes, reset `1793600447`. Aggregate session total was 11580573 tokens; this metadata does not isolate setup-task input or convert usage into dollars. The observed quota progression is recorded by timestamp, not attributed wholly to one call.
- Existing product test baseline remains 3530 passed on 2026-10-25. No backend/frontend tests were run as part of this documentation/setup call.
- At 10:28:06 Moscow quota was 15%; at 10:29:49 it was 18%. A bounded helper read at 10:55 Moscow reports primary limit `codex`, 26%, 300 minutes, reset epoch `1793013647` (14:20:47 Moscow); weekly secondary is a separate 4%, 10080-minute window, reset epoch `1793600447`. These are distinct time snapshots, and the primary figures share the same reset window. The setup consumed observable user-session quota; it is not free even though local Nemotron session cost is 0. No API-dollar-to-subscription conversion is made.

## Git and acceptance status

This worker changed workflow/specification/evidence and approved external local helpers only; it did not change product code, tests, migrations, frontend, environment, storage or dependencies, and it did not commit. Existing work in progress was preserved. The independent report currently says **FAIL** on AC-004/008; previous failure evidence is preserved. The historical 3530-test baseline is not presented as a new run.

Current repository SHA-256 after setup and truthful review status update:

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `AC6F5C743C8C391C97636775020E765495FB3166B348185FAF00627DF701DDB6` |
| `ROADMAP.md` | `84414BC0395B20AE9EC6D5983FE4413E913374F3A95CE8AF6C16E82F48C861EA` |
| `docs/adr/ADR-011-local-nemotron-coordinator.md` | `49D86B8E01E84AB0BC2A09A2A8CD7CCD8D082B50EBED93377358113ACC422CEE` |
| `docs/workflow/APPROVALS.md` | `3E8F35AF6789E6402853E6335ACDB1CB02398E7B61DC4C2D767C03E20B1BF04B` |
| `docs/tasks/TASK-WF-01.md` | `33E5038D2A41FEF0C8A46ADE4B1611DD34C27D59030C1D3CFD2EEA2926002CAB` |
| `docs/tasks/TASK-MVP-04.md` | `4CA63DE39857D9FE4B4E18BD906CC5F70D6F7570CA8E7DCAD5C7F4473FBE65DF` |
| `docs/workflow/STATE.md` | `D726EA3BFCE005A61330CF5DE10057E5CD9C4656CC4ABFB6E7D180BA9DAA863C` |
| `docs/workflow/HISTORY.md` | `CC9C86953DDB747CBCF189FFD0AB32DA3CFCB6A9E30D0660AFACA6CCDE1F6E6D` |
| `D:/AI/NemotronBoltE4B/Get-EDRWorkerStatus.ps1` | `392EAFB8EAB40BF222A4F6F4F3E4FA05F72F30F2B67621CE43CECB398F63B836` |
| `D:/AI/NemotronBoltE4B/Start-WF01CodexReview.ps1` | `3FF1059D0D170090355D07EFC7D4500637FAC649F2AAAB9F1C7125FCCAF4569C` |
| `D:/AI/NemotronBoltE4B/opencode-edr-experiment-20261026.json` | `31A8CB846BD89924E457A9059D4DF5DDE1B4E04858783A4A920545DC2CFC688F` |
| `D:/AI/NemotronBoltE4B/EDR-EXPERIMENT-20261026.md` | `4DF05D5E5EE1B0A5B6099F14896FD50094AEF260B653946991172983B4C6BB5D` |
| `D:/AI/NemotronBoltE4B/Open-EDR-Experiment-20261026.ps1` | `C92315223CEE13A113AD735123E373BC784BEE6ACA7BC9FC04BF5B601A685FF8` |

## Bounded guards prepared after coordinator follow-up

- `D:/AI/NemotronBoltE4B/Get-EDRWorkerStatus.ps1` performs one read-only `worker-show`; it requires both expected IDs, maps ready/input_accepted to `in_progress`, and requires explicit outcome plus a nonempty report before it can return `verified`. It never acknowledges mail or starts successors.
- `D:/AI/NemotronBoltE4B/Start-WF01CodexReview.ps1` now passes the full spec text and explicit `codex`, `gpt-6.1-sol`, `medium`; nonzero CLI exit or JSON `ok:false` produces an explicit failed result with the output retained.
- `opencode-edr-experiment-20261026.json` grants only the read-only status helper command. The running coordinator was launched with inline `OPENCODE_CONFIG_CONTENT`; this file edit does not change active permissions. No denial was bypassed and no coordinator restart was performed. The Run owner must arrange a controlled restart after settling active work before relying on the profile permission.
- An initial PowerShell AST check found an apostrophe in an existing single-quoted error string in `Start-WF01CodexReview.ps1`; the string was corrected, then all three affected PowerShell scripts parsed successfully. The experiment profile JSON parsed successfully and `Open-EDR-Experiment-20261026.ps1 -CheckOnly` returned `CONFIG_VALIDATED`, `launched=false`, `run_mutated=false`.
- Live helper invocation was read-only for the positively exited old Dispatch and returned matching Task/Dispatch IDs, `failed`, `process_exited`, and `liveness=exited`. The `ready`/`input_accepted` branch is covered by code inspection, not a fabricated live worker result. No reviewer or successor was started by this setup call.

Current independent report verdict is **FAIL**, not acceptance. The Task remains blocked on AC-004/008 and actual reviewer route discrepancy; setup completion is not WF-01 PASS.


## Историческая поправка call3, 2026-10-26

Предыдущий текст и неуспешные результаты сохранены. Это исторический,
неточный пакет, не актуальное evidence: terminal `term_f2e42ac1…` принадлежал
координатору, а реальный setup worker — `term_b6bac716-303a-4c27-863a-0cd231697740`.
Generation 7 заменена сначала 8, затем 9. Исходный хеш до этой приписки
`8D0B702FD99E9E2A15AD398161C1A29296ECE29A9117C4E66EE67F24B899C7AE`
остаётся в независимом FAIL. Новая коррекция и факты —
[TASK-WF-01-C2-correction.md](TASK-WF-01-C2-correction.md).
Прежний отчёт не переписан; ни один FAIL не превращён в PASS.
