# CLOUD-APP-01 UTF-8 Alembic fix — implementer report

- TASK: TASK-WINDOWS-PROGRAMDATA-01 / CLOUD-APP-01 scoped fix
- Approval: `CLOUD_APP_01_UTF8_FIX_AUTHORIZED_20261104`
- Implementer: OpenCode worker, effective model `deepseek/deepseek-flash`
- Repo: `D:/Antigravity/EquipmentDocumentationRegistry`, WSL path
  `/mnt/d/Antigravity/EquipmentDocumentationRegistry`
- Branch `main`, HEAD `8e5253b31494aba2e59efe1c8741cd7374e35322` (unchanged)
- No commit, push, workflow run, host install, VM, UAC or working-DB access.

## Changes

### `app/windows_local.py`

Added module-level `load_alembic_config(path)` immediately before `class Runtime`.
It constructs an empty `Config()`, reuses its `file_config` parser without reading
the file, sets `%(here)s` to the resolved parent directory (both the parser
default and `config_args`), opens `path` with explicit `encoding="utf-8"`, calls
`parser.read_file(stream)` and finally sets `cfg.config_file_name = str(path)`.
Alembic imports remain lazy inside the helper.

`Runtime.migrate` now calls `load_alembic_config(self.install / "alembic.ini")`;
the unused local `from alembic.config import Config` was removed. No other
behavior, CLI, ACL/owner, packaging, lockfile, Alembic-version, toolchain or CI
change. No `PYTHONUTF8`, `errors="replace"/"ignore"` or ASCII stripping.

SHA-256 after fix: `BFEB2F3F826315655B3C52B44F40CF5BE886A04A66FE920EA4F0D8F3319EC95C`
(before: `648F15B5E08185D4FA9FAB4ED457D81ABD31CDD0878EB439E87065D30E613C4A`).

### `tests/test_windows_local.py`

Appended three self-contained tests at end of file; pre-existing dirty
comment/legacy-test block was not touched. Exact appended block is in
`new-tests.txt` and `new-tests.diff`.

- `test_alembic_config_reads_utf8_and_preserves_here` — UTF-8 ini with a
  Cyrillic comment and `%(here)s`; asserts the interpolated
  `script_location` resolves to `tmp_path/alembic` and `config_file_name` is
  the ini path.
- `test_alembic_config_cp1252_regression` — monkeypatches
  `configparser.ConfigParser.read` to force `encoding="cp1252"`; the old
  `Config(str(ini)).file_config` raises `UnicodeDecodeError` with
  `start == 3635` and `object[start] == 0x81`; `load_alembic_config` still
  succeeds.
- `test_alembic_config_head_and_unicode_path` — real repo ini yields head
  `e4b8c2d16a70`; a `Данные` temp directory with `%(here)s` interpolates to the
  Unicode path and matches the expected resolved path.

SHA-256 after append: `DE351E89E055F3AEB212462712FDC0D6A111BD2FDF94FC995BF0EAB81895018F`.
Baseline dirty test file (`baseline-tests-dirty.py` in the frozen checklist,
`6F1A32489FCB7C956AE2337E75678F0F9338A70F11F8D73E9BA05C82BB384999`) was
reconstructed by truncating only the appended block; its SHA-256 matches the
frozen baseline exactly, proving the pre-existing dirty content is preserved
and only the new block was added.

## Commands, CWD and exit codes

All WSL checks ran with CWD `/mnt/d/Antigravity/EquipmentDocumentationRegistry`
using the approved `.venv/bin/python` (Python 3.14.4, Alembic 1.20.0).

| Command | Exit |
|---|---|
| `.venv/bin/python -m py_compile app/windows_local.py tests/test_windows_local.py` | 0 |
| `.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config" -p no:cacheprovider` | 0 |
| `.venv/bin/python -m pytest -q tests/test_windows_local.py -k "alembic_config_cp1252_regression or alembic_config_reads_utf8 or alembic_config_head" -p no:cacheprovider` | 0 |

Both targeted runs: `3 passed, 43 deselected, 1 warning` (pre-existing
Starlette/httpx deprecation). Logs: `py_compile.txt`,
`pytest-alembic_config.txt`, `pytest-alembic_config-intersection.txt`;
runner: `run-checks.sh`. No full-suite rerun.

Windows Git commands with CWD `D:/Antigravity/EquipmentDocumentationRegistry`:

| Command | Exit | Notes |
|---|---|---|
| `git diff --check -- app/windows_local.py` | 0 | only CRLF-will-be-replaced warning |
| `git status --porcelain` | 0 | output in `git-status.txt` |
| `git diff --check` (full tree) | 2 | pre-existing `docs/workflow/HISTORY.md:2342: new blank line at EOF`; CRLF warnings for pre-existing dirty files. `app/` is clean apart from the intended change. |

`git diff --check` non-zero is not from this fix: the only reported whitespace
error is the pre-existing HISTORY.md blank line at EOF; all other lines are
Git CRLF conversion warnings.

## Checklist closure (implementer scope)

| ID | Status | Evidence |
|---|---|---|
| C1 | Closed for implementer | Diff limited to `app/windows_local.py` + appended test block; no packaging/CI/lockfile/alembic-version change. |
| C2 | Closed | Explicit UTF-8 read; options, `%(here)s`, `config_file_name`, Unicode path and head `e4b8c2d16a70` verified by tests. |
| C3 | Closed | No `PYTHONUTF8`, no `errors="replace"`/`"ignore"`, no ASCII stripping; diff inspection. |
| C4 | Closed | cp1252 reproducer at exact offset 3635/0x81; fix passes; config/head/relative `%(here)s`/Unicode path covered without app/installer/DB. |
| C5 | Closed | Targeted WSL `.venv/bin/python` runs only; no full suite. |
| C6 | Closed | Baseline hash `6F1A32…384999` reproduced from pre-append file; `new-tests.txt`/`new-tests.diff` isolate the block. |
| C7 | Closed | No host install, VM, working DB, UAC change, release/deploy. |
| C8 | Closed | This report, `app.diff`, `new-tests.diff`, `worker.diff`, `new-tests.txt`, `git-status.txt`, `git-diff-check-app.txt`, `git-diff-check-full.txt`, pytest/compile logs. |
| C9 | Not implementer's | One R3 Astra/high review is coordinator-owned; counters untouched. |
| C10 | Not implementer's | Commit/push/workflow_dispatch require separate approval after PASS. |

## Residual risks

- The cp1252 regression asserts the frozen real `alembic.ini` byte offset
  (`3635`, byte `0x81`); any future edit to that file's earlier content would
  change the offset and must update the test. This is intentional evidence
  anchoring, not a runtime dependency.
- Header contract verified against the installed Alembic 1.20.0; a different
  Alembic version is out of scope and must not be introduced.
- Full lifecycle/UAC/cloud criteria remain NOT_RUN and are not claimed here.
