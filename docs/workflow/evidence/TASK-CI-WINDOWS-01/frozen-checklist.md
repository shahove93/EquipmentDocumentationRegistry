# TASK-CI-WINDOWS-01 — frozen checklist (C1)

Frozen by the OpenCode coordinator 2026-11-04 before implementer dispatch.
Scope SHA-256 authority: `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`
(`docs/workflow/APPROVALS.md` §CI_WINDOWS_LOCAL_PREPARATION_AUTHORIZED_20261104).
Risk class: **R2** (new cross-file CI install driver; security-sensitive
fail-closed guard; installer/API contract surfaces). Route: Codex
`gpt-6.1-sol` / high for TASK acceptance after local implementation.

Local acceptance can only yield **READY_FOR_CLOUD_TESTING**. Every check that
needs a real GitHub-hosted Windows runner is **NOT_RUN** locally.

| ID | Observable criterion | Proof command / artifact | Local status |
|----|----------------------|--------------------------|--------------|
| C1 | New `.github/workflows/windows-installer.yml` exists, parses as YAML, defines one job on `windows-latest`, has `permissions: contents: read`, trigger `workflow_dispatch`, and `.github/workflows/ci.yml` is byte-unchanged from baseline. | YAML load exit 0; file content; `git diff --name-status` shows only allowlisted paths. | CHECK |
| C2 | The job builds in one ephemeral Windows job: checks out, builds frontend (`npm ci`, `npm run build`), downloads **pinned** inputs — CPython embeddable `3.12.10` amd64 and EDB PostgreSQL `18.6-5` x64 binaries — from official URLs, verifies their pinned SHA-256, installs Inno Setup `6.7.3`, runs `build.ps1`, and fails on any version/hash/layout mismatch. | Workflow step text; pinned constants; build log artifact (cloud). | CHECK (static) / NOT_RUN (cloud) |
| C3 | New `packaging/windows/ci-installer.ps1` fails closed unless genuine GitHub-hosted Windows CI: requires `GITHUB_ACTIONS=true`, `CI=true`, `RUNNER_OS=Windows`, `RUNNER_ENVIRONMENT=github-hosted`; rejects host `EDR-Win11-Test`; requires fresh (absent) work/install/data directories; otherwise exits non-zero before any install/side effect. | Source inspection + local negative test with the env unset: exit non-zero and no install directory created. | CHECK |
| C4 | Silent install runs the built EXE with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=<path>` into a fresh runner temp directory, installer exit 0, install log retained. | Script and artifact-upload config; cloud exit code/log. | NOT_RUN (cloud) |
| C5 | Post-install verification asserts installed `<install>\python\python.exe`, installed `launcher.ps1`/`alembic.ini`/`ui\index.html`, and bundled runtime `%ProgramData%\EDR\runtime\postgresql\bin\postgres.exe`. | Script assertions and recorded results JSON. | NOT_RUN (cloud) |
| C6 | App is launched with the **installed bundled interpreter** (`<install>\python\python.exe -B -m app.windows_local start --no-browser`), `GET /health` returns `{"status":"ok"}`, and `GET /` returns HTML containing `<div id="root">`. | Script + results JSON + app log artifact. | NOT_RUN (cloud) |
| C7 | Synthetic data path: create document type and document over API, upload a synthetic PDF attachment (`multipart/form-data`), download the attachment and assert download SHA-256 equals the uploaded bytes. Only synthetic data, no production paths. | Script `hashlib.sha256` comparison; results JSON. | NOT_RUN (cloud) |
| C8 | Stop, restart the installed app, verify the document exists and re-downloaded attachment SHA-256 is unchanged, then stop cleanly. | Script + results JSON + logs. | NOT_RUN (cloud) |
| C9 | On any step failure the job still uploads artifacts (`if: always()`): install log, app/PostgreSQL logs, results JSON, built EXE and its SHA-256; runtime archive versions/SHA-256 recorded. | Workflow `if: always()` upload step; artifact contents. | CHECK (static) / NOT_RUN (cloud) |
| C10 | Only allowlisted paths change: new `.github/workflows/windows-installer.yml`, new `packaging/windows/ci-*.ps1`, new `packaging/windows/ci-*.py`, modified `docs/installation/windows.md`. `smoke.ps1`, `smoke.py`, `build.ps1`, `edr.iss`, `app/`, `frontend/`, lockfiles and old tests are byte-unchanged from baseline. | `git status`/`git diff --name-status` vs baseline; SHA-256 of protected files vs `baseline-hashes.json`. | CHECK |
| C11 | `docs/installation/windows.md` adds a CI section: job purpose, pinned inputs/hashes, trigger, what is verified, and explicit limits (interactive UAC/manual clean-PC and full lifecycle remain out of scope; cloud status NOT_RUN until an actual run). | Doc diff. | CHECK |
| C12 | Local static evidence recorded with exact command, CWD and exit code: `py_compile` of new `ci-*.py`, PowerShell parser check of new `ci-*.ps1`, YAML parse of the workflow, and the C3 negative guard test. | `implementer/checks.md` + logs under `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/`. | CHECK |

Out of scope / must not be claimed: actual cloud run, real UAC prompt, clean-PC
manual install, full installer lifecycle (backup/restore/update/uninstall/reinstall),
and any product-code fix. Findings in existing packaging must be reported as
findings, not silently fixed in this TASK.
