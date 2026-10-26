# TASK-MVP-04 — final evidence review

Verdict: **PASS** for the frozen AC-001 through AC-010. **MVP04-R2-001 CLOSED**.

Date: 2026-10-26. Independent R2 reviewer, authorized call **5/5**, second/final review slot **2/2**. This is the bounded completion of missing evidence verification, not a new implementation or expanded code review. The prior C1 BLOCKED report and all historical failures/spend remain intact.

Run `run_68046cea3eb4`; worker Task `task_f46401946eef`; Dispatch `ctx_ab6321c6c683`; reviewer `term_cf5c2ff7-a4eb-49ff-bc9e-72b50b2d787c`; coordinator `term_d727cc23-31e8-42eb-a295-c42268e0c645`.

Authority is the current explicit dispatch/user exception: one additional Astra call, parent input ceiling 12,400,000, prior actual 12,016,680 preserved, remaining 383,320; this worker reserve 300,000 including finalization. Current Codex coordination/product authorization applies despite WF-01 BLOCKED. No WF-01 repair or acceptance is implied.

## State identity and evidence method

Workspace `D:/Antigravity/EquipmentDocumentationRegistry`; WSL test CWD `/mnt/d/Antigravity/EquipmentDocumentationRegistry`. Live read-only `git rev-parse HEAD` and `git branch --show-current` returned exit 0, baseline/HEAD `a405968401eefe6bcbbc2ca3302d14072eb63509`, branch `main`.

The reviewer computed SHA-256 for all 17 entries in [SHA256-final](../evidence/TASK-MVP-04-SHA256-final.txt): **17/17 matched**, including the empty `app/api/batches/__init__.py`. Manifest SHA-256 is `DEEBF64C47910D6427BC10E1C2B8FBB383D7DE34964E4FB252901ACD7B6670AF`, identical to C1. Thus the exact product/test/status set previously inspected is unchanged. Hashes used PowerShell `Get-FileHash -Algorithm SHA256 -LiteralPath` for the manifest and each listed path; count and per-file match booleans were inspected, exit 0.

[Prior independent C1 review](TASK-MVP-04-C1.md) is inherited checked evidence: all eight new files, the allowed tracked diff, AC static mappings, fixture isolation and the user-approved seven totals changes 19→21 / 34→38 plus two test names were already inspected. C1 found no product BLOCKER/MAJOR. These checks were not repeated. Its original BLOCKED verdict was a bounded evidence-viewing/resource gap, not a product FAIL.

This review independently read the complete original F and ALL-final logs in separate bounded outputs, G-final in contiguous lines 1–80, 81–160, 161–240 and 241–291, and the complete coordinator cleanup log. No output truncation occurred in those reads. Pertinent execution/continuation sections of [implementer C1 evidence](../evidence/TASK-MVP-04-C1.md) supplied exact commands, CWD and recorded exits; raw output was checked against them. No pytest, Alembic, frontend or product exploration was run by this reviewer.

## Final AC disposition

Every static mapping below is explicitly **inherited from independent C1**, not a fresh code inspection. S/V/H/O are inherited executed-check evidence, with their exact commands/results preserved below. Newly inspected F/ALL/G evidence completes acceptance of the unchanged state.

| AC | Inherited checked mapping | Final disposition |
| --- | --- | --- |
| AC-001 | schemas.py:19–63 and schema tests:14–35,80–113: exact fields, extra forbid, required FK, explicit null handling, exclude_unset, Read.from_attributes, six keys; S114. | PASS; unchanged hashes, F and final ALL confirm required tests. |
| AC-002 | Schema trim/bounds/null/date and service/API normalization, Unicode/date persistence; no quantity/unit cross-requirement; S/H/F. | PASS. |
| AC-003 | Public Measurement as Quantity, finite/>0/exponent/bound validation, Decimal Read, no float/rounding; schema/service/API tests; S/V/H/F. | PASS. |
| AC-004 | Service get/create/list/update, unknown Batch first, require_variant before mutation, no delete, cross-Product transfer; V55. | PASS. |
| AC-005 | One commit, rollback SQLAlchemyError, exact sqlstate+constraint+table classification; commit spy, real FK rollback/reusable Session, foreign diagnostics/no retry; V/F. | PASS. |
| AC-006 | SQL id ASC, limit/offset/default50, global listing without filter/join; duplicates/null/pagination; V/H. | PASS. |
| AC-007 | Four routes, POST201 with absolute followable Location, GET/list/PATCH200, empty PATCH, no DELETE/PUT and 405 persistence; H88. | PASS. |
| AC-008 | Domain-only 404 conversion, validation 422 before service, priority/null/extra, safe500, no partial write/no error Location; H88. | PASS. |
| AC-009 | Two paths/four operations, refs/tags/summaries/unique IDs, statuses/body/nullable/date/Decimal, no linking/delete/put; O10/F. | PASS. |
| AC-010 | Amended allowlist and tracked diff already inspected by C1; 17 identities now independently reconfirmed; F/ALL/G originals and subsequent cleanup now fully inspected. | PASS; evidence gap closed. |

