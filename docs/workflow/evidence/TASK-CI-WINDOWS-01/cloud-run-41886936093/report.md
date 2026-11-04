# TASK-CI-WINDOWS-01 — cloud run 41886936093 report (FAILED at app startup)

- Date: 2026-11-04 (UTC).
- Approval: `CI_CLOUD_02_ISCC_VERSION_CHECK_CORRECTION_AUTHORIZED_20261104`
  (user: «разрешаю»).
- Review: A1 review 4 **PASS** (Task `task_61c0c61621c1`,
  `docs/workflow/reviews/TASK-CI-WINDOWS-01-C4.md`); final CI Codex call 4/4.
- Commit: `8e5253b31494aba2e59efe1c8741cd7374e35322`
  (`ci(windows): verify ISCC compiler version from build log`); non-force push
  exit 0; remote main = `8e5253b`.
- Run ID: `41886936093`;
  URL `https://github.com/shahove93/EquipmentDocumentationRegistry/actions/runs/41886936093`;
  event `workflow_dispatch`; headSha
  `8e5253b31494aba2e59efe1c8741cd7374e35322`; conclusion **failure**
  (2m37s, job `126773804363`).

## Step results

Success:
- checkout, Python 3.12.10, Node 24.22.0, frontend build;
- pinned Python/PostgreSQL downloads and SHA-256 checks;
- **Install Inno Setup 6.7.3** — official immutable URL, SHA-256
  `9C73C3…B732`, Valid Authenticode `CN=Pyrsys B.V.`;
- **Build installer** — `build.ps1` succeeded; the new compiler-version check
  found the expected `Compiler engine version: Inno Setup 6.7.3` line
  (the CI-CLOUD-01/02 correction is proven by this run);
- **Silent install** — installer exit 0; installed files present:
  `python\python.exe`, `launcher.ps1`, `alembic.ini`, `ui\index.html`,
  `%ProgramData%\EDR\runtime\postgresql\bin\postgres.exe`.

Failure:
- the installed app was started with
  `D:\a\_temp\edr-ci-install\python\python.exe -B -m app.windows_local start --no-browser`;
- supervisor exited 1 almost immediately:

```text
EDR: UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 3635:
character maps to <undefined>
ci-installer failed: AssertionError: supervisor exited during startup with 1
```

Skipped / NOT_RUN: `/health`, UI root, synthetic document/PDF upload/download
SHA-256, stop/restart/persistence, clean stop. No app-level criteria were
verified beyond install/file presence.

## Finding

| ID | Severity | Owner | Finding |
|----|----------|-------|---------|
| CLOUD-APP-01 | MAJOR (cloud blocker) | Original Windows ProgramData/lifecycle logical TASK, not the CI TASK | Installed app startup fails with `UnicodeDecodeError` from a UTF-8 config file read under the runner's locale encoding. |

Strong root-cause evidence:
- `alembic.ini` in the repo is 5,218 bytes, UTF-8, with the first non-ASCII
  byte at offset 3,593; the failure occurs at position 3,635 (`0x81` is a UTF-8
  continuation byte, invalid in the runner's charmap encoding).
- `app/windows_local.py:284` does
  `cfg = Config(str(self.install / "alembic.ini"))`; Alembic/configparser reads
  that file with the process default (locale) encoding, not UTF-8.
- This is a **product/runtime defect on Windows**, not caused by the CI
  correction. The CI correction is demonstrated by the successful Inno
  install, compiler-version check and build in this same run.

## Options (require a new product-TASK decision; none executed)

1. Read `alembic.ini` as UTF-8 in the product (explicit encoding in the Alembic
   config load / `configparser.read_file`), then rebuild and rerun the approved
   cloud check under the original Windows TASK.
2. Normalize `alembic.ini` to ASCII-only (remove/transliterate the non-ASCII
   comments) as a product-owned packaging fix.
3. Do **not** mask this with a CI-only `PYTHONUTF8=1`/encoding workaround; that
   would hide the product defect and is outside this TASK.

No fix, review, commit or rerun was performed after this failure, per the
approval. The new cloud failure stops the chain for a user decision.

## Evidence

- Full run log:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/cloud-run-41886936093/run.log`
  (1.1 MB; captured via `gh run view 41886936093 --log`).
- Remote artifact `windows-installer-evidence` (ID `13352476524`,
  73,228,696 bytes) remains available at the run URL. Local download was
  attempted twice but the artifact service transferred only ~4.9 MB before the
  command timeout; the partial zip was removed. The run log contains the
  decisive failure and supervisor output.
- Cloud success/full Windows/UAC/lifecycle PASS is not claimed.
