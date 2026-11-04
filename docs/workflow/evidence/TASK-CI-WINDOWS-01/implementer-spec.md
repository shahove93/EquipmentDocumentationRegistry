# Implementer spec — TASK-CI-WINDOWS-01 C1 (A1)

You are a separate OpenCode implementer in the existing worktree
`D:/Antigravity/EquipmentDocumentationRegistry` on branch `main`
(HEAD `dccb14554cca3f688f20153f1f3eb41195740319`). You are NOT the coordinator
and you cannot assign project PASS. Do not use native subagents: do this work
yourself in this session.

Before editing, read:
- `AGENTS.md`
- `docs/tasks/TASK-CI-WINDOWS-01.md`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/baseline-hashes.json`,
  `baseline-dirty.diff`, `baseline-status.txt`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/frozen-checklist.md`
- existing `.github/workflows/ci.yml`, `packaging/windows/build.ps1`,
  `packaging/windows/smoke.ps1`, `packaging/windows/smoke.py`,
  `packaging/windows/edr.iss`, `packaging/windows/provision.ps1`,
  `packaging/windows/launcher.ps1`, `docs/installation/windows.md`,
  `app/windows_local.py`.
- Existing build-contract evidence for pinned inputs:
  `docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01/manifest.json` and
  `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01-A1-C1-prerequisites/build-manifest.json`.

## Goal

Create a GitHub Actions Windows job that builds the installer, silently
installs it in the same ephemeral hosted runner, starts the installed app with
its bundled interpreter/PostgreSQL, checks health and UI, creates synthetic
document + PDF attachment, verifies attachment SHA-256, restarts, verifies
persistence and SHA-256 again. Local preparation only.

## Files you may create/edit (strict allowlist)

- CREATE `.github/workflows/windows-installer.yml`
- CREATE `packaging/windows/ci-installer.ps1`
- CREATE `packaging/windows/ci-installer.py` (or other `ci-*.py` name)
- EDIT `docs/installation/windows.md` (add a CI section)
- Evidence/report only under `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/`

You must NOT edit `app/`, `frontend/`, `packaging/windows/edr.iss`,
`packaging/windows/build.ps1`, `packaging/windows/smoke.ps1`,
`packaging/windows/smoke.py`, other old packaging tests, lockfiles, `.env`,
`.github/workflows/ci.yml`, or any prior evidence. Preserve all existing dirty
and untracked files exactly.

## Requirements

1. `.github/workflows/windows-installer.yml`
   - Trigger `workflow_dispatch` only (opt-in; no unexpected heavy runs).
   - `permissions: contents: read`; a concurrency group; `windows-latest`.
   - One `windows-installer` job:
     * checkout with `persist-credentials: false`;
     * `actions/setup-python@v7` with `3.12.10` (builder; build.ps1 requires 3.12);
     * frontend: `actions/setup-node@v7` `24.22.0`, `npm ci`, `npm run build`
       in `frontend`;
     * download the pinned CPython embeddable `3.12.10` amd64 zip and EDB
       PostgreSQL `18.6-5` Windows x64 binaries zip from their official URLs
       into a fresh temp `build-inputs` directory, and `Get-FileHash -Algorithm
       SHA256` each; fail closed on mismatch. Pin exactly the SHA-256 values
       recorded in the existing build-contract evidence above (do not invent
       hashes; if the recorded evidence does not contain a needed value, stop
       and report the gap instead of fabricating).
     * install Inno Setup exactly `6.7.3` (deterministic, version-verified; fail
       closed if the installed ISCC is not 6.7.3) and resolve `ISCC.exe`.
     * run `packaging/windows/build.ps1` with a fresh `-WorkDirectory`, the
       downloaded archives, built `frontend/dist`, resolved ISCC, and
       `-BuilderPython` from setup-python.
     * record built EXE path, size and SHA-256 to the work directory.
     * run `packaging/windows/ci-installer.ps1` for install + runtime checks.
     * upload artifacts with `if: always()`: install log, app/PostgreSQL logs,
       results JSON, EXE, EXE SHA-256, build manifest/log. Reasonable retention.
   - Do not modify the existing Ubuntu `ci.yml` jobs.

