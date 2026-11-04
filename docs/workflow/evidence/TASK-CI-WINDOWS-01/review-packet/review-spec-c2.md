# Independent R2 repeat review spec — TASK-CI-WINDOWS-01 A1/C2

You are the independent Codex reviewer for the single permitted **repeat full
review** of TASK-CI-WINDOWS-01 approach A1, cycle C2. This is full review 2 of
2. You are read-only: do not edit any file, do not run shell edits, do not
install/start the product, do not touch the working database, the local VM,
remote Git or any network service. Inspect the actual files and evidence and
return a bounded verdict.

Repository: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`,
HEAD `dccb14554cca3f688f20153f1f3eb41195740319`.

## Context

C1 was reviewed and FAILed on MAJOR CI-C2-01:
`.github/workflows/windows-installer.yml` ran `npm ci` and `npm run build`
consecutively without checking the first native exit code, so a failed install
could be masked. C1 review record:
`docs/workflow/reviews/TASK-CI-WINDOWS-01-C1.md`.

A bounded C2 correction was made by a separate implementer:
`docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/c2-correction.md`.
Correction delta: `review-packet/worker-c2.diff`. Current file SHA-256:
- `.github/workflows/windows-installer.yml`
  `7A256F572EC97760DF255EAE6E6E9E99989D7A00D68C456D15362FD27AD8DA21`
- `packaging/windows/ci-installer.ps1`
  `764AB73A1C3BAD3AD49FC774AF61891AC690A3566C8B7E4F349D9583098D2F05`
- `packaging/windows/ci-installer.py`
  `5EC794D5BC39ABD5772639BE1F9B28BA08CF772F92EF1F049442F75DE51B9FA5`
- `docs/installation/windows.md`
  `E68366289EDA94264DFEA815CB817BD3293218F1A87BAD727B80D9AEEFD4881E`

## Authority and scope

- Authority: `docs/workflow/APPROVALS.md` §CI_WINDOWS_LOCAL_PREPARATION_AUTHORIZED_20261104,
  TASK `docs/tasks/TASK-CI-WINDOWS-01.md`, scope SHA-256
  `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`.
- Review **only the new CI change** for local preparation. Pre-existing dirty
  packaging, ProgramData/lifecycle, UAC and full lifecycle are out of scope; use
  them only as read-only context.
- Local outcome can only be **READY_FOR_CLOUD_TESTING**. The actual GitHub run
  is **NOT_RUN**. Do not grant cloud or full Windows PASS.

## Inputs

- Frozen checklist: `docs/workflow/evidence/TASK-CI-WINDOWS-01/frozen-checklist.md`
- Dispatch/baseline plan: `docs/workflow/evidence/TASK-CI-WINDOWS-01/dispatch-plan.md`
- Baseline: `baseline-head.txt`, `baseline-status.txt`, `baseline-dirty.diff`,
  `baseline-hashes.json`.
- Review packet: `review-packet/`
  - `docs-ci-section.diff` — only the appended CI section of windows.md
    (pre-TASK baseline is the first 237 lines).
  - `worker.diff` — original C1 diff.
  - `worker-c2.diff` — C2 correction delta.
  - `review-spec.md` — original C1 review spec.
- C2 correction report:
  `implementer/c2-correction.md`.
- Implementer evidence: `implementer/` (`report.md`, `checks.md`,
  `c2-correction.md`, raw check logs, probe scripts, `git-status.txt`).

## What to verify (repeat full review)

1. **Closure of C1 findings:**
   - CI-C2-01 (MAJOR): the frontend step now uses `shell: pwsh`,
     `$ErrorActionPreference = 'Stop'`, and an explicit `$LASTEXITCODE` throw
     immediately after each of `npm ci` and `npm run build`, so the first
     nonzero npm exit fails the step. Verify the actual YAML and the local
     fail-closed/fail-open-control evidence. Confirm the defect is closed.
   - CI-C2-02 (MINOR): docs now describe Inno as version-verified, not
     byte-pinned, and do not invent a hash.
   - CI-C3-01 (NIT): unused `-BuildWorkDirectory` parameter/argument removed;
     workflow freshness check retained.
   - CI-C12-01 (MINOR): commands in `checks.md` are literal/reproducible, no
     ellipses/placeholders.
   - CI-C4-01 (MINOR cloud risk): remains a documented NOT_RUN risk; confirm the
     correction did not weaken packaging guards and did not pretend to fix it.
2. **Full checklist C1–C12 on the final state** (not just the delta):
   valid YAML, single `windows-installer` job on `windows-latest`,
   `workflow_dispatch`, `permissions: contents: read`, unchanged
   `.github/workflows/ci.yml`; pinned Python/PostgreSQL URLs+SHA-256 matching
   recorded build-contract evidence; Inno `6.7.3` version verification; fresh
   work dirs; fail-closed guard requiring `GITHUB_ACTIONS=true`, `CI=true`,
   `RUNNER_OS=Windows`, `RUNNER_ENVIRONMENT=github-hosted`, rejecting
   `EDR-Win11-Test`/sandbox, requiring absent work/install/`%ProgramData%\EDR`,
   no side effects on refusal; silent install → file checks → installed
   interpreter start → `/health` → UI root → synthetic document/PDF
   upload/download SHA-256 → stop/restart/persistence SHA-256 → clean stop;
   `if: always()` artifact upload; allowlist-only changes; docs accuracy.
3. **No regression / no fail-open:** explicitly check that no other native
   command sequence can silently ignore a failure, and that the installed
   runtime is always the bundled interpreter.
4. **Unexpected files:** compare the actual diff/status with the allowlist.
   Report any unexpected changed file.

C4–C9 remain cloud NOT_RUN; static implementation is what can be accepted
locally.

## Verdict

Return exactly one verdict:

- **PASS** — all C1–C12 local criteria met, CI-C2-01 demonstrably closed, cloud
  items correctly NOT_RUN, only MINOR/NIT findings; local result
  READY_FOR_CLOUD_TESTING.
- **FAIL** — any BLOCKER/MAJOR finding. List stable finding IDs, criterion,
  location, observed result, reproduction/evidence, expectation, severity, and
  whether the affected path must stop.

If this repeat review FAILs, no further full review is permitted: only C3
diagnosis remains. Do not invent results and do not grant a project/cloud PASS.
End after the verdict using Orca `worker_done` (outcome succeeded for PASS,
failed for FAIL) with a three-sentence summary, the verdict, findings, files
inspected and evidence paths. Do not write any file; the coordinator records
your verdict.
