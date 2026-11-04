# Implementer spec — TASK-WINDOWS-PROGRAMDATA-01 / CLOUD-APP-01 fix

You are a separate OpenCode implementer. Work in
`D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`, HEAD
`8e5253b31494aba2e59efe1c8741cd7374e35322`. No native subagents. Do not commit,
push or run the workflow.

Read:
- `AGENTS.md`
- `docs/tasks/TASK-WINDOWS-PROGRAMDATA-01.md`
- `docs/workflow/APPROVALS.md` §`CLOUD_APP_01_UTF8_FIX_AUTHORIZED_20261104`
- `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/CLOUD-APP-01-diagnosis.md`
- `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/frozen-checklist.md`

## Change (strict allowlist)

### 1. `app/windows_local.py`

Add a module-level helper (keep the lazy Alembic imports) and use it in
`Runtime.migrate`:

```python
def load_alembic_config(path: Path):
    """Load alembic.ini explicitly as UTF-8; never let the OS locale decode it."""
    from alembic.config import Config
    cfg = Config()
    parser = cfg.file_config            # empty parser; no file read yet
    here = path.resolve().parent.as_posix()
    parser.defaults()["here"] = here    # preserve %(here)s semantics
    cfg.config_args["here"] = here
    with path.open("r", encoding="utf-8") as stream:
        parser.read_file(stream)
    cfg.config_file_name = str(path)
    return cfg


class Runtime:
    ...
    def migrate(self):
        from alembic import command
        from alembic.script import ScriptDirectory
        cfg = load_alembic_config(self.install / "alembic.ini")
        ...
```

Remove the now-unused local `from alembic.config import Config` in `migrate`
only if it becomes unused. Do not change any other behavior, CLI, ACL/owner
logic, `edr.iss`, build, toolchain, lockfiles, Alembic version or CI workflow.

### 2. `tests/test_windows_local.py`

The file is already dirty. **Do not modify the pre-existing dirty comment or
legacy-test block.** Append a self-contained new test block at the end. Use
local imports inside tests (so no top-level imports are needed), and also write
the exact same block to
`docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/new-tests.txt`
for hunk-isolation/commit purposes.

New tests (names and intent):

- `test_alembic_config_reads_utf8_and_preserves_here(tmp_path)`
  - create a UTF-8 `alembic.ini` with
    `[alembic]\nscript_location = %(here)s/alembic\n# комментарий UTF-8\n`;
  - `load_alembic_config` returns a config whose
    `script_location` resolves to `tmp_path / "alembic"` and whose
    `config_file_name` is the ini path.
- `test_alembic_config_cp1252_regression(monkeypatch)`
  - use the real repo `alembic.ini` (`Path(__file__).resolve().parents[1]`);
  - monkeypatch `configparser.ConfigParser.read` to force
    `encoding="cp1252"`;
  - assert `Config(str(ini)).file_config` raises `UnicodeDecodeError` with
    `start == 3635` and `object[start] == 0x81`;
  - assert `load_alembic_config` succeeds despite the patched `read` (it uses
    `read_file` with UTF-8).
- `test_alembic_config_head_and_unicode_path(tmp_path)`
  - load the real repo `alembic.ini` and assert
    `ScriptDirectory.from_config(cfg).get_current_head() == "e4b8c2d16a70"`;
  - create a Unicode temp directory (e.g. `"Данные"`) with an ini using
    `%(here)s`; load it and assert the interpolated path preserves the Unicode
    directory and equals the expected resolved path.

No host app/installer/working DB is used.

## Checks (approved WSL environment)

All CWD `/mnt/d/Antigravity/EquipmentDocumentationRegistry`:

```bash
.venv/bin/python -m py_compile app/windows_local.py tests/test_windows_local.py
.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config" -p no:cacheprovider
.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config_cp1252_regression or alembic_config_reads_utf8 or alembic_config_head" -p no:cacheprovider
```

(One targeted run is enough; do not run the full suite unless a failure needs
diagnosis.) Also record:

```powershell
git diff --check -- app/windows_local.py
git status --porcelain
```

The full-tree `git diff --check` may be non-zero only from pre-existing dirty
`tests/test_windows_local.py`/workflow records; record that fact. `app` must be
clean apart from the intended helper/call-site change. The pre-existing dirty
test changes must remain in the working tree and must not be modified.

## Evidence

Write to
`docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/implementer/`:
- `report.md` — changes, commands/CWD/exit codes, checklist closure, effective
  model, residual risks;
- `new-tests.txt` — exact appended test block;
- `worker.diff` — exact diff of only the app fix + the new test block (generate
  against the saved baseline if useful; the coordinator will isolate the test
  hunk);
- `git-status.txt` and raw check logs (use `.txt` suffixes where possible).

Do not commit/push/run. Do not claim project/cloud PASS.

## Return

Send Orca `worker_done` with `--outcome succeeded` only if the fix and targeted
tests are complete; otherwise `--outcome failed`. Three sentences: what changed,
what was verified, what remains (the single R3 Astra/high review, then the
separately approved commit/push/run). Include real `--files-modified` and
`--report-path`.
