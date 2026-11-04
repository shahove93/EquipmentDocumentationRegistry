# TASK-CI-WINDOWS-01 C1 (A1) — implementer report

- Worktree: `D:/Antigravity/EquipmentDocumentationRegistry`
- Branch: `main`
- HEAD: `dccb14554cca3f688f20153f1f3eb41195740319`
- Effective model: `deepseek/deepseek-flash`
- Role: implementer (not coordinator, no project PASS assigned)
- Result: **READY_FOR_CLOUD_TESTING** (actual GitHub run **NOT_RUN**)
- All commands below ran with CWD `D:\Antigravity\EquipmentDocumentationRegistry`
  unless stated otherwise.
- Host: Windows, Windows PowerShell 5.1, host Python 3.12.4, PyYAML 6.0.3.
- No installer, installed app, PostgreSQL lifecycle or Product install was run on
  this host. `%ProgramData%\EDR` was not created.

## Files created / edited (allowlist only)

| Change | Path | SHA-256 |
|--------|------|---------|
| CREATE | `.github/workflows/windows-installer.yml` | `3C69EBD58602FC846C8D3B3B9E269313ECF85BE268343601ED66217F2D3DE15C` |
| CREATE | `packaging/windows/ci-installer.ps1` | `B1D34ECE4109B63EE8CCBD4C1F680FEBA2EC3EF3EFA509C798490988CBCBAB8A` |
| CREATE | `packaging/windows/ci-installer.py` | `5EC794D5BC39ABD5772639BE1F9B28BA08CF772F92EF1F049442F75DE51B9FA5` |
| EDIT | `docs/installation/windows.md` (added CI section) | `9F93F611DDE7C685CBFA81CF0BD414FB1321A1C918FAF7005A6C4685368D71B8` |
| CREATE | `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/*` | this evidence directory |

No other file was written by this worker.

## What was implemented

1. **`.github/workflows/windows-installer.yml`**
   - `workflow_dispatch` only; top-level `permissions: contents: read`;
     dedicated `concurrency` group; single job `windows-installer` on
     `windows-latest`.
   - Checkout with `persist-credentials: false`; `actions/setup-python@v7`
     `3.12.10`; `actions/setup-node@v7` `24.22.0`; `npm ci` + `npm run build`
     in `frontend`.
   - Downloads the pinned CPython embedded `3.12.10` amd64 and EDB PostgreSQL
     `18.6-5` x64 binaries zips into a fresh `$RUNNER_TEMP\build-inputs` and
     verifies SHA-256 with `Get-FileHash -Algorithm SHA256`, failing closed:
     - `python-3.12.10-embed-amd64.zip` →
       `4ACBED6DD1C744B0376E3B1CF57CE906F9DC9E95E68824584C8099A63025A3C3`
     - `postgresql-18.6-5-windows-x64-binaries.zip` →
       `E2246BA91D22345BC3D017586C09EDE52D9DF180B1EEB480F050445F1CAD84E2`
     Both values are copied from `TASK-WINDOWS-CRT-OFFLINE-01/manifest.json` and
     `TASK-WINDOWS-PROGRAMDATA-01-A1-C1-prerequisites/build-manifest.json`.
   - Installs Inno Setup `6.7.3` from
     `https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe`, resolves
     `ISCC.exe`, and fails unless its `FileVersion` matches `6.7.3`.
   - Runs `packaging/windows/build.ps1` with a fresh `-WorkDirectory`, the
     downloaded archives, `frontend/dist`, the resolved ISCC and the
     `setup-python` interpreter (`-BuilderPython`), teeing output to
     `build.log`. Then records EXE path/size/SHA-256 into
     `$RUNNER_TEMP\edr-build\installer-exe.json` and `.sha256`.
   - Runs `packaging/windows/ci-installer.ps1` with `powershell` (5.1) and
     propagates its exit code.
   - `if: always()` uploads `edr-ci-work` (install log, results JSON,
     app/PostgreSQL logs), built EXE, EXE metadata/hash, `build-manifest.json`
     and `build.log`; retention 14 days.
   - Existing `.github/workflows/ci.yml` is untouched.

2. **`packaging/windows/ci-installer.ps1`**
   - Fail-closed guard executes before any directory creation, install or
     process start. Requires `GITHUB_ACTIONS=true`, `CI=true`,
     `RUNNER_OS=Windows`, `RUNNER_ENVIRONMENT=github-hosted`; rejects
     `COMPUTERNAME` equal (case-insensitive) to `EDR-Win11-Test`, `WDAG*`, the
     `WDAGUtilityAccount` identity, absent `ProgramData`, existing work/install
     paths, existing `%ProgramData%\EDR`, and a missing EXE. On failure it
     writes one line per issue to stderr and exits `2` without creating
     anything.
   - Parameters for EXE, work directory, install directory and build work
     directory (temp-based defaults).
   - Silent install with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART
     /DIR="<install>" /LOG="<work>\install.log"`, failing on non-zero exit.
   - Verifies `<install>\python\python.exe`, `<install>\launcher.ps1`,
     `<install>\alembic.ini`, `<install>\ui\index.html`, and
     `%ProgramData%\EDR\runtime\postgresql\bin\postgres.exe`.
   - Runs `ci-installer.py` with the **installed** interpreter
     (`<install>\python\python.exe -B <repo>\packaging\windows\ci-installer.py
     --install <install> --work <work>`), propagates its exit code, and copies
     `%ProgramData%\EDR\state\data\logs\*` into `<work>\logs` in `finally`
     (success or failure). Work directory is kept.

3. **`packaging/windows/ci-installer.py`**
   - Standard library only; starts the installed app exactly like `smoke.py`:
     `Popen([<install>/python/python.exe, '-B', '-m', 'app.windows_local',
     'start', '--no-browser'], cwd=<install>)`, polls
     `http://127.0.0.1:18765/health` up to 120 s, fails on early process exit or
     timeout.
   - Asserts `GET /` with `Accept: text/html` contains `<div id="root">`.
   - Creates synthetic `POST /document-types`, `POST /documents`, uploads a
     small synthetic PDF via multipart `POST /documents/{id}/files`, downloads
     `GET /documents/{id}/files/{file_id}/content`, and compares SHA-256.
   - Stops with `<install>/python/python.exe -B -m app.windows_local stop`,
     asserts supervisor exit `0`, restarts, asserts `GET /documents/{id}`
     persists and the re-downloaded attachment SHA-256 is unchanged, stops
     again.
   - Writes `results.json` (check name, argv, cwd, exit, stdout/stderr where
     relevant, IDs, SHA-256) after every event; on failure writes a partial
     `FAILED` event and exits non-zero. No UAC, no
     backup/restore/update/uninstall/reinstall, no production data, no
     hardcoded user paths.

