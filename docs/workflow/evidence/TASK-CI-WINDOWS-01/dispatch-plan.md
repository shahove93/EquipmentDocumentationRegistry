# TASK-CI-WINDOWS-01 — dispatch plan and live reconciliation

Date: 2026-11-04 (MSK). Coordinator: OpenCode `deepseek/deepseek-flash`
(dispatch `ctx_c9bcb5a7f5a6`, task `task_eba51f957b09`, run `run_b556ddaf13c3`,
terminal `term_721aaaff-2872-4e1b-857e-aa0143645431`).

## Authority and scope

- Authority: `docs/workflow/APPROVALS.md` §CI_WINDOWS_LOCAL_PREPARATION_AUTHORIZED_20261104.
- TASK: `docs/tasks/TASK-CI-WINDOWS-01.md`, scope SHA-256
  `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`.
- Allowed product paths: NEW `.github/workflows/windows-installer.yml`, NEW
  `packaging/windows/ci-*.ps1`, NEW `packaging/windows/ci-*.py`, and edits to
  `docs/installation/windows.md` only.
- Forbidden: `app/`, `frontend/`, `edr.iss`, `build.ps1`, `smoke.ps1`,
  `smoke.py`, old tests, lockfiles, `.env`, working data, previous evidence.
- No commit/push/remote run/release/deploy; no host install, UAC/DB change or
  start of VM `EDR-Win11-Test`.

## Live reconciliation (read-only bootstrap)

- Orca CLI resolved as `orca` (`C:\Users\user\AppData\Local\Programs\orca\resources\bin\orca.exe`),
  `orca --version` = `1.4.247`.
- `worker-list` shows the only live/in-progress supervised worker is this
  coordinator dispatch; every other Dispatch is settled/exited. Historical
  user-owned terminals were not touched.
- `opencode models deepseek` lists `deepseek/deepseek-flash` and
  `deepseek/deepseek-v4-pro`. Catalog presence alone does not prove generation;
  the launch receipt and the worker's own reported effective model are checked.
- Codex available as `codex`; R2 reviewer launch is `--agent codex --model
  gpt-6.1-sol --effort high`.

## Baseline (frozen before implementer dispatch)

- Branch `main`, HEAD `dccb14554cca3f688f20153f1f3eb41195740319`.
- `baseline-status.txt` (44 porcelain entries), `baseline-dirty.diff`
  (SHA-256 `03EC257F89C2CC6D4EFA02F36A87F354927C31B1E50B00D3A4DB9FF0A9B405EE`),
  `baseline-hashes.json` (345 dirty/untracked files with SHA-256 and size).
- Existing dirty/untracked work must be preserved. The published package later
  lists ONLY the CI TASK files; unrelated dirty changes are never staged.

## Risk, route and reservations

- Risk class: **R2**. Rationale: new cross-file CI workflow plus a new
  install/start/upload/restart driver that touches security-sensitive
  fail-closed guarding and the installer/API contract; not a new architecture
  (R3) because it reuses the frozen Windows packaging contract.
- Approach A1 / cycle C1. TASK acceptance slots: first full review reserved now;
  at most one repeat full review after a FAIL, then C3 diagnosis only.
- Codex allowance for this logical CI TASK is separate from the reserved two
  Windows Codex calls for `TASK-WINDOWS-PROGRAMDATA-01`/lifecycle. Planned use:
  1 Codex R2 TASK review call; remaining CI R2 allowance stays available.
- The two reserved Windows Codex calls are NOT spent here.

## Implementer / reviewer ownership

- Implementer: real Orca OpenCode worker, `deepseek/deepseek-flash`, worktree
  `current`, no native subagent substitution. Single active writer.
- Reviewer: real Orca Codex worker, `gpt-6.1-sol` effort high, read-only/review
  only, receives the frozen checklist, actual diff and evidence pack.
- Coordinator writes only workflow/evidence/docs, not product code.

## Frozen checklist

See `frozen-checklist.md` in this directory.