No new functional criteria, design changes, severity findings or backlog requirements were introduced. Frozen contract and allowlist are unchanged.

## Executed checks and precise provenance

All pytest commands below were executed by the implementer, **not rerun here**. Windows launch CWD: `D:\Antigravity\EquipmentDocumentationRegistry`; shell: WSL Ubuntu; inner CWD: `/mnt/d/Antigravity/EquipmentDocumentationRegistry`.

**F:**

```text
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch.py tests/test_batch_schemas.py tests/test_batch_service.py tests/test_batches_api.py tests/test_batches_openapi.py tests/test_issuer_schemas.py tests/test_issuer_service.py tests/test_issuers_api.py tests/test_variant_schemas.py tests/test_variant_service.py tests/test_variants_api.py'
```

[F original](../evidence/TASK-MVP-04-F.txt) ends `1094 passed, 1 warning in 109.98s (0:01:49)`. Exit **0** is recorded in the implementer C1 command table; the raw F file itself contains pytest stdout, not an exit marker. This provenance distinction is preserved. The raw successful test result was directly inspected; exit 0 is inherited execution metadata supported by that result.

**Final ALL:**

```text
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'
```

[ALL-final original](../evidence/TASK-MVP-04-ALL-final.txt) ends `3771 passed, 1 warning in 447.49s (0:07:27)` and explicit `ExitCode: 0`. C1 continuation records the same command/CWD/exit and that the captured exit belongs to the already completed process. Both raw logs show the same `StarletteDeprecationWarning` about httpx in starlette.testclient. The original ALL (`7 failed, 3764 passed, 1 warning`, exit 1) remains historical evidence; it is not substituted for the final successful integrated run and was not erased. The approved counter/name correction and its static scope were already checked in C1.

**Inherited S/V/H/O:** exact command prefix is `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q `, followed by the table's arguments and a closing single quote. CWD is as above; each recorded exit is 0.

| ID | Exact arguments after prefix | Recorded result |
| --- | --- | --- |
| S | `tests/test_batch_schemas.py` | 114 passed in 1.04s |
| V | `tests/test_batch_service.py tests/test_batch.py` | 55 passed in 6.38s |
| H | `tests/test_batches_api.py` | 88 passed, 1 warning in 17.61s |
| O | `tests/test_batches_openapi.py` | 10 passed in 3.16s |

These sufficient inline results were checked by C1 and reused unchanged; newly inspected F and final ALL reinforce the same unchanged test state. Inherited Alembic evidence in C1: `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic heads'` → exit 0, `e4b8c2d16a70 (head)`; `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py | wc -l'` → exit 0, `13`. No new migration/database verification is claimed.

**G-final:** [original](../evidence/TASK-MVP-04-G-final.txt), all 291 lines inspected. Recorded CWD `D:\Antigravity\EquipmentDocumentationRegistry`.

