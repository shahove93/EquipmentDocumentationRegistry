# Implementer spec — TASK-CI-WINDOWS-01 / A1 bounded correction (CI-CLOUD-01)

You are a separate OpenCode implementer. Work in
`D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`, HEAD
`11d66b1c8a86dd59b7b1d7e693f8c27f43796196`. Do not use native subagents.
You do not assign project PASS and must not commit, push or run the workflow.

Read first:
- `AGENTS.md`
- `docs/tasks/TASK-CI-WINDOWS-01.md`
- `docs/workflow/APPROVALS.md` §`CI_CLOUD_01_URL_CORRECTION_AND_RETRY_AUTHORIZED_20261104`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/CI-CLOUD-01-diagnosis.md`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/frozen-checklist.md`
  and `baseline-hashes.txt`
- `.github/workflows/windows-installer.yml`

## Change (strict allowlist)

1. `.github/workflows/windows-installer.yml` (required):
   - keep `INNO_VERSION: '6.7.3'`;
   - set `INNO_SETUP_URL` to
     `https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe`;
   - add `INNO_SETUP_SHA256: '9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732'`;
   - in the Inno installation step, after `Invoke-WebRequest` and before
     `Start-Process`, verify:
     * `Get-FileHash -LiteralPath $setup -Algorithm SHA256` equals
       `$env:INNO_SETUP_SHA256` (throw on mismatch);
     * `Get-AuthenticodeSignature -LiteralPath $setup` has `Status -eq 'Valid'`
       and `SignerCertificate.Subject` matches `CN=Pyrsys B.V.` (throw
       otherwise; do not weaken or skip the check);
   - keep the existing `ISCC.exe` `VersionInfo.FileVersion` `6.7.3` check and
     all other guards/steps unchanged.
2. `docs/installation/windows.md` (optional, targeted): update only the CI
   section item 3 to state the official immutable GitHub release URL and
   SHA-256/Authenticode verification. Do not change other documentation.

Do NOT edit `packaging/windows/build.ps1`, `edr.iss`, `provision.ps1`,
`ci-installer.ps1/.py`, `app/`, `frontend/`, lockfiles, tests, `.env`, or any
product prerequisite. Preserve every unrelated dirty/untracked file. Do not
change the Inno version or dependencies.

## Local checks (no install, no product execution)

Write evidence to
`docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/implementer/`.
Record exact command, CWD and exit code for each:

1. YAML parse + structural assertions (host `python`, PyYAML):
   one `windows-installer` job, `workflow_dispatch`, `permissions: contents:
   read`, upload step `if: always()`, the new URL and SHA-256 constant present,
   `INNO_VERSION` still `6.7.3`, and the ISCC FileVersion check still present.
2. `actionlint` on the workflow. A portable binary may already exist at
   `C:\Users\user\AppData\Local\Temp\opencode\actionlint\actionlint.exe`; if
   absent, use the YAML check and note actionlint NOT_RUN. Do not install tools.
3. `git diff --check` exit 0; `git status --porcelain` recorded; protected-file
   hashes compared with `baseline-hashes.txt` (only the allowlisted files may
   differ).
4. Fail-closed proof for the new checks (PowerShell 5.1 or 7):
   - Use the official installer already downloaded for diagnosis if present:
     `C:\Users\user\AppData\Local\Temp\opencode\inno-diag\innosetup-6.7.3.exe`.
     First assert its SHA-256 is `9C73C3…B732` and its Authenticode signer is
     `CN=Pyrsys B.V.`; this must not install or execute it.
   - Reproduce the exact hash/signature check logic from the workflow:
     correct hash + valid signature → success; wrong expected hash → throws
     (capture non-zero exit and the error). Record both.
   - If the file is absent, download it from the official URL to `%TEMP%` and
     verify the same hash/signature; do not install it.
5. Do not run the installer, app, PostgreSQL, VM or working DB.

## Evidence

- `report.md` — what changed, exact commands/CWD/exit codes, closure of C1–C9,
  effective model, residual risks.
- `checks.md` + raw logs for the checks above.
- `worker.diff` — exact diff of only the allowlisted change(s).
- `git-status.txt` — after the work.

Do not commit/push/run. Do not claim project/cloud PASS; only
correction-complete with local evidence.

## Return

Send Orca `worker_done` with `--outcome succeeded` only if the correction and
local evidence are complete; otherwise `--outcome failed`. Three sentences:
what changed, what was verified, what remains (the single additional routed
review and the later approved commit/push/run). Include real
`--files-modified` and `--report-path`.
