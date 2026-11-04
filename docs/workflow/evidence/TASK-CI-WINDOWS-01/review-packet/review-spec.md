# Independent R2 review spec — TASK-CI-WINDOWS-01 C1

You are an independent Codex reviewer for the TASK acceptance of
TASK-CI-WINDOWS-01 approach A1 / cycle C1. You are read-only: do not edit any
file, do not run shell edits, do not install/start the product, do not touch the
working database, the local VM, remote Git or any network service. Inspect the
actual files and evidence yourself and return a bounded verdict.

Repository: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`,
HEAD `dccb14554cca3f688f20153f1f3eb41195740319`.

## Authority and scope

- Authority: `docs/workflow/APPROVALS.md` §CI_WINDOWS_LOCAL_PREPARATION_AUTHORIZED_20261104,
  TASK `docs/tasks/TASK-CI-WINDOWS-01.md`, scope SHA-256
  `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`.
- This review covers **only the new CI change** for local preparation:
  `.github/workflows/windows-installer.yml`,
  `packaging/windows/ci-installer.ps1`, `packaging/windows/ci-installer.py`,
  and the new CI section of `docs/installation/windows.md`.
- Pre-existing dirty/untracked files, ProgramData/lifecycle packaging, UAC and
  full lifecycle are OUT OF SCOPE. Do not re-accept or re-review them. Treat
  them only as read-only context needed to judge the CI diff.
- Local outcome can only be **READY_FOR_CLOUD_TESTING**. The actual GitHub
  Actions run is **NOT_RUN**. Do not grant cloud or full Windows PASS.

## Inputs

- Frozen checklist: `docs/workflow/evidence/TASK-CI-WINDOWS-01/frozen-checklist.md`
- Dispatch/baseline plan: `docs/workflow/evidence/TASK-CI-WINDOWS-01/dispatch-plan.md`
- Baseline: `baseline-head.txt`, `baseline-status.txt`, `baseline-dirty.diff`,
  `baseline-hashes.json` in the same directory.
- Scoped review packet:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/review-packet/`
  - `docs-ci-section.diff` — only the appended CI section of windows.md
    (pre-TASK baseline is the first 237 lines).
  - `worker.diff` — implementer's diff.
- Implementer evidence/report:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/` (`report.md`,
  `checks.md`, raw check logs, `git-status.txt`).
- Actual files and SHA-256 as recorded in `implementer/report.md`.

## What to verify

Check each frozen checklist item C1–C12. In particular verify by reading the
actual files (not trusting the report):

1. C1: workflow is valid YAML, `workflow_dispatch` only, one
   `windows-installer` job on `windows-latest`, `permissions: contents: read`;
   `.github/workflows/ci.yml` is unchanged from HEAD.
2. C2: pinned CPython `3.12.10` and EDB PostgreSQL `18.6-5` URLs and SHA-256
   match the recorded build-contract evidence; Inno Setup `6.7.3` is
   version-verified; build uses a fresh work dir; non-zero/hash mismatch fails.
3. C3: `ci-installer.ps1` guard runs before any side effect, requires
   `GITHUB_ACTIONS=true`, `CI=true`, `RUNNER_OS=Windows`,
   `RUNNER_ENVIRONMENT=github-hosted`, rejects `EDR-Win11-Test`/sandbox
   identities, requires absent work/install/`%ProgramData%\EDR`, and exits
   non-zero without creating anything. Confirm the negative-guard evidence is
   consistent and that no install occurred locally.
4. C4–C9 (cloud behavior): confirm the scripts implement silent install, file
   checks, installed-interpreter start, `/health`, UI root, synthetic
   document/PDF upload/download SHA-256, stop/restart/persistence SHA-256,
   clean stop, and `if: always()` artifact upload. These remain NOT_RUN.
5. C10: only the four allowlisted paths changed; protected files
   (`build.ps1`, `smoke.ps1`, `smoke.py`, `edr.iss`, `app/windows_local.py`,
   `app/windows_layout.py`, old tests, lockfiles, `.github/workflows/ci.yml`)
   are byte-unchanged from baseline/HEAD. Report any unexpected changed file.
6. C11: docs section is accurate, documents the pinned inputs and the explicit
   limits/NOT_RUN status.
7. C12: local checks (py_compile, PowerShell 5.1 parser, YAML parse, negative
   guard) are real and reproducible; the reported SHA-256 values match.

Evaluate these specific risks and give a severity for each:

- `packaging/windows/provision.ps1` calls `GetShellWindow()` and refuses install
  when no interactive shell exists. Is this a known packaging *bug* that must
  stop the cloud path (per the TASK rule "Product packaging bug findings must
  stop affected cloud path"), or an acceptable documented NOT_RUN cloud risk for
  READY_FOR_CLOUD_TESTING? Explain.
- Inno Setup has a pinned version but no pinned SHA-256.
- `-BuildWorkDirectory` is accepted by `ci-installer.ps1` but appears unused.
- `exit $LASTEXITCODE` propagation from the called PowerShell script in the
  workflow step.
- Whether any check could pass silently without actually testing the installed
  bundled runtime (fail-open risk).

## Verdict

Return exactly one verdict:

- **PASS** — all C1–C12 local criteria met, cloud items correctly NOT_RUN, only
  MINOR/NIT findings (list them); local result READY_FOR_CLOUD_TESTING.
- **FAIL** — any BLOCKER/MAJOR finding. List stable finding IDs (e.g.
  CI-C1-01), criterion, location, observed result, reproduction/evidence,
  expectation, severity, and whether the affected path must stop.

Do not accept a missing required local check. Do not invent results. Do not
grant a project/cloud PASS. End after the verdict using Orca `worker_done`
(outcome succeeded for PASS, failed for FAIL) with a three-sentence summary,
the verdict, findings, files inspected, and the evidence paths. Do not write any
file; the coordinator will persist your verdict.