2. `packaging/windows/ci-installer.ps1`
   - Begin with a fail-closed guard that runs BEFORE any directory creation,
     install or process start. Require ALL of:
     `$env:GITHUB_ACTIONS -eq 'true'`, `$env:CI -eq 'true'`,
     `$env:RUNNER_OS -eq 'Windows'`,
     `$env:RUNNER_ENVIRONMENT -eq 'github-hosted'`.
     Reject `COMPUTERNAME` equal to (case-insensitive) `EDR-Win11-Test` or any
     `WDAG*` sandbox. Require fresh, absent work/install paths and an absent
     `%ProgramData%\EDR` (before install). On guard failure: write a clear
     message to stderr, exit non-zero, create nothing.
   - Accept parameters for built EXE, work directory, install directory and
     build work directory (give sensible defaults from env/temp).
   - Silent install:
     `Start-Process <exe> -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES',
     '/NORESTART','/DIR=<install>','/LOG=<work>/install.log') -Wait -PassThru`,
     fail on non-zero exit; never install on host outside the guard.
   - Verify installed files: `<install>\python\python.exe`,
     `<install>\launcher.ps1`, `<install>\alembic.ini`,
     `<install>\ui\index.html`, and
     `%ProgramData%\EDR\runtime\postgresql\bin\postgres.exe`.
   - Invoke `ci-installer.py` with the INSTALLED interpreter
     (`<install>\python\python.exe -B <repo>\packaging\windows\ci-installer.py
     --install <install> --work <work>`), propagate its exit code.
   - Keep the work directory on failure; copy app/PostgreSQL logs from
     `%ProgramData%\EDR\state\data\logs\` into the work directory when present.

3. `ci-installer.py` (executed by the installed bundled Python)
   - Start the installed app exactly as `smoke.py` does:
     `subprocess.Popen([<install>/python/python.exe, '-B', '-m',
     'app.windows_local', 'start', '--no-browser'], cwd=<install>, ...)`,
     poll `http://127.0.0.1:18765/health` for `{"status":"ok"}` with a bounded
     timeout (e.g. 120 s), fail on process exit/timeout.
   - Assert UI: `GET /` with `Accept: text/html` contains `<div id="root">`.
   - Synthetic data only: POST `/document-types`, POST `/documents`, upload a
     small synthetic PDF via multipart `POST /documents/{id}/files`, then
     `GET /documents/{id}/files/{file_id}/content`; assert downloaded SHA-256
     equals the uploaded bytes' SHA-256.
   - Stop via `<install>/python/python.exe -B -m app.windows_local stop`,
     assert supervisor exit 0; start again; assert `GET /documents/{id}` still
     returns the document and the re-downloaded attachment SHA-256 is unchanged;
     stop again.
   - Write `results.json` (list of events: check name, command, cwd, exit code,
     stdout/stderr where relevant, document/file IDs, SHA-256) into the work
     directory. On failure write partial results and exit non-zero.
   - No UAC interaction, no backup/restore/update/uninstall/reinstall, no
     production data, no hardcoded user paths.

4. `docs/installation/windows.md`
   - Add a section describing the CI job: trigger, pinned runtime versions and
     SHA-256, build -> silent install -> installed-runtime start -> health/UI ->
     synthetic upload/download -> restart/persistence, artifacts on failure.
   - State explicitly what is NOT verified: real interactive UAC, clean
     end-user PC, full lifecycle; and that the actual cloud run status is
     NOT_RUN until a real run happens.

## Local evidence you must produce (no product install on this host)

Write to `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/`:
- `report.md` with exact commands, CWD, exit codes, results, files created and
  any deviations.
- `checks.md` (or logs) with:
  * `python -m py_compile packaging/windows/ci-installer.py` (or your filename);
  * PowerShell parser check of `ci-installer.ps1` using Windows PowerShell 5.1:
    `[System.Management.Automation.Language.Parser]::ParseFile(...)` collecting
    `$errors` and failing on any parse error;
  * YAML parse of the workflow with host `python -c "import yaml; ..."` (host
    Python has PyYAML);
  * a negative guard test: run `ci-installer.ps1` with the GitHub env vars
    unset and assert non-zero exit AND that no install directory was created.
    This negative test must not install anything.
- `worker.diff` or an exact `git diff` of only your allowlisted changes.
- `git status --porcelain` proving no forbidden files changed.

Do NOT run the installer, app, or lifecycle on this host. Do NOT commit, push,
tag, or modify remote state. Do not claim project PASS; report
`READY_FOR_CLOUD_TESTING` or concrete findings.

## Return protocol

When done, use `orca orchestration send --type worker_done` from your dispatch
with `--outcome succeeded` only if the allowlisted files and local checks are
complete; use `--outcome failed` otherwise. Body: three sentences — what you
did, what you found/verified, what remains (cloud run NOT_RUN). Include
`--files-modified` with the real paths and `--report-path` pointing at your
report. Report your effective model ID and the exact local check exit codes.