| Exact command | Recorded exit and directly observed result |
| --- | --- |
| `git status --short` | 0; modified/untracked paths recorded, including the separate coordinator/workflow changes already classified by C1. |
| `git diff --check` | 2; `docs/workflow/HISTORY.md:345: new blank line at EOF`, with CRLF-to-LF warnings. This historical result is preserved. |
| `git diff --name-only a405968401eefe6bcbbc2ca3302d14072eb63509` | 0; changed tracked paths recorded. |
| `git ls-files --others --exclude-standard` | 0; new Batch and evidence/workflow files recorded. |
| `git diff -- docs/PROJECT_STATUS.md` | 0; status diff captured, including final test totals and pending independent review. |
| `git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- app/models alembic` | 0; empty diff. |
| `git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- tests/test_batch.py tests/conftest.py` | 0; empty diff. |
| `git rev-parse HEAD` | 0; `a405968401eefe6bcbbc2ca3302d14072eb63509`. |
| `git diff --check -- app/api/router.py docs/PROJECT_STATUS.md tests/test_document_variants_api.py tests/test_documents_integration_api.py tests/test_documents_search_api.py tests/test_files_api.py tests/test_files_delete_api.py tests/test_files_download_api.py tests/test_files_upload_api.py` | 0; stdout empty, recorded scoped check. |

[Later coordinator cleanup](../evidence/TASK-MVP-04-coordinator-G-cleanup.txt) records exact command `git diff --check`, CWD `D:/Antigravity/EquipmentDocumentationRegistry`, **EXIT: 0**. Its complete output contains only CRLF-to-LF warnings, with no EOF error. This closes the earlier coordinator-owned whitespace failure; it does not rewrite G-final exit 2 or require a product correction.

## Finding closure and boundaries

**MVP04-R2-001: CLOSED.** Criterion: completed independent evidence verification, primarily AC-010. Prior observation: truncated combined reads and exhausted reserved input prevented complete F/ALL/G inspection. Required closure: explicit resource authorization plus full original-log inspection within the new reserve. Current evidence: explicit call5/slot2 authorization, complete bounded original reads, 17/17 unchanged hashes, final ALL exit0, F successful output with recorded exit0, complete G and later cleanup exit0. No product BLOCKER/MAJOR was found by inherited C1; no acceptance evidence gap remains in this assigned scope. Combined final verdict is PASS.

Only this report was created. No code/tests/prior reports/status/workflow bookkeeping was edited; no tests, migration commands, frontend checks, workers, commits, pushes, merges, deployments, settings/data changes or resets were performed. Coordinator owns final accounting and recording the routed verdict; worker settlement itself is not acceptance. WF-01 remains BLOCKED/NOT_ACCEPTED and outside this review.

## Model and input accounting

Actual local rollout metadata confirms provider `openai`, model `gpt-6-astra`, effort `high`, matching this dispatch. Session `01a17825-9683-77f3-a52e-97fae38a9461`; rollout `C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T15-18-11-01a17825-9683-77f3-a52e-97fae38a9461.jsonl`; turn_context CWD matches the workspace. Only session_meta, turn_context model/effort/CWD and token_count fields were emitted, not transcript contents.

One observed usage snapshot at `2026-10-26T12:19:42.532Z`: input **99,928**, cached input **70,272** (already included in input), output **1,167**, reasoning output **200**, total **101,095**. This is a pre-finalization snapshot, **not final worker or TASK cost**. Report/tool/mail/final output may add usage; coordinator must record the settled actual from this rollout without refunding prior spend. No repeated quota collection, provider exhaustion, model/account/plan changes, reset or new session occurred. A read-only optional artifact-identity formatting command had a PowerShell parse error before execution; corrected below, with no effect on verification or files.

## Original artifact identities

The following SHA-256/byte identities are computed from the original files during report finalization; the contents were inspected above.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| docs/workflow/evidence/TASK-MVP-04-F.txt | 1857 | 0046E90FBE70F45C3A992569C66E69343B5700572C330DF140115D0A60B609E9 |
| docs/workflow/evidence/TASK-MVP-04-ALL-final.txt | 9732 | 44CBF396E168F04B45F0242AAFC19C56FFF1890E1F57F6635FD137167000C8C5 |
| docs/workflow/evidence/TASK-MVP-04-G-final.txt | 25914 | B2C9B90106DAE7AF1C5DC9C671AF38A1B51CA36AC0469B27D8FD6D50BBBDB043 |
| docs/workflow/evidence/TASK-MVP-04-coordinator-G-cleanup.txt | 669 | F6C4ABCB42DAE03ECDAB5C7F921705FEBB4D4C19C7BB8381C29E991498DF2E44 |
| docs/workflow/reviews/TASK-MVP-04-C1.md | 13905 | 23484A87EAE401A88D2A40659DB22CC3FF1CB0FD6194242E731DFE3A7BF23C03 |
