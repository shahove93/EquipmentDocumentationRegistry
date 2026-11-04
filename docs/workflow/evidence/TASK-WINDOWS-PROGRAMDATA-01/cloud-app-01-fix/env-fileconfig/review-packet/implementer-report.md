# CLOUD-APP-01 downstream `fileConfig` UTF-8 fix — implementer report

- TASK: TASK-WINDOWS-PROGRAMDATA-01 / CLOUD-APP-01 scoped fix
- Approval: `CLOUD_APP_01_ENV_FILE_CONFIG_FIX_AUTHORIZED_20261104`
- Implementer: OpenCode worker, effective model `deepseek/deepseek-flash`
- Repo: `D:/Antigravity/EquipmentDocumentationRegistry`, WSL
  `/mnt/d/Antigravity/EquipmentDocumentationRegistry`
- Branch `main`, HEAD `8e5253b31494aba2e59efe1c8741cd7374e35322` (unchanged)
- No commit, push, workflow run, host install, VM, UAC or working-DB access.
- Pre-existing dirty working tree and the other pending fix hunks were preserved.

## Changes

### 1. `alembic/env.py` (one line)

```diff
 if config.config_file_name is not None:
-    fileConfig(config.config_file_name)
+    fileConfig(config.config_file_name, encoding="utf-8")
     project_root = Path(config.config_file_name).resolve().parent
```

No import, branch, `project_root`, offline/online or non-Windows logic changed.
`alembic.ini`, toolchain, dependencies, lockfiles, packaging and CI were not
touched.

### 2. `tests/test_windows_local.py`

Kept the three existing appended `alembic_config` tests untouched and appended a
fourth self-contained test at EOF (does not modify the pre-existing dirty
legacy/comment block):

`test_alembic_env_fileconfig_reads_utf8_chain(tmp_path, monkeypatch)`:
1. loads the real repo `alembic.ini` through `load_alembic_config`;
2. sets `DATABASE_URL` and `STORAGE_ROOT` via `monkeypatch.setenv`;
3. monkeypatches `configparser.ConfigParser.read` so `encoding in (None,
   "locale")` is forced to `cp1252`;
4. asserts the old downstream call
   `logging.config.fileConfig(cfg.config_file_name)` raises
   `UnicodeDecodeError` at exactly `start == 3635` / byte `0x81`;
5. patches `alembic.context.configure`, `begin_transaction` (`nullcontext`) and
   `run_migrations` (no-op) and runs the real offline
   `command.upgrade(cfg, "head", sql=True)`, which executes `alembic/env.py`
   and its fixed `fileConfig(..., encoding="utf-8")` without a DB or app.

Local imports only (`configparser`, `contextlib.nullcontext`, `logging.config`,
`alembic.command`, `alembic.context`, `app.windows_local`); no host DB/app.

### 3. `new-tests.txt`

`docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/new-tests.txt`
contains the **complete** new test block, from
`def test_alembic_config_reads_utf8_and_preserves_here` to EOF (all four tests,
78 lines, 4 `def test_`). The pre-existing dirty legacy block stays excluded.

## Commands, CWD and exit codes

WSL checks, CWD `/mnt/d/Antigravity/EquipmentDocumentationRegistry`,
`.venv/bin/python` (Python 3.14.4, Alembic 1.20.0):

| Command | Exit | Log |
|---|---|---|
| `.venv/bin/python -m py_compile app/windows_local.py alembic/env.py tests/test_windows_local.py` | 0 | `py_compile.txt` |
| `.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config" -p no:cacheprovider` | 0 (`3 passed, 44 deselected`) | `pytest-alembic_config.txt` |
| `.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_env_fileconfig_reads_utf8_chain" -p no:cacheprovider` | 0 (`1 passed, 46 deselected`) | `pytest-env-fileconfig-chain.txt` |

Windows Git, CWD `D:/Antigravity/EquipmentDocumentationRegistry`:

