# TASK-CI-WINDOWS-01 C2 — local static checks

CWD for every command below: `D:\Antigravity\EquipmentDocumentationRegistry`.
Host: Windows; Windows PowerShell 5.1.26100.9711; Python 3.12.4; PyYAML 6.0.3;
`pwsh` (PowerShell 7) is not installed on this host. No installer, app,
PostgreSQL lifecycle or product install was run. Nothing was installed.

This C2 revision replaces the C1 command list that contained `<temp>` and
`...` placeholders (closure of CI-C12-01). Every command below is literal.

## 1. Python syntax (`py_compile`)

```
python -m py_compile packaging/windows/ci-installer.py
```

- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Exit code: **0**
- Raw output: `check-c2-pycompile.txt` (exit `0`, no output)
- Note: `ci-installer.py` is byte-unchanged in C2
  (SHA-256 `5EC794D5BC39ABD5772639BE1F9B28BA08CF772F92EF1F049442F75DE51B9FA5`).

## 2. PowerShell 5.1 parser check (`ci-installer.ps1`)

Helper script: `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/parse-ci-installer.ps1`.

```
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/parse-ci-installer.ps1
```

- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Exit code: **0**
- Output: `PARSER_OK errors=0`
- Raw output: `check-c2-ps-parser.txt`

The helper resolves the repository root from `$PSScriptRoot`
(`../../../../..`) and calls
`[System.Management.Automation.Language.Parser]::ParseFile(<repo>\packaging\windows\ci-installer.ps1, [ref]$null, [ref]$errors)`,
exiting `1` on any parse error.

## 3. Workflow YAML parse and structure

Helper script: `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/check-yaml.py`.

```
python docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/check-yaml.py
```

- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Exit code: **0**
- Output: `YAML_OK jobs=windows-installer trigger=workflow_dispatch upload_artifact_if_always=true frontend_shell=pwsh last_exitcode_checks=2 buildworkdirectory_arg=absent`
- Raw output: `check-c2-yaml.txt`

Assertions: PyYAML `safe_load`; one job `windows-installer` on
`windows-latest`; `permissions: contents: read`; `workflow_dispatch` trigger;
`actions/upload-artifact` step with `if: always()`; the `Build frontend` step
uses `shell: pwsh` and has exactly two `$LASTEXITCODE -ne 0` guards with the
first preceding `npm run build`; the silent-install step no longer passes
`-BuildWorkDirectory`. PyYAML (YAML 1.1) decodes the unquoted `on:` key as
`True`, so the script reads the trigger via `data[True]`; GitHub Actions
interprets the file as `workflow_dispatch`.

## 4. Frontend step fails closed (CI-C2-01)

Helper script: `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/check-frontend-exit.ps1`.

```
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/check-frontend-exit.ps1
```

- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Exit code: **1** (non-zero = the corrected step fails closed; this is the
  expected result)
- Raw transcript: `check-c2-frontend-exit.txt`

The probe mirrors the workflow pattern: `cmd /c exit 7`; explicit
`$LASTEXITCODE` throw; `cmd /c exit 0`. The first failure aborts the script, so
the outer exit is `1`. A control with only the two `cmd /c` calls (no checks)
exits `0`, reproducing the C1 fail-open behavior. Because `pwsh` is not
installed on this host the probe ran under Windows PowerShell 5.1, whose native
exit-code semantics are identical; the workflow itself uses `shell: pwsh`.

## 5. Negative guard (C3), reproducible

Preparation and invocation (exact commands):

```
$base = Join-Path $env:TEMP 'edr-ci-c2-negative'
if (Test-Path -LiteralPath $base) { Remove-Item -LiteralPath $base -Recurse -Force }
Remove-Item Env:GITHUB_ACTIONS,Env:CI,Env:RUNNER_OS,Env:RUNNER_ENVIRONMENT -ErrorAction SilentlyContinue
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File packaging/windows/ci-installer.ps1 -Exe (Join-Path $env:TEMP 'edr-ci-c2-negative\missing.exe') -WorkDirectory (Join-Path $env:TEMP 'edr-ci-c2-negative\work') -InstallDirectory (Join-Path $env:TEMP 'edr-ci-c2-negative\install')
```

- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Script exit code: **2** (non-zero, as required)
- `INSTALL_DIR_CREATED=False`; `WORK_DIR_CREATED=False`
- Raw transcript: `check-c2-negative-guard.txt`

The guard reports the four missing CI environment markers and the missing EXE,
then exits `2` before any directory creation, install or process start.

## 6. Protected files / status

```
git status --porcelain
```

- Raw output: `git-status.txt`
- `build.ps1`, `smoke.ps1`, `smoke.py`, `edr.iss`, `app/windows_local.py`,
  `app/windows_layout.py`, old tests, lockfiles and `.github/workflows/ci.yml`
  were not modified by this worker. Prior `check-protected-hashes.txt` remains
  valid; `ci-installer.py` is byte-unchanged.
- `worker-c2.diff` — exact C2 diff for the three allowlisted changed paths
  (`.github/workflows/windows-installer.yml`,
  `packaging/windows/ci-installer.ps1`, `docs/installation/windows.md`).

## Summary

| Check | Exit | Status |
|-------|------|--------|
| `py_compile ci-installer.py` | 0 | PASS |
| PowerShell 5.1 parser `ci-installer.ps1` | 0 | PASS |
| Workflow YAML parse + structure | 0 | PASS |
| Frontend step fails closed (expected non-zero) | 1 | PASS |
| Negative guard (expected non-zero) | 2 | PASS |
| Protected hashes / status | - | unchanged |