4. **`docs/installation/windows.md`**
   - Added section "Проверка установщика в GitHub Actions (Windows CI)":
     trigger, pinned runtime versions and SHA-256, build → silent install →
     installed-runtime start → health/UI → synthetic upload/download →
     restart/persistence, artifact list, and explicit limits (interactive UAC,
     clean end-user PC, full lifecycle, cloud status **NOT_RUN**).

## Local checks (exact commands, CWD, exit codes)

All commands run from `D:\Antigravity\EquipmentDocumentationRegistry`.

| Check | Exact command | Exit | Log |
|-------|---------------|------|-----|
| Python syntax | `python -m py_compile packaging/windows/ci-installer.py` | `0` | `check-pycompile.txt` |
| PowerShell parser (5.1) | `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <temp>\edr-ci-ps-parse-check.ps1` where the script calls `[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'packaging/windows/ci-installer.ps1').Path, [ref]$null, [ref]$errors)` and exits 1 on any error | `0` (`PARSER_OK errors=0`) | `check-ps-parser.txt` |
| YAML parse | `python -c "import yaml; ..."` loading `.github/workflows/windows-installer.yml`, asserting one `windows-installer` job, `workflow_dispatch`, and an `if: always()` upload-artifact step | `0` | `check-yaml.txt` |
| Negative guard | `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File packaging/windows/ci-installer.ps1 -Exe <missing> -WorkDirectory <fresh> -InstallDirectory <fresh>` with `GITHUB_ACTIONS`, `CI`, `RUNNER_OS`, `RUNNER_ENVIRONMENT` unset | script `2` (test passes) | `check-negative-guard.txt` |
| Protected hashes | compare C10-protected files with `baseline-hashes.json` + `git diff --name-status` | matches (see log) | `check-protected-hashes.txt` |

Negative guard result: exit `2`, stderr listed all four missing CI env markers,
`INSTALL_DIR_CREATED=False`, `WORK_DIR_CREATED=False`. Nothing was installed.

The generated `packaging/windows/__pycache__/ci-installer.cpython-312.pyc` from
`py_compile` was removed afterwards; `__pycache__` is git-ignored.

## Diff and status

- `worker.diff` contains the exact diff for the four allowlisted paths
  (verified valid UTF-8; includes the full new files and the docs section).
- `git-status.txt` is `git status --porcelain` after the work.
- `check-protected-hashes.txt` shows `build.ps1`, `smoke.ps1`, `smoke.py`,
  `edr.iss`, `app/windows_local.py`, `app/windows_layout.py` all byte-identical
  to baseline, and `.github/workflows/ci.yml` has no tracked diff.

### Baseline drift observed (not written by this worker)

Comparing current files to `baseline-hashes.json` shows three changed paths:
`docs/installation/windows.md` (intentional allowlisted edit), and
`docs/workflow/HISTORY.md` / `docs/workflow/STATE.md`. The latter two have
`LastWriteTime` 20:10, before this worker's first write (20:12), and this
worker never opened them for writing; they are coordinator-owned workflow
records updated during dispatch. No prior evidence file was modified.

## Findings / residual risks (cloud only, NOT_RUN)

1. **Interactive-shell requirement in `provision.ps1`.** The installer's
   `PrepareToInstall` runs `provision.ps1`, which calls `GetShellWindow()` and
   refuses installation when no interactive shell exists ("No interactive
   shell; installation refused"). A headless `windows-latest` runner may not have
   `explorer.exe` in session 1, so the cloud silent install may fail at this
   documented but untested boundary. This is outside this TASK's allowlist
   (`provision.ps1`/`edr.iss` must not be edited) and is reported as a finding.
2. **Elevation context.** A GitHub-hosted Windows runner is expected to run
   elevated and with UAC disabled; if that assumption does not hold,
   `Start-Process` of the `PrivilegesRequired=admin` installer fails. Not
   verifiable locally.
3. **Pinned URLs.** Input SHA-256 values are authoritative from recorded
   evidence. Inno Setup has no recorded SHA-256, so `6.7.3` is enforced only by
   version (`FileVersion` of `ISCC.exe`). URL availability is verified only at
   cloud run time.
4. The installer itself fetches `vc_redist.x64.exe` through the existing
   `fetch-vcredist.ps1` (Microsoft URL + Authenticode); this requires runner
   network access and is unchanged by this TASK.

## Explicit non-claims

- No project PASS is claimed; only **READY_FOR_CLOUD_TESTING**.
- Actual cloud job status: **NOT_RUN**.
- Real interactive UAC, clean end-user PC installation and full lifecycle
  (backup/restore/update/uninstall/reinstall, ACL/migration matrix) are not
  verified.
- No commit, push, tag or remote state change was made.
