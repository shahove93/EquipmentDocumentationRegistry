# TASK-CI-WINDOWS-01 — prepared publication package (awaiting user approval)

Status: **LOCAL REVIEW PASSED — READY_FOR_CLOUD_TESTING; cloud run NOT_RUN.**
No commit, push, merge, release, remote workflow run, host install, VM start or
working-DB change has been performed. This package is a proposal only.

- Reviewed revision: `main` HEAD
  `dccb14554cca3f688f20153f1f3eb41195740319` with the scoped files below.
- Authority: `CI_WINDOWS_LOCAL_PREPARATION_AUTHORIZED_20261104`, scope SHA-256
  `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`.
- Reviews: [C1 FAIL](../reviews/TASK-CI-WINDOWS-01-C1.md),
  [C2 PASS](../reviews/TASK-CI-WINDOWS-01-C2.md). R2 route, Codex
  `gpt-6.1-sol`/high, full reviews 2/2, failed 1, Codex calls 2 of 4.
- Frozen checklist: [frozen-checklist.md](frozen-checklist.md).
- Review packet: [review-packet/](review-packet/).

## 1. Reviewed CI/TASK files (this TASK)

| Path | Change | SHA-256 |
|------|--------|---------|
| `.github/workflows/windows-installer.yml` | new | `7A256F572EC97760DF255EAE6E6E9E99989D7A00D68C456D15362FD27AD8DA21` |
| `packaging/windows/ci-installer.ps1` | new | `764AB73A1C3BAD3AD49FC774AF61891AC690A3566C8B7E4F349D9583098D2F05` |
| `packaging/windows/ci-installer.py` | new | `5EC794D5BC39ABD5772639BE1F9B28BA08CF772F92EF1F049442F75DE51B9FA5` |
| `docs/installation/windows.md` | edited (CI section + prior doc updates) | `E68366289EDA94264DFEA815CB817BD3293218F1A87BAD727B80D9AEEFD4881E` |