| Command | Exit | Log |
|---|---|---|
| `git diff --check -- app/windows_local.py alembic/env.py` | 0 (only CRLF-will-be-replaced warning for dirty `app/windows_local.py`) | `git-diff-check-app.txt` |
| `git status --porcelain` | 0 | `git-status.txt` |

No full-suite rerun.

### Negative control (proves the real chain is exercised)

Temporarily reverted only the `encoding="utf-8"` argument, reran the new test:
it **failed** with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in
position 3635` raised from `alembic/env.py:13` via
`logging/config.py -> configparser.read` — i.e. exactly the downstream path.
`alembic/env.py` was then restored byte-for-byte (repo-local backup, deleted);
SHA-256 `79752F72…C92092C` matches before and after. Log: `negative-control.txt`.

## Dirty-test isolation

- Pre-append file reconstructed as `head -n 355 tests/test_windows_local.py`
  hashes to `6F1A32489FCB7C956AE2337E75678F0F9338A70F11F8D73E9BA05C82BB384999`,
  matching the frozen baseline for the pre-existing dirty content.
- The new block is appended after that content only; `new-tests.txt` starts at
  the first new test and reaches EOF.
- No unrelated baseline change was introduced by this step.

## File SHA-256

| File | SHA-256 |
|---|---|
| `app/windows_local.py` | `BFEB2F3F826315655B3C52B44F40CF5BE886A04A66FE920EA4F0D8F3319EC95C` |
| `alembic/env.py` | `79752F720472BB754999F23B5742EED9194F1F18CF58A1BF648B57D58C92092C` |
| `tests/test_windows_local.py` | `D04BA1C4D79E7AD806D859EEE47B6C65C547F8529BFF475377EA9B1841F08EE1` |
| `alembic.ini` (unchanged) | `601C011C280A625DA1DE37DE891A1A7DCA97263C67461167CE63676A195EF52E` |
| `new-tests.txt` | `4D48A1A7717C58E8ED015C2332394872675FC6B4A8827A5214A6787FCC6EAAAD` |

## Checklist closure (implementer scope)

| ID | Status | Evidence |
|---|---|---|
| C1 | Closed | Delta limited to `alembic/env.py` one line + appended fourth test; `app/windows_local.py` unchanged from its prior fix. No toolchain/deps/packaging/CI change. `worker.diff`, `alembic-env.diff`. |
| C2 | Closed | `fileConfig(..., encoding="utf-8")`; imports/branches/non-Windows behavior unchanged; logging semantics preserved by `fileConfig` itself. |
| C3 | Closed | Affected startup reads: `load_alembic_config` (already UTF-8) and `alembic/env.py` `fileConfig` (now UTF-8). `command.upgrade` does not re-read the ini elsewhere. |
| C4 | Closed | Test reproduces old downstream cp1252 failure at 3635/0x81 and verifies real `load_alembic_config -> command.upgrade -> env.py -> fileConfig` success with no DB/app; negative control confirms the chain is exercised. |
| C5 | Closed | Targeted pytest: UTF-8/`%(here)s`/`config_file_name`, head `e4b8c2d16a70`, Unicode path, downstream chain (`3 + 1 passed`). |
| C6 | Closed | Baseline prefix hash `6F1A32…384999` reproduced; `new-tests.txt` isolates the block. |
| C7 | Closed | Report, logs, `worker.diff`, `new-tests.txt`, `git-status.txt`, `git-diff-check-app.txt` in this directory. |
| C8 | Not implementer's | Last reserved Windows Codex call / counters are coordinator-owned. |
| C9 | Not implementer's | One scoped commit, non-force push and one `workflow_dispatch` require the independent PASS and separate authorization. |

## Residual risks

- The regression assertion anchors the frozen real `alembic.ini` byte offset
  (`3635`, byte `0x81`); editing earlier file content would require updating the
  test intentionally.
- Encoding contract verified against the installed Alembic 1.20.0 / Python
  3.14.4; no other version is introduced.
- Runtime/cloud install/start/health/UI/document/PDF/restart and full
  lifecycle/UAC remain NOT_RUN and are not claimed here.
