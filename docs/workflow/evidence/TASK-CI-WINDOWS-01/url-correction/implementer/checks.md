# Implementer checks — TASK-CI-WINDOWS-01 / A1 bounded correction (CI-CLOUD-01)

Effected by: OpenCode implementer, model `deepseek/deepseek-flash`.
Branch `main`, HEAD `11d66b1c8a86dd59b7b1d7e693f8c27f43796196`.
No commit, push or workflow run performed. No installer/app/PostgreSQL/VM/DB was
executed or installed.

All commands ran with CWD `D:\Antigravity\EquipmentDocumentationRegistry` unless
stated otherwise. Raw logs are in this directory.

## 1. YAML parse + structural assertions

- Command: `python docs\workflow\evidence\TASK-CI-WINDOWS-01\url-correction\implementer\check_yaml.py`
- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Interpreter: host Python 3.12.4, PyYAML 6.0.3
- Exit code: **0**
- Log: `yaml-check.log`
- Asserted (all PASS): trigger is `workflow_dispatch` only; `permissions.contents`
  is `read`; exactly one job `windows-installer`; `INNO_VERSION` is `6.7.3`;
  `INNO_SETUP_URL` equals the official immutable release URL;
  `INNO_SETUP_SHA256` equals `9C73C3…B732`; exactly one `upload-artifact` step
  with `if: always()`; single Inno install step; hash compare precedes
  `Start-Process`; hash mismatch throws; Authenticode `Status -eq 'Valid'` and
  `CN=Pyrsys B.V.` checks precede `Start-Process`; post-install ISCC
  `VersionInfo.FileVersion` `6.7.3` check retained.

## 2. actionlint

- Command: `& 'C:\Users\user\AppData\Local\Temp\opencode\actionlint\actionlint.exe' .github/workflows/windows-installer.yml`
- actionlint version: 1.7.12 (built with go1.26.1, windows/amd64)
- CWD: `D:\Antigravity\EquipmentDocumentationRegistry`
- Exit code: **0**
- Log: `actionlint.log`
- Portable binary was already present for diagnosis; nothing was installed.

## 3. Git hygiene and protected hashes

- `git diff --check` (whole dirty tree): exit **2**, caused only by a
  pre-existing unrelated dirty file `docs/workflow/HISTORY.md:2192: new blank
  line at EOF` (HISTORY.md was already modified before this task; not touched).
- `git diff --check -- .github/workflows/windows-installer.yml docs/installation/windows.md`
  (allowlisted files only): exit **0**.
- `git status --porcelain`: recorded in `git-status.txt`; all pre-existing
  dirty/untracked files preserved.
- Protected-file SHA-256 vs `baseline-hashes.txt`: only the two allowlisted files
  differ; the other 8 protected files (build.ps1, edr.iss, ci-installer.ps1/.py,
  app/windows_local.py, app/windows_layout.py, smoke.ps1, smoke.py) are
  byte-identical to baseline.
  - `windows-installer.yml`: base `7A256F57…DA21` → now `DA22EDF5E8A00E291667FA7DC38C8ADEAF40B96CC9761CDB2B2424844D8FEBCB`
  - `docs/installation/windows.md`: base `E6836628…881E` → now `CFC8BC96685FE156E228F7B6D316E261A649D2B6190F187CEF6EFC0B0EAE6D41`
- Log: `git-checks.log`

## 4. Fail-closed proof (PowerShell 5.1)

- Harness: `fail-closed-proof.ps1` reproduces the workflow's hash/signature
  logic verbatim. It never installs or executes the target file.
- Installer inspected: `C:\Users\user\AppData\Local\Temp\opencode\inno-diag\innosetup-6.7.3.exe`
  (official 6.7.3 artifact downloaded for the C3 diagnosis).
- PowerShell version: 5.1.26100.9711
- Case `correct` (pinned hash + valid signature):
  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <harness> -Setup <installer> -Mode correct`
  → actual SHA-256 `9C73C3BA…B732`, status `Valid`, signer
  `CN=Pyrsys B.V., O=Pyrsys B.V., S=Noord-Holland, C=NL`,
  `VERIFICATION_OK`, exit **0**.
- Case `wrong-hash` (expected hash zeroed):
  → `throw "SHA-256 mismatch …"`, exit **1** (non-zero captured).
- Log: `fail-closed-proof.log`

## 5. Not run

Installer execution, EDR app, PostgreSQL, VM, working DB, cloud workflow — NOT
RUN. No project or cloud PASS is claimed; this is correction-complete with local
static evidence only.
