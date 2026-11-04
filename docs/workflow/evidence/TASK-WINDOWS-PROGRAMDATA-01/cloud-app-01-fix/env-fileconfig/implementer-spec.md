# Implementer spec — CLOUD-APP-01 downstream fileConfig UTF-8 fix

You are a separate OpenCode implementer. Work in
`D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`, HEAD
`8e5253b31494aba2e59efe1c8741cd7374e35322`. No native subagents. Do not commit,
push or run the workflow.

Read:
- `AGENTS.md`
- `docs/tasks/TASK-WINDOWS-PROGRAMDATA-01.md`
- `docs/workflow/APPROVALS.md` §`CLOUD_APP_01_ENV_FILE_CONFIG_FIX_AUTHORIZED_20261104`
- `docs/workflow/reviews/TASK-WINDOWS-PROGRAMDATA-01-CLOUD-APP-01-R3.md`
- `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/CLOUD-APP-01-diagnosis.md`
- the existing `app/windows_local.py` helper and `tests/test_windows_local.py`
  alembic tests (already in the working tree).

## Change (strict allowlist)

### 1. `alembic/env.py`

Change only the downstream logging read:

```python
if config.config_file_name is not None:
    fileConfig(config.config_file_name, encoding="utf-8")
    project_root = Path(config.config_file_name).resolve().parent
```

Keep all other logic, imports and non-Windows behavior unchanged. Do not alter
`alembic.ini`, toolchain, dependencies, lockfiles, packaging or CI workflows.

### 2. `tests/test_windows_local.py`

Keep the existing appended `alembic_config` tests; append a fourth self-contained
test at the end without touching the pre-existing dirty legacy/comment block:

- `test_alembic_env_fileconfig_reads_utf8_chain(tmp_path, monkeypatch)`
  - load the real repo `alembic.ini` with `load_alembic_config`;
  - `monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://edr:test@127.0.0.1:5432/test")`
    and `STORAGE_ROOT` to a temp path;
  - patch `alembic.context.configure`, `begin_transaction` (nullcontext) and
    `run_migrations` (no-op) so the real offline `command.upgrade(..., sql=True)`
    executes `env.py`/`fileConfig` without a DB;
  - monkeypatch `configparser.ConfigParser.read` so calls with
    `encoding in (None, "locale")` force `encoding="cp1252"`;
  - assert the old downstream call
    `logging.config.fileConfig(cfg.config_file_name)` raises
    `UnicodeDecodeError` at exactly 3635/0x81;
  - then call `command.upgrade(cfg, "head", sql=True)`; it must succeed through
    the fixed `alembic/env.py` `fileConfig(..., encoding="utf-8")` chain.
  - Use local imports (`configparser`, `contextlib`, `logging.config`,
    `alembic.command`, `alembic.context`, `app.windows_local`); no host DB/app.

### 3. `new-tests.txt`

After appending the fourth test, rewrite
`docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/new-tests.txt`
so it contains the **complete** new test block from the first
`def test_alembic_config_reads_utf8_and_preserves_here` to EOF (all four tests).
This is the block the coordinator will append to the HEAD test file for the
commit; the pre-existing dirty legacy block stays excluded.

## Checks (WSL approved environment)

CWD `/mnt/d/Antigravity/EquipmentDocumentationRegistry`:

```bash
.venv/bin/python -m py_compile app/windows_local.py alembic/env.py tests/test_windows_local.py
.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config" -p no:cacheprovider
.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_env_fileconfig_reads_utf8_chain" -p no:cacheprovider
```

Also record:

```powershell
git diff --check -- app/windows_local.py alembic/env.py
git status --porcelain
```

No full-suite rerun unless a failure needs diagnosis. The pre-existing dirty
test file/legacy block must remain in the working tree and be excluded from the
future commit.

## Evidence

Write to
`docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/env-fileconfig/implementer/`:
- `report.md` — changes, commands/CWD/exit, checklist closure, effective model,
  residual risks;
- `new-tests.txt` — complete new block (all four tests);
- `worker.diff` — exact app/env/test delta;
- raw check logs and `git-status.txt`.

Do not commit/push/run. Do not claim project/cloud PASS.

## Return

Send Orca `worker_done` with `--outcome succeeded` only if the fix and targeted
real-chain tests are complete; otherwise `--outcome failed`. Three sentences:
what changed, what was verified, what remains (the last R3 Astra/high review,
then the separately approved commit/push/run). Include real `--files-modified`
and `--report-path`.
