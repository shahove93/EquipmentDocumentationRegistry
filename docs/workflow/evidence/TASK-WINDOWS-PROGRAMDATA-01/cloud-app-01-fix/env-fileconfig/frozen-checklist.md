# TASK-WINDOWS-PROGRAMDATA-01 — frozen checklist, CLOUD-APP-01 downstream fix

Frozen 2026-11-04 before implementer dispatch under
`CLOUD_APP_01_ENV_FILE_CONFIG_FIX_AUTHORIZED_20261104` (user: «Разрешаю.»).
Original logical TASK; not a new TASK/approach.

## Accounting (preserved)

- CI TASK: 4 reviews / 4 Codex calls — untouched.
- ProgramData/lifecycle attempts, security waiver and counters preserved.
- Previous R3 FAIL **CLOUD-UTF8-R3-01** is retained as history.
- This step uses the **last remaining reserved Windows Codex call** for one
  repeat R3 Astra/high review. After it, reserved Windows calls = **0**.
- If the review FAILs or the provider is exhausted: stop; no new fix/review/run.
- After PASS only: one scoped commit, non-force push, exactly one Windows
  `workflow_dispatch`. No rerun on cloud failure.
- Full lifecycle/UAC PASS is not granted.

## Checklist

| ID | Criterion | Proof |
|----|-----------|-------|
| C1 | Product delta only `app/windows_local.py`, `alembic/env.py`, and the new test block. No toolchain/deps/packaging/CI-guard or non-Windows behavior change. | Diff vs baseline; review. |
| C2 | `alembic/env.py` reads the logging config with explicit UTF-8 (`fileConfig(..., encoding="utf-8")` or equivalent); file-logging semantics preserved. | Code + review. |
| C3 | All reads of the same `alembic.ini` in the affected startup path are covered: `load_alembic_config` and `alembic/env.py` `fileConfig`; no other uncovered read in the path. | Source inspection/evidence. |
| C4 | Regression test reproduces the old downstream cp1252 failure and verifies the fixed **real chain** `load_alembic_config -> command.upgrade -> alembic/env.py -> fileConfig` succeeds with no real DB/app/installer. | Test + logs. |
| C5 | Tests cover UTF-8/`%(here)s`/`config_file_name`, head `e4b8c2d16a70`, Unicode path, and the downstream chain. | Targeted pytest exit 0. |
| C6 | Dirty-test isolation: final committed test file = HEAD + full new test block; pre-existing dirty comment/legacy-test changes excluded. If separation is impossible, stop. | Constructed committed file/hash + staged diff. |
| C7 | Evidence: exact commands/CWD/exit, diff, status, `new-tests.txt`, review record. | Evidence directory. |
| C8 | Accounting: last reserved Windows call consumed by the one R3 Astra/high review; remaining 0; CI 4/4 and ProgramData counters/waiver preserved. | Review record/accounting. |
| C9 | After PASS only: one scoped commit, non-force push, one workflow_dispatch; cloud failure stops without fix/rerun. | Commit/run evidence. |

## Baseline

- HEAD/remote `8e5253b31494aba2e59efe1c8741cd7374e35322`.
- `app/windows_local.py` `BFEB2F3F…19EC95C` (uncommitted prior fix).
- `alembic/env.py` `D42A5BA9…252DE45` (HEAD-clean).
- `tests/test_windows_local.py` `DE351E89…95018F` (pre-existing dirty +
  prior 3 new tests).
- Prior R3 FAIL review `5FDC063F…44E758`.
