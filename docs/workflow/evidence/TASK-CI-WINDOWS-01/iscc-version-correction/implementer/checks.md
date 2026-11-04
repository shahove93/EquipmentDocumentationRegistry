# TASK-CI-WINDOWS-01 / A1 ISCC version-check correction — implementer checks

All commands were run on the user host (win32, PowerShell 5.1.26100.9711),
CWD `D:\Antigravity\EquipmentDocumentationRegistry`, unless noted. Python is the
host CPython 3.12 with PyYAML 6.0.3. No host installation, product build/run,
EDR/PostgreSQL app execution, working DB or VM was used.

Evidence directory: `docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/`.

## 1. YAML parse + structural assertions

Command:

```powershell
$ev='docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer'; python "$ev/check_static.py" 2>&1 | Tee-Object -FilePath "$ev/01-static.txt"; Write-Output "EXIT=$LASTEXITCODE"
```

CWD: repo root. **Exit 0**. Log `01-static.txt`.

18/18 checks passed: YAML parses; `VersionInfo.FileVersion` and the old
`Installed ISCC version is not 6.7.3` throw are absent; the compiler-version
check appears after `Tee-Object -FilePath $buildLog`; exact pattern
`-Pattern '^Compiler engine version: Inno Setup 6\.7\.3$' -Quiet` present;
`Select-String` on `$buildLog`; build-log existence guard; official immutable
URL; `INNO_SETUP_SHA256` `9C73C3…B732`; Authenticode `Status -eq 'Valid'`;
`CN=Pyrsys B.V.`; ISCC existence check; simplified `Write-Output "ISCC: $iscc"`;
`INNO_VERSION` 6.7.3; no `/Q` or `/Qp`; fresh `$logDir` guard; `$buildLog`
created in the same step; try/catch rethrow shape retained.

## 2. actionlint

Command:

```powershell
$ev='docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer'; & 'C:\Users\user\AppData\Local\Temp\opencode\actionlint\actionlint.exe' .github/workflows/windows-installer.yml 2>&1 | Tee-Object -FilePath "$ev/02-actionlint.txt"; Write-Output "EXIT=$LASTEXITCODE"
```

CWD: repo root. **Exit 0**, no diagnostics. actionlint 1.7.12 (pre-existing
portable binary; nothing installed). Log `02-actionlint.txt`.

## 3. Positive/negative version-signal proof (PowerShell 5.1)

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/03-version-signal.ps1" 2>&1 | Tee-Object -FilePath "docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/03-version-signal.txt"; Write-Output "EXIT=$LASTEXITCODE"
```

CWD: repo root. **Exit 0**. Log `03-version-signal.txt`.

```text
positive_real_6.7.3=True (…\docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01\build.log)
negative_synthetic_6.7.4=False (…\Temp\iscc-signal-…\build-6.7.4.log)
negative_missing_line=False (…\Temp\iscc-signal-…\build-missing.log)
RESULT=PASS
```

## 4. Failed-build control

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/04-failed-build-control.ps1" 2>&1 | Tee-Object -FilePath "docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/04-failed-build-control.txt"; Write-Output "EXIT=$LASTEXITCODE"
```

CWD: repo root. **Exit 1**. Log `04-failed-build-control.txt`.

Harness runs `cmd.exe /c "exit 7"`, throws on `$LASTEXITCODE`, appends the
error to the log and rethrows inside the same try/catch shape as the workflow.
Output shows `native command failed with exit code 7`; the version-check markers
(`MARKER_VERSION_CHECK_REACHED`, `MARKER_VERSION_CHECK_REACHED_AFTER_CATCH`) are
absent (checked: `MARKER_PRESENT=False`). The step exits non-zero, so no
version check can run after a failed build.

## 5. Stale-log control

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/05-stale-log-control.ps1" 2>&1 | Tee-Object -FilePath "docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/05-stale-log-control.txt"; Write-Output "EXIT=$LASTEXITCODE"
```

CWD: repo root. **Exit 1**. Log `05-stale-log-control.txt`.

A temp `$logDir` is pre-created with a `build.log` containing the passing
line. `stale_log_pre_exists=True`; the retained
`if (Test-Path -LiteralPath $logDir) { throw "Build log directory must be fresh: $logDir" }`
guard throws and the step exits 1; `MARKER_GUARD_BYPASSED` is absent
(`GUARD_BYPASS_MARKER_PRESENT=False`). A pre-existing log cannot satisfy the
check.

## 6. Scoped diff check

Command:

```powershell
git --no-pager diff --check -- .github/workflows/windows-installer.yml docs/installation/windows.md
```

CWD: repo root. **Exit 0**. Log `06-diff-check-scoped.txt`. (Git prints a benign
CRLF-normalization warning for `docs/installation/windows.md` on stderr.)

## 7. Full-tree diff check (pre-existing unrelated dirt)

Command:

```powershell
git --no-pager diff --check
```

CWD: repo root. **Exit 2**, sole finding
`docs/workflow/HISTORY.md:2262: new blank line at EOF.` — pre-existing unrelated
dirty content, untouched by this task. Log `07-diff-check-full.txt`.

## 8. git status

Command:

```powershell
git status --porcelain
```

CWD: repo root. **Exit 0**. Full output in `git-status.txt` (pre-existing dirty
and untracked files preserved; this task only adds/modifies the two allowlisted
files and the implementer evidence directory).

## 9. Protected-file hashes vs baseline

Command (loops over `baseline-hashes.txt` and compares `Get-FileHash -Algorithm SHA256`):

```powershell
$base='docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/baseline-hashes.txt'; foreach ($line in Get-Content -LiteralPath $base) { if ($line -match '^([0-9A-F]{64})\s+(.+)$') { $exp=$Matches[1]; $path=$Matches[2].Trim(); $act=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash; $status = if ($act -eq $exp) {'SAME'} else {'CHANGED'}; "$status  $act  $path" } }
```

CWD: repo root. **Exit 0**. Log `08-hashes.txt`.

Only the two allowlisted files changed:

```text
CHANGED  34C3BECBCD38768DA1F3A7517F82F0A5E128EF7738DCF36DAC74FBAE71418252  .github/workflows/windows-installer.yml
CHANGED  36248CC68C96C9EAC58EC67D7563BFD0889F2D34D61DAED57875B624D7FB41CD  docs/installation/windows.md
SAME  packaging/windows/build.ps1
SAME  packaging/windows/edr.iss
SAME  packaging/windows/ci-installer.ps1
SAME  packaging/windows/ci-installer.py
SAME  app/windows_local.py
SAME  app/windows_layout.py
```
