# TASK-CI-WINDOWS-01 / A1 — frozen correction checklist (CI-CLOUD-01)

Frozen 2026-11-04 before implementer dispatch, under
`CI_CLOUD_01_URL_CORRECTION_AND_RETRY_AUTHORIZED_20261104` (user: «Разрешаю»).
Logical TASK/A1; this is a bounded correction, not A2.

## Accounting (preserved)

- Prior full reviews: **2/2** (C1 FAIL, C2 PASS); failed reviews **1**;
  CI Codex calls **2/4**; C3 diagnosis already performed.
- This approval adds **one** independent full review for the correction
  (an explicit extension of A1 review allowance). If it FAILs, stop: no further
  fix or review under this approval.
- After PASS only: one scoped commit, one non-force push, one
  `workflow_dispatch` cloud run on the published commit. No rerun.
- Full Windows lifecycle/UAC PASS is not granted by this smoke run.

## Checklist

| ID | Criterion | Proof |
|----|-----------|-------|
| C1 | Only `.github/workflows/windows-installer.yml` and (optionally) a targeted CI note in `docs/installation/windows.md` change. `build.ps1`, `edr.iss`, `provision.ps1`, `app/`, `frontend/`, `ci-installer.ps1/.py`, lockfiles, tests and product dependencies stay byte-identical. | `git diff --name-status` vs baseline; hash comparison from `baseline-hashes.txt`. |
| C2 | `INNO_VERSION` remains `6.7.3`. `INNO_SETUP_URL` is exactly `https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe` (official immutable release). | File content + static assertion. |
| C3 | A pinned `INNO_SETUP_SHA256` = `9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732` is added and verified with `Get-FileHash -Algorithm SHA256` before executing the installer; mismatch throws and fails the step. | File content + fail-closed proof. |
| C4 | Authenticode is verified before execution: `Get-AuthenticodeSignature` status `Valid` and signer subject matches `CN=Pyrsys B.V.`; failure throws. | File content + fail-closed proof. |
| C5 | The existing post-install `ISCC.exe` FileVersion `6.7.3` check remains unchanged. | File content/static assertion. |
| C6 | No TLS/signature/runner guard weakening, no version change, no product prerequisite/dependency change, no new secret (SHA is public), no host install. | Diff inspection + `git diff --check`. |
| C7 | Workflow YAML parses; `actionlint` (if available) exits 0; PowerShell parser check of the embedded installation snippet (if extracted) exits 0; optional doc note accurately states the official URL + SHA. | Check logs with command/CWD/exit. |
| C8 | Fail-closed proof for C3: correct SHA passes; wrong SHA throws. Signature check on the official 6.7.3 installer reports `Valid`/`Pyrsys B.V.`. No install/execution of the installer. | Reproducible local PowerShell harness + logs. |
| C9 | Evidence is complete: report, exact commands/CWD/exit codes, scoped diff, `git status`, hashes. No commit/push/run by the implementer. | Evidence directory. |

Out of scope: any product/install script change, Inno 6.7.4 switch, any new
approach A2, any additional review after a FAIL, any cloud rerun after a cloud
FAIL.
