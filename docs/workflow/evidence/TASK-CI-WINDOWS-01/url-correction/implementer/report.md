# Implementer report — TASK-CI-WINDOWS-01 / A1 bounded correction (CI-CLOUD-01)

- Logical TASK/A1 bounded correction under
  `CI_CLOUD_01_URL_CORRECTION_AND_RETRY_AUTHORIZED_20261104`.
- Effective model: **`deepseek/deepseek-flash`** (OpenCode implementer).
- Branch `main`, HEAD `11d66b1c8a86dd59b7b1d7e693f8c27f43796196`.
- Outcome: **correction-complete with local evidence**; no project/cloud PASS,
  no commit/push/workflow run.
- Evidence: `checks.md`, `yaml-check.log`, `actionlint.log`, `git-checks.log`,
  `fail-closed-proof.log`, `worker.diff`, `git-status.txt`, plus the helper
  scripts `check_yaml.py` and `fail-closed-proof.ps1`.

## What changed

Allowlisted changes only:

1. `.github/workflows/windows-installer.yml`
   - kept `INNO_VERSION: '6.7.3'`;
   - `INNO_SETUP_URL` → `https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe`;
   - added `INNO_SETUP_SHA256: '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732'`;
   - in `Install Inno Setup 6.7.3`, after `Invoke-WebRequest` and before
     `Start-Process`, added fail-closed `Get-FileHash -Algorithm SHA256`
     comparison and `Get-AuthenticodeSignature` status `Valid` +
     `SignerCertificate.Subject` match `CN=Pyrsys B.V.`;
   - the post-install `ISCC.exe` `VersionInfo.FileVersion` `6.7.3` check and all
     other steps/guards are unchanged.
2. `docs/installation/windows.md`
   - only CI section item 3 updated to state the official immutable GitHub
     release URL plus SHA-256/Authenticode verification.

No other file was edited. `worker.diff` contains exactly these two files.

## Commands, CWD, exit codes

All CWD `D:\Antigravity\EquipmentDocumentationRegistry`.

| # | Command | Exit |
|---|---------|------|
| 1 | `python docs\workflow\evidence\TASK-CI-WINDOWS-01\url-correction\implementer\check_yaml.py` | 0 |
| 2 | `& 'C:\Users\user\AppData\Local\Temp\opencode\actionlint\actionlint.exe' .github/workflows/windows-installer.yml` | 0 |
| 3a | `git diff --check` (whole dirty tree) | 2 (pre-existing `HISTORY.md` blank line at EOF, unrelated, untouched) |
| 3b | `git diff --check -- .github/workflows/windows-installer.yml docs/installation/windows.md` | 0 |
| 3c | `git status --porcelain` | 0 (recorded) |
| 3d | protected-file SHA-256 vs `baseline-hashes.txt` | only the two allowlisted files differ |
| 4a | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <harness> -Setup <installer> -Mode correct` | 0 |
| 4b | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <harness> -Setup <installer> -Mode wrong-hash` | 1 (expected throw) |

The fail-closed positive case verified on the official installer: SHA-256
`9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`,
Authenticode `Valid`, signer `CN=Pyrsys B.V., O=Pyrsys B.V., S=Noord-Holland, C=NL`.
No install or execution occurred.

## Frozen checklist closure (C1–C9)

- **C1** — Only the workflow and a targeted CI note in `docs/installation/windows.md`
  changed; other protected files are byte-identical to baseline. PASS (local).
- **C2** — `INNO_VERSION` still `6.7.3`; URL is exactly the official immutable
  release URL. PASS.
- **C3** — `INNO_SETUP_SHA256` pinned; `Get-FileHash` check before execution
  throws on mismatch (wrong-hash case exit 1). PASS.
- **C4** — `Get-AuthenticodeSignature` requires `Status -eq 'Valid'` and signer
  subject `CN=Pyrsys B.V.` before `Start-Process`; failure throws. Positive case
  reported `Valid`/`Pyrsys B.V.`. PASS.
- **C5** — Post-install ISCC `VersionInfo.FileVersion` `6.7.3` check unchanged. PASS.
- **C6** — No TLS/signature/runner guard weakening, no version change, no product
  dependency/prerequisite change, no new secret, no host install. PASS.
- **C7** — YAML parses; actionlint 1.7.12 exit 0; structural assertions all pass;
  doc note states official URL + SHA. PASS.
- **C8** — Fail-closed proof: correct hash + valid signature → success (exit 0);
  wrong expected hash → throws (exit 1). No install/execution. PASS.
- **C9** — Evidence complete: report, checks, logs, scoped diff, `git status`,
  hashes. No commit/push/run. PASS (local evidence).

## Residual risks / NOT_RUN

- No actual cloud run: `workflow_dispatch` on a published commit is NOT_RUN and
  requires the separately approved commit/push/run.
- The GitHub release URL/SHA-256 were validated statically and against the
  locally downloaded official artifact; actual network fetch on `windows-latest`
  is only proven at cloud run time.
- Authenticode trust depends on the hosted runner's trust store and timestamp;
  the check is fail-closed but a revoked/expired chain would fail the job.
- Full Windows install/runtime/UAC/lifecycle PASS remains NOT_RUN; this
  correction does not certify the installed application.
- `git diff --check` over the whole dirty tree is non-zero solely because of the
  pre-existing unrelated `docs/workflow/HISTORY.md` change, which is preserved.
