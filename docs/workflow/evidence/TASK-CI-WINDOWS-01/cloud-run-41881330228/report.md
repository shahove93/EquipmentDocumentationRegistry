# TASK-CI-WINDOWS-01 — cloud run 41881330228 report (FAILED)

- Date: 2026-11-04 (UTC).
- Approved publication executed: user approval
  `CI_WINDOWS_PUBLICATION_AND_CLOUD_RUN_AUTHORIZED_20261104`
  (`docs/workflow/APPROVALS.md`), package SHA-256
  `D9DDF5EAEDBD87497126B655A826CE4C30BD3CC54C7FBC4309E0493B1964318C`.
- Commits created and pushed (non-force):
  - `e378fdf` — `feat(windows): publish offline runtime and installer prerequisites`
    (6 files: `app/windows_local.py`, `app/windows_layout.py`,
    `packaging/windows/build.ps1`, `packaging/windows/edr.iss`,
    `packaging/windows/fetch-vcredist.ps1`, `packaging/windows/provision.ps1`).
  - `11d66b1c8a86dd59b7b1d7e693f8c27f43796196` — `ci(windows): add hosted
    installer build and runtime checks` (39 files: reviewed CI files, docs
    section, evidence, review records).
  - `git push origin main` exit 0; `origin/main` = `11d66b1c8a86dd…`.
- Workflow registration: the workflow was not listed immediately after the
  push; GitHub later reported an Actions partial outage
  (`h02n9572mx9y`, started 2026-11-04T17:40:33Z). After a bounded wait the
  workflow registered. This delay was platform-side, not a scope change.

## Run metadata

- Workflow: `Windows installer` (`.github/workflows/windows-installer.yml`).
- Run ID: `41881330228`.
- URL: `https://github.com/shahove93/EquipmentDocumentationRegistry/actions/runs/41881330228`.
- Event: `workflow_dispatch`; branch `main`; headSha
  `11d66b1c8a86dd59b7b1d7e693f8c27f43796196`.
- Job: `126754262902` — `Build and verify Windows installer`.
- Result: **failure** (started 17:52:46Z, completed 17:53:21Z).
- Artifacts: **0** (`actions/upload-artifact` step ran but found no files;
  `gh run download` returned “no valid artifacts found”).

## Step results

Success: Set up job, Check out source, Set up build Python (3.12.10),
Set up Node.js (24.22.0), Build frontend (including the C2 explicit
`$LASTEXITCODE` checks), Download and verify pinned build inputs (PostgreSQL
SHA-256 verified; Python archive download also completed).

Failure: **Install Inno Setup 6.7.3**.

```
Invoke-WebRequest -UseBasicParsing -Uri $env:INNO_SETUP_URL -OutFile $setup
INNO_SETUP_URL = https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe
404 Not Found  Not Found The requested URL was not found on this server.
Process completed with exit code 1.
```

Skipped: Build installer, Silent install and installed-runtime checks.
Therefore install, bundled-runtime start, health/UI, synthetic
document/PDF SHA-256 and restart/persistence were **NOT_RUN**. No installer
EXE or build manifest was produced.

## Finding

| ID | Severity | Location | Finding | Effect |
|----|----------|----------|---------|--------|
| CI-CLOUD-01 | MAJOR (CI TASK) | `.github/workflows/windows-installer.yml` env `INNO_SETUP_URL` (line 27) and step `Install Inno Setup 6.7.3` (lines 79–103) | The pinned Inno Setup download URL `https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe` returns HTTP 404. The workflow therefore cannot obtain ISCC and never reaches build/install. | Cloud run FAILED; C4–C9 remain unverified. |

This is a defect in the CI implementation's tool acquisition, not a product
prerequisite and not a packaging/runtime guard. Original logical ownership:
**TASK-CI-WINDOWS-01** (CI). No product code, packaging guard, installer
behavior or database was changed.

## Options (require a new approval; no automatic rerun)

1. Make Inno Setup acquisition verifiable and real: use an actually published
   Inno Setup version/URL, verify its SHA-256 and `ISCC.exe` FileVersion, or
   install via the runner's supported package manager. This changes the pinned
   build-tool input and needs a new bounded correction, review and a new
   workflow-run approval.
2. If Inno Setup `6.7.3` is required but not publicly available, the build
   contract's Inno version is a scope/architecture decision for the user.
3. Stop the cloud path here; the local review PASS and publication remain, but
   no cloud/install evidence exists.

No rerun was attempted. Cloud success is not claimed. Real UAC, clean end-user
PC and full lifecycle remain NOT_RUN.

## Evidence

- Full run log: `docs/workflow/evidence/TASK-CI-WINDOWS-01/cloud-run-41881330228/run.log`
  (captured via `gh run view 41881330228 --log`).
- Push-triggered existing Ubuntu CI run `41878711383` on the same head
  completed **success**; it is unrelated to Windows installer acceptance.
