# TASK-MVP-05 C1 implementation evidence

Status: implementation and listed checks were performed, but the worker is BLOCKED because authoritative provider input usage exceeded the frozen TASK input ceiling. Independent routed acceptance has not run; no project PASS is claimed.

## Scope and workspace

- Frozen task: `docs/tasks/TASK-MVP-05.md`; R1, A1/C1; Run `run_68046cea3eb4`; Task `task_1f8ceba36e9e`; Dispatch `ctx_e9800c446d2d`.
- Repository branch/workspace: `main`, `D:/Antigravity/EquipmentDocumentationRegistry`; baseline `318e6336737ee635abf593c2643f26daba273f86`.
- Implemented Batch API client/types, list/detail/create/edit UI, variant picker, nav link and `/batches` Vite proxy with HTML SPA bypass. Existing Batch routes only are used.
- No backend, database, migration, dependency, package manifest, document-link or authentication changes.

## Observable checks

| AC | Evidence |
| --- | --- |
| AC-001 | Orca browser page `a5a98608-453d-4c3c-b8be-5effd41ecae6` opened/refreshed `http://localhost:5173/batches`; snapshot showed navigation and Batch UI. An HTML `GET /batches` through Vite returned HTTP 200, `text/html`, and the SPA shell. Screenshot: `TASK-MVP-05-browser.png`. API JSON was forwarded through Vite to fixture (`TASK-MVP-05-api-log.json`). |
| AC-002 | UI showed loading then empty state, then the created row. The list query was `GET /batches?limit=26&offset=0`; its response status was 200. Detail was read by `GET /batches/1` (200). Empty nullable fields displayed as em dashes. |
| AC-003 | Browser submitted `POST /batches` with `{"variant_id":7,"batch_number":"LOT-FINAL","manufacture_date":null,"quantity":"99.25","quantity_unit":"kg"}`; fixture returned 201 and ID 1. UI then read ID 1 and a refreshed list displayed the row. |
| AC-004 | Browser edited ID 1 and submitted `PATCH /batches/1` with `{"quantity":null,"quantity_unit":null}`; fixture returned 200. The following list request returned 200 and displayed both nullable fields empty. Existing `batch_number` and `variant_id` remained. |
| AC-005 | Quantity remains string-valued through state and request construction; no float conversion is used. Detail requests use an effect-owned AbortController and ignore aborted results; list and variant-picker reads are also aborted on replacement/unmount. Errors render through the existing safe `describeError` helper. |
| AC-006 | Real browser UI and real relative API calls through Vite proxy were exercised against the explicit in-memory mock fixture. Fixture was labelled `MOCK ONLY`; it did not use the product DB or storage. Screenshot and request/response status/payload journal are linked above. |
| AC-007 | `npm run typecheck` and `npm run build` both exited 0 in WSL with Node v24.22.0. Exact output is in `TASK-MVP-05-typecheck.log` and `TASK-MVP-05-build.log`. |

The temporary fixture server is source-controlled as the allowed evidence artifact `TASK-MVP-05-fixture.py`; it keeps data in process memory only. It is not a substitute for a production backend round trip. `TASK-MVP-05-api-log.json` contains observed requests and fixture HTTP responses; `/batches` document navigation returned the SPA HTML shell. No backend/database tests were rerun.

## Diff and evidence integrity

Implementation files are limited to the TASK allowlist: `frontend/src/types/api.ts`, `frontend/src/api/batches.ts`, `frontend/src/components/BatchForm.tsx`, `frontend/src/pages/BatchesPage.tsx`, `frontend/src/App.tsx`, `frontend/src/components/Nav.tsx`, `frontend/src/styles.css`, and `frontend/vite.config.ts`. Generated `frontend/dist` was produced by the required build and is not part of the implementation allowlist. Dependencies and package manifests are unchanged.

Logs, screenshot, fixture and this report are `TASK-MVP-05-*` artifacts under `docs/workflow/evidence/`.

## Provider usage and blocker

Authoritative native rollout metadata was verified by the coordinator for this exact task/dispatch: model `gpt-6-luna`, effort `medium`; rollout `C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T16-08-37-01a17853-c00d-7671-9966-39f89dd18a58.jsonl`. At the captured `token_count` snapshot: input 7,271,010 (including 7,029,120 cached input), output 30,891, reasoning 9,290, total 7,301,901. Cached input is included in input, not additive. This exceeds the frozen 1,000,000 input ceiling and the 600,000 worker reserve; provider usage reported 48% of its 300-minute window, with no provider exhaustion. Supporting snapshots: `TASK-MVP-05-provider-checkpoint.json` and `TASK-MVP-05-usage-checkpoint.json`. Per the TASK budget rule, stop the dependent chain; do not run the reviewer, further checks, or corrections without an explicit new resource decision.

`git diff --check` exited 0. Allowlist/status review and final artifact hashes are recorded in the evidence pack. This report is implementation evidence only and does not declare TASK PASS.
