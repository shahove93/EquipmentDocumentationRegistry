# TASK-CI-WINDOWS-01 — cloud retry 41884655362 report (FAILED)

- Date: 2026-11-04 (UTC).
- Approval: `CI_CLOUD_01_URL_CORRECTION_AND_RETRY_AUTHORIZED_20261104`
  (user: «Разрешаю»), one scoped correction, one non-force push, one retry run.
- Correction commit: `44d7b65bd387b3ab0b670efcb2686c05d11290ae`
  (`ci(windows): fix Inno Setup acquisition and verify signature`);
  push `origin/main` exit 0; remote main = `44d7b65`.
- Prior cloud failure: run `41881330228` on `11d66b1` (old Inno URL 404).

## Run metadata

- Workflow: `Windows installer`; event `workflow_dispatch`; branch `main`.
- Run ID: `41884655362`.
- URL: `https://github.com/shahove93/EquipmentDocumentationRegistry/actions/runs/41884655362`.
- headSha: `44d7b65bd387b3ab0b670efcb2686c05d11290ae`.
- Job: `126765768012` (`Build and verify Windows installer`).
- Result: **failure** (37 s). Artifacts: **0**.

## Step results

Success: Set up job/checkout/Python 3.12.10/Node 24.22.0, frontend build,
pinned Python/PostgreSQL download + SHA-256.

Inno Setup step:
- download from the official immutable GitHub release succeeded;
- `Get-FileHash` matched
  `9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`;
- Authenticode `Valid`, signer
  `CN=Pyrsys B.V., O=Pyrsys B.V., S=Noord-Holland, C=NL`;
- the log line confirms:
  `Inno Setup installer verified: ... sha256=9C73... signer=CN=Pyrsys B.V., ...`;
- installer `Start-Process` completed; `ISCC.exe` exists at the target path;
- then the **retained pre-existing** check failed:
  `Installed ISCC version is not 6.7.3: 0.0.0.0`.

Skipped: Build installer, Silent install and installed-runtime checks. Therefore
installation/runtime/health/UI/document/PDF/restart persistence are **NOT_RUN**.

## Finding

| ID | Severity | Location | Finding | Effect |
|----|----------|----------|---------|--------|
| CI-CLOUD-02 | MAJOR (CI TASK) | `.github/workflows/windows-installer.yml` lines 112–115: `(Get-Item $iscc).VersionInfo.FileVersion` + `^6\.7\.3` check | On the hosted runner, the installed official Inno Setup 6.7.3 `ISCC.exe` reports `VersionInfo.FileVersion = 0.0.0.0`, so the retained check fails closed after a successful, hash/signature-verified install. | Retry run FAILED before build/install; CI-CLOUD-01 acquisition is resolved, but the version-signal check is a false negative on this runner. |

The URL/SHA/Authenticode correction is proven by this run. The new failure is
the **pre-existing ISCC FileVersion check**, which the approval required to
keep; it is not a regression introduced by the URL change. No fix or rerun was
performed under this approval.

## Options (require a new explicit decision; not executed)

1. Replace the unreliable `ISCC.exe` `VersionInfo.FileVersion` signal with a
   reliable check while retaining authenticity/version guarantees, e.g.:
   - keep the already-proven official installer SHA-256 + Authenticode signer
     and check `ISCC.exe` existence, plus use `ProductVersion`/`ProductName`
     metadata if it is non-zero on the runner; or
   - run `ISCC.exe` only for a version probe (e.g. `ISCC.exe /?` and parse a
     version string) if it has a stable machine-readable output; or
   - install Inno Setup through a pinned package manager that exposes a
     reliable version.
2. Drop the `ISCC.exe` FileVersion check only if the installer SHA/Authenticode
   pin is accepted as sufficient version provenance; this is a scope/contract
   decision.
3. Stop the cloud path; keep the corrected URL/signature enforcement and report
   the blocked runner check.

Any change requires a new bounded correction/approval, possibly a new review,
and a new run approval. The prior additional review slot is already consumed;
no further fix/review is authorized by the current approval.

## Evidence

- `docs/workflow/evidence/TASK-CI-WINDOWS-01/cloud-run-41884655362/run.log`
  (captured via `gh run view 41884655362 --log`).
- Correction evidence: `docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/`.
- No artifact was produced (`upload-artifact` found no files).
- Cloud success/full Windows/UAC/lifecycle PASS is **not** claimed.