Reviewed code diff: `review-packet/worker.diff` (C1) +
`review-packet/worker-c2.diff` (C2). Scoped docs addition:
`review-packet/docs-ci-section.diff` (pre-TASK baseline = first 237 lines; the
rest of this file's dirty diff predates this TASK).

Accounted as reviewed: 342 of 345 baseline file hashes unchanged; differences
only in `docs/installation/windows.md` and coordinator-owned
`docs/workflow/HISTORY.md` / `STATE.md`. Protected files
(`build.ps1`, `smoke.ps1`, `smoke.py`, `edr.iss`, `app/windows_local.py`,
`app/windows_layout.py`, `ci.yml`) are byte-unchanged by this TASK.

## 2. Mandatory prerequisite: existing uncommitted Windows packaging/runtime

A cloud checkout of `main` at HEAD **cannot** build or exercise the installer
from the CI files alone. The CI workflow calls `build.ps1`, which calls
`fetch-vcredist.ps1`; `edr.iss` deploys `provision.ps1`; `build.ps1` copies
`app/`, and `app/windows_local.py` imports the untracked
`app/windows_layout.py`. Verified at HEAD:

- `HEAD:packaging/windows/provision.ps1` — **absent**
- `HEAD:app/windows_layout.py` — **absent**
- `HEAD:packaging/windows/build.ps1` — **no** `fetch-vcredist.ps1` reference
- `HEAD:packaging/windows/edr.iss` — **no** `provision.ps1` reference and no
  explicit SQLAlchemy `dialects\postgresql` copy
- `HEAD:app/windows_local.py` — **no** `windows_layout` import

Therefore a valid publication needs a prerequisite commit with these exact
uncommitted files (fixed hashes):

| Path | Git state | SHA-256 | Prior logical basis (not re-accepted here) |
|------|-----------|---------|--------------------------------------------|
| `app/windows_local.py` | modified | `648F15B5E08185D4FA9FAB4ED457D81ABD31CDD0878EB439E87065D30E613C4A` | Windows ProgramData runtime work; A2/C2 scoped PASS is PARTIAL/CLOSED, not full PASS |
| `app/windows_layout.py` | new | `C7081F5A4C400E89D862865D5A6EEB4450B98C024CB8C90A2EA891372B08F8E0` | same |
| `packaging/windows/build.ps1` | modified | `5F2C7729C1B0AD61C471A6EB3D753D69928901637D398D5B9EA4970BAB38D593` | offline CRT + runtime packaging work |
| `packaging/windows/edr.iss` | modified | `C912AE4A8614C3B6516DACD094A8356B555B889BBF4A464C931DF14073A8AD7C` | CRT prerequisite + SQLAlchemy dialect packaging fix (A2/C1/A2/C2 scoped work) |
| `packaging/windows/fetch-vcredist.ps1` | new | `579D272A64FDFAF50474420292E5C3892C976A54F46D2EE77207F8446705B08E` | CRT offline TASK, R2 PASS `/` `task_d55d6550e738` |
| `packaging/windows/provision.ps1` | new | `57ABDD5D3BFCDB5B289139BAF6BFF7D16BB62AAFAE47F3BED9BCC351E0831F2C` | ProgramData runtime work; `CI-C4-01` interactive-shell risk is documented and unverified |

`packaging/windows/launcher.ps1`, `EDR.cmd`, `prepare.py`,
`requirements.lock` and `alembic.ini` are already tracked and clean at HEAD.

**Explicit warning:** these prerequisite files were **not** re-accepted by the
CI review (it used them only as read-only context). Publishing them is a
separate user decision under their own logical TASKs; they are not evidence of
full Windows lifecycle/UAC acceptance.

### Deliberately excluded from publication

- `packaging/windows/smoke.ps1`, `packaging/windows/smoke.py`,
  `tests/test_windows_local.py` — not needed by the cloud job; leave dirty.
- `docs/workflow/{STATE,HISTORY,APPROVALS,MODEL-ROUTING}.md`, `AGENTS.md`,
  `ROADMAP.md`, task/ADR/NEXT-STAGE/workflow records — not needed for the run;
  leave dirty unless the user separately approves publishing workflow records.
- `.env`, `.venv/`, `storage/`, `node_modules/`, `dist/` and all other untracked
  data stay untouched.
- Never use `git add -A` or `git add .`.

## 3. Proposed Git commands (for user approval; do not run yet)

Run from `D:/Antigravity/EquipmentDocumentationRegistry` on `main`.

```powershell
# Preconditions / evidence snapshot
git status --porcelain
git rev-parse HEAD
git diff --stat

# Commit 1 — prerequisite Windows packaging/runtime (separate logical basis)
git add -- app/windows_local.py app/windows_layout.py `
  packaging/windows/build.ps1 packaging/windows/edr.iss `
  packaging/windows/fetch-vcredist.ps1 packaging/windows/provision.ps1
git diff --cached --stat
git commit -m "feat(windows): publish offline runtime and installer prerequisites"

# Commit 2 — reviewed CI TASK files and evidence
git add -- .github/workflows/windows-installer.yml `
  packaging/windows/ci-installer.ps1 packaging/windows/ci-installer.py `
  docs/installation/windows.md `
  docs/workflow/evidence/TASK-CI-WINDOWS-01 `
  docs/workflow/reviews/TASK-CI-WINDOWS-01-C1.md `
  docs/workflow/reviews/TASK-CI-WINDOWS-01-C2.md
git diff --cached --stat
git commit -m "ci(windows): add hosted installer build and runtime checks"

# Push — requires explicit approval
git push origin main

# Remote cloud run — requires explicit approval
gh workflow run windows-installer.yml --ref main
gh run list --workflow windows-installer.yml --limit 1
gh run watch <run-id> --exit-status
gh run download <run-id> -n windows-installer-evidence -D artifacts/windows-installer
```

Notes:
- Commit 1 must precede Commit 2; without it the cloud checkout lacks the build
  inputs and the job cannot succeed.
- If the user prefers one commit, the CI review boundary is lost; two commits
  keep the reviewed CI change separate from the prerequisite packaging.
- Workflow-record publication (STATE/HISTORY/etc.) can be a separate optional
  commit only after explicit approval.
- No commit/push/run is performed by the coordinator.

## 4. What the cloud run will prove (only after an actual run)

C4–C9: silent install, installed file checks, installed bundled-interpreter
start, `/health`, UI root, synthetic document/PDF upload/download SHA-256,
stop/restart/persistence SHA-256, clean stop, and artifacts on failure.
It will **not** prove real interactive UAC, clean end-user Windows, or the full
lifecycle (backup/restore/update/uninstall/reinstall, ACL/migration matrix).
Those remain separate NOT_RUN work.

`CI-C4-01`: if the hosted runner lacks a same-session interactive shell,
`provision.ps1` will refuse installation. In that case the affected install path
must stop and be reported under its original logical TASK; no packaging guard
may be weakened inside this CI TASK.

## 5. Current non-claims

- Local PASS only: READY_FOR_CLOUD_TESTING.
- Actual GitHub Actions run: **NOT_RUN**.
- No full Windows/project PASS, no lifecycle/UAC acceptance.
- No commit, push, merge, release, deployment or remote run performed.
