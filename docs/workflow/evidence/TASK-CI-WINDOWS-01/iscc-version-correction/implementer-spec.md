# Implementer spec — TASK-CI-WINDOWS-01 / A1 ISCC version-check correction

You are a separate OpenCode implementer. Work in
`D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`, HEAD
`44d7b65bd387b3ab0b670efcb2686c05d11290ae`. No native subagents. Do not
commit, push or run the workflow.

Read:
- `AGENTS.md`
- `docs/tasks/TASK-CI-WINDOWS-01.md`
- `docs/workflow/APPROVALS.md` §`CI_CLOUD_02_ISCC_VERSION_CHECK_CORRECTION_AUTHORIZED_20261104`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/CI-CLOUD-02-diagnosis.md`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/frozen-checklist.md`
  and `baseline-hashes.txt`
- `.github/workflows/windows-installer.yml`

## Change (strict allowlist)

1. `.github/workflows/windows-installer.yml` (required):
   - In `Install Inno Setup 6.7.3`, remove ONLY the invalid
     `(Get-Item $iscc).VersionInfo.FileVersion` + `^6\.7\.3` check and its
     `Write-Output "ISCC: $iscc ($version)"`. Keep the ISCC existence check,
     the official URL, the SHA-256 check, and the Authenticode
     `Status -eq 'Valid'` / `CN=Pyrsys B.V.` checks unchanged. Replace the
     removed output with `Write-Output "ISCC: $iscc"`.
   - In `Build installer`, after the existing `try { build.ps1 ... } catch
     { ...; throw }` block has completed successfully, before locating the EXE,
     add a fresh-log compiler-version check:
     ```powershell
     if (!(Test-Path -LiteralPath $buildLog -PathType Leaf)) {
         throw "Build log missing: $buildLog"
     }
     $compilerVersionLine = Select-String -LiteralPath $buildLog `
         -Pattern '^Compiler engine version: Inno Setup 6\.7\.3$' -Quiet
     if (-not $compilerVersionLine) {
         throw "ISCC compiler engine version line 'Inno Setup 6.7.3' not found in $buildLog"
     }
     Write-Output "ISCC compiler engine version verified from build log"
     ```
     Do not use `/Q` or `/Qp`; the exact line is emitted only in non-quiet
     builds. Do not change `build.ps1`.
2. `docs/installation/windows.md` (optional, targeted): update only CI item 3
   to say the compiler-engine version is verified from the successful build log
   line `Compiler engine version: Inno Setup 6.7.3`, not from `ISCC.exe`
   FileVersion. Do not change other documentation.

Do NOT edit `packaging/windows/build.ps1`, `edr.iss`, `provision.ps1`,
`ci-installer.ps1/.py`, `app/`, `frontend/`, lockfiles, tests, `.env`, the Inno
version/toolchain or any product prerequisite. Preserve all unrelated dirty and
untracked files.

## Local checks (no install, no product build/run)

Write evidence to
`docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/`
with exact commands, CWD and exit codes:

1. YAML parse + structural assertions: FileVersion check absent; new
   compiler-version check present after `build.ps1`/`Tee-Object`; exact pattern
   `^Compiler engine version: Inno Setup 6\.7\.3$`; URL/SHA/Authenticode/ISCC
   existence retained; `INNO_VERSION` 6.7.3; no `/Q`/`/Qp`; fresh `$logDir`
   guard retained.
2. `actionlint` on the workflow (portable binary may be at
   `C:\Users\user\AppData\Local\Temp\opencode\actionlint\actionlint.exe`; do not
   install tools).
3. Positive/negative version-signal proof (PowerShell 5.1 or 7):
   - positive: real existing
     `docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01/build.log` line
     `Compiler engine version: Inno Setup 6.7.3` → `Select-String ... -Quiet`
     True;
   - negative 6.7.4: temp log with `... Inno Setup 6.7.4` → False;
   - negative missing: temp log without the line → False;
   - failed-build control: a small harness that simulates a failing build
     (throws / non-zero native command) with the same try/catch-rethrow shape,
     and proves the version-check marker is never reached and the step exits
     non-zero. Record exact output/exit.
   - stale-log control: show the existing `$logDir` freshness guard would reject
     a pre-existing log (a temp directory with `build.log` + the same
     `Test-Path`/throw snippet → non-zero).
4. `git diff --check` scoped to the allowlisted files → 0; full-tree result may
   be non-zero only from pre-existing unrelated HISTORY blank-line dirt; record
   that fact. `git status --porcelain` recorded. Protected-file hashes vs
   `baseline-hashes.txt`: only allowlisted files may differ.
5. No host installation, no EDR/PostgreSQL app execution, no working DB, no VM.

## Evidence

- `report.md` — changes, commands/CWD/exit codes, checklist closure, effective
  model, residual risks.
- `checks.md` + raw logs (use `.txt` suffixes where practical so they are not
  git-ignored; if you use `.log`, ensure the coordinator can force-add them).
- `worker.diff` — exact diff of only allowlisted changes.
- `git-status.txt`.

Do not commit/push/run. Do not claim project/cloud PASS.

## Return

Send Orca `worker_done` with `--outcome succeeded` only if the correction and
local evidence are complete; otherwise `--outcome failed`. Three sentences:
what changed, what was verified, what remains (the single additional review,
then the separately approved commit/push/run). Include real
`--files-modified` and `--report-path`.
