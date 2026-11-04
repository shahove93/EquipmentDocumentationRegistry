# TASK-WINDOWS-PROGRAMDATA-01 — frozen checklist for CLOUD-APP-01 fix

Frozen 2026-11-04 before implementer dispatch, under
`CLOUD_APP_01_UTF8_FIX_AUTHORIZED_20261104` (user: «разрешаю»). This is a
scoped reopening of the original Windows ProgramData TASK, not a new CI TASK
and not A2.

## Accounting (preserved)

- CI TASK: 4 full reviews / 4 Codex calls; do not touch.
- ProgramData/lifecycle attempts, waiver and previous counters preserved.
- This fix uses **one** of the two reserved Windows Codex calls for **R3
  Astra/high** independent review; the second remains unspent.
- One review only. If it FAILs or the provider is exhausted: stop; no second
  reserved call, no additional fix/review.
- After PASS only: one scoped commit, one non-force push, exactly one Windows
  `workflow_dispatch` on the published headSha.
- Full lifecycle/UAC PASS is not granted by the smoke run.

## Checklist

| ID | Criterion | Proof |
|----|-----------|-------|
| C1 | Scoped delta only in `app/windows_local.py` and `tests/test_windows_local.py`; no CLI/architecture/ACL/owner-waiver behavior change; no lockfile/Alembic-version/toolchain/CI-workflow/packaging change. | Diff vs baseline; hashes; review. |
| C2 | `alembic.ini` is read with an explicit UTF-8 encoding contract; Alembic options, `%(here)s`, `config_file_name` and Unicode paths are preserved. | Code + tests; head `e4b8c2d16a70`; Unicode-path test. |
| C3 | No `PYTHONUTF8` workaround, no `errors="replace"/"ignore"`, no ASCII stripping, no silent conversion/loss. | Diff inspection. |
| C4 | Regression tests reproduce the cp1252 `UnicodeDecodeError` on the original loader and pass on the fix; verify config/head, relative `%(here)s`, and a Unicode path without host app/installer/working DB. | Test logs with exact commands/exit. |
| C5 | Targeted checks use the approved WSL `.venv/bin/python`; no unnecessary full-suite rerun; evidence reuse. | Exact commands/CWD/exit logs. |
| C6 | `tests/test_windows_local.py` is already dirty: only the new fix-test hunks may enter the commit. Pre-existing dirty comment/legacy-test changes are preserved, not committed. If separation is impossible, stop and report. | Baseline `baseline-tests-dirty.py` hash `6F1A3248…384999`; `new-tests.txt`; staged diff review. |
| C7 | No host install, VM, working DB, UAC change, release or deploy. | Evidence/report. |
| C8 | Evidence complete: exact commands/CWD/exit, diff, status, hashes, `new-tests.txt`. | Evidence directory. |
| C9 | One R3 Astra/high review only; second reserved call untouched; CI 4/4 preserved; ProgramData/lifecycle counters/waiver preserved. | Review record/accounting. |
| C10 | After PASS only: one scoped commit, non-force push, one workflow_dispatch; no rerun on cloud failure. | Commit/run evidence. |

## Baseline

- HEAD/remote `8e5253b31494aba2e59efe1c8741cd7374e35322`.
- `app/windows_local.py` SHA-256 `648F15B5…613C4A` (HEAD-clean).
- `tests/test_windows_local.py` dirty SHA-256 `6F1A3248…384999`;
  HEAD version `324F726A…20336B`; pre-existing dirty changes must be preserved.
