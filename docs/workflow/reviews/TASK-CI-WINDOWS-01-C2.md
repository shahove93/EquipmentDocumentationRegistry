# TASK-CI-WINDOWS-01 — A1/C2 independent R2 repeat review record

- Reviewer: Codex `gpt-6.1-sol`, effort `high`, read-only.
- Orca Task `task_f340087ab3bd`, Dispatch `ctx_8c539733d199`,
  Run `run_b556ddaf13c3`, terminal `term_be14e9ad-1fe1-40df-a3ac-e308aaa6298b`.
- Worker result: `worker_done` msg_d70be34a3ede, outcome `succeeded` (verdict PASS).
- Revision reviewed: `main` HEAD
  `dccb14554cca3f688f20153f1f3eb41195740319`; approved TASK SHA-256
  `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`.
- Final code SHA-256:
  - `.github/workflows/windows-installer.yml`
    `7A256F572EC97760DF255EAE6E6E9E99989D7A00D68C456D15362FD27AD8DA21`
  - `packaging/windows/ci-installer.ps1`
    `764AB73A1C3BAD3AD49FC774AF61891AC690A3566C8B7E4F349D9583098D2F05`
  - `packaging/windows/ci-installer.py`
    `5EC794D5BC39ABD5772639BE1F9B28BA08CF772F92EF1F049442F75DE51B9FA5`
  - `docs/installation/windows.md`
    `E68366289EDA94264DFEA815CB817BD3293218F1A87BAD727B80D9AEEFD4881E`
- Packet: `docs/workflow/evidence/TASK-CI-WINDOWS-01/review-packet/`
  (`worker.diff`, `worker-c2.diff`, `docs-ci-section.diff`, `review-spec-c2.md`).

## Verdict

**PASS for local preparation — READY_FOR_CLOUD_TESTING only.** All C1–C12 local
criteria met. No cloud or full Windows/project PASS. Actual GitHub Actions run
remains **NOT_RUN**.

## Findings closure

| ID | Severity | Status | Closure evidence |
|----|----------|--------|------------------|
| CI-C2-01 | MAJOR | **CLOSED** | Workflow lines 47–53: `shell: pwsh`, `$ErrorActionPreference='Stop'`, explicit `$LASTEXITCODE` throw after both `npm ci` and `npm run build`; C2 native-exit probe exits 1 while the unchecked control exits 0. |
| CI-C2-02 | MINOR | CLOSED | Truthful Inno version-only wording; no invented hash. |
| CI-C3-01 | NIT | CLOSED | Unused `-BuildWorkDirectory` parameter/argument removed; build freshness checks retained. |
| CI-C12-01 | MINOR | CLOSED | Literal/reproducible commands, checked-in probe scripts and raw logs. |
| CI-C4-01 | MINOR (conditional cloud risk) | OPEN as documented risk | `provision.ps1:23-28` / `edr.iss:124-134`: same-session interactive-shell absence causes refusal, but runner incompatibility is not observed. Keep guards; if a real run establishes refusal, stop/route the affected install path separately. No current local stop. |

No BLOCKER/MAJOR remains. Reviewer found no new native-command masking and no
system-interpreter fallback. All four final SHA-256 values match; 342 of 345
baseline file hashes unchanged (differences only in allowed `windows.md` and
coordinator-owned HISTORY/STATE); original 23326 documentation bytes unchanged;
no unexpected changed file (new entries are the three allowlisted CI files and
coordinator-owned C1 review).

Reviewer reused worker-executed syntax/YAML/negative/native-exit evidence
without rerunning; read-only Git/hash/source comparisons confirmed the actual
final state. No file was written; no installer/product/database/VM/remote/network
service touched.

## Accounting

- Full reviews: **2 of 2** used. Failed reviews: 1 (C1 only). Approach A1
  exhausted its permitted correction; PASS closes the local acceptance slot.
- Codex calls for the logical CI TASK: **2** (C1 FAIL + C2 PASS), within the R2
  maximum of 4; separate from the two reserved ProgramData/lifecycle Windows
  calls, which remain unspent. Token usage was not exposed in the worker_done
  payload; not fabricated.
- Cloud C4–C9, real UAC, clean end-user PC and full lifecycle remain NOT_RUN.
  Publication and actual remote run require explicit user approval.
