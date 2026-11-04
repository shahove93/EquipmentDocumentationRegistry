# CLOUD-APP-01 — read-only RCA and fix proposal (original Windows TASK)

Status: **diagnosis only.** No product edits, host install, VM/DB access, commit,
push, workflow run or new Codex review was performed. This finding belongs to
the original Windows program-data/runtime + lifecycle logical TASK, **not**
TASK-CI-WINDOWS-01. The CI TASK's 4 reviews / 4 Codex calls and all
ProgramData/lifecycle counters/waiver are preserved; the two reserved Windows
Codex calls are untouched. No review or run is requested by this document.

- Cloud run: `41886936093`, head
  `8e5253b31494aba2e59efe1c8741cd7374e35322`, conclusion failure.
- Evidence:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/cloud-run-41886936093/run.log`.
- Remote artifact `windows-installer-evidence` (ID `13352476524`,
  73,228,696 bytes) remains at the run URL. Two bounded local downloads timed
  out before completion (~4.9 MB); no repeat loop was run.

## 1. Observed cloud failure

The run succeeded through:

- frontend build;
- pinned Python/PostgreSQL downloads and SHA-256;
- official Inno Setup 6.7.3 download, SHA-256
  `9C73C3…B732`, Valid Authenticode `CN=Pyrsys B.V.`;
- `Build installer` (including the new compiler-version check);
- silent install (exit 0) and installed-file presence:
  `python\python.exe`, `launcher.ps1`, `alembic.ini`, `ui\index.html`,
  `%ProgramData%\EDR\runtime\postgresql\bin\postgres.exe`.

Then the installed app was started with
`...\edr-ci-install\python\python.exe -B -m app.windows_local start --no-browser`
and exited 1:

```text
EDR: UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 3635:
character maps to <undefined>
ci-installer failed: AssertionError: supervisor exited during startup with 1
```

### Exact traceback

The cloud log contains **no Python traceback**, only the message above: the
app catches the exception and prints only `EDR: <type>: <message>`
(`app/windows_local.py:518-519,537-539`), and `ci-installer.py` tails the same
one-line supervisor log. The artifact would contain the same one-line message,
not a traceback.

A representative traceback reproduced from the same Alembic code path under a
forced cp1252 decode (local WSL, pinned Alembic 1.20.0; not a cloud traceback):

```text
File ".../alembic/config.py", line 250, in file_config
    compat.read_config_parser(file_config, [self._config_file_path])
File ".../alembic/util/compat.py", line 130, in read_config_parser
    return file_config.read(file_argument, encoding="locale")
File "/usr/lib/python3.14/configparser.py", line 754, in read
    self._read(fp, filename)
...
UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 3635:
character maps to <undefined>
```

## 2. Acting versions and encoding contract

- App runtime: embedded **CPython 3.12.10** (build contract; installed
  interpreter).
- Config library: **Alembic 1.20.0** (`requirements.lock`; cloud payload
  `alembic-1.20.0.dist-info`).
- Inspected Alembic 1.20.0 source (installed pinned package; also official
  `alembic/config.py`):
  - `Config.__init__` has **no `encoding` parameter**;
  - `Config.file_config` calls `compat.read_config_parser(...)`;
  - `compat.read_config_parser` calls
    `file_config.read(file_argument, encoding="locale")`.

The official PyPI sdist
`https://files.pythonhosted.org/packages/ed/aa/02910bdb8e2f1444f6654d5b296cd827d126f82209050ee7b1000f92ac4b/alembic-1.20.0.tar.gz`
confirms the same lines: `alembic/util/compat.py:130`
`return file_config.read(file_argument, encoding="locale")`,
`alembic/config.py:250` `compat.read_config_parser(...)`, and
`__version__ = "1.20.0"`.

`encoding="locale"` resolves to the process locale; on the English
`windows-latest` runner that is cp1252. The app’s embedded Python is not in UTF-8
mode and `-B`/`-X utf8` is not used, so the default is the Windows locale.

## 3. Root cause (confirmed, not byte-offset-only)

`alembic.ini` is valid UTF-8 (5,218 bytes). Its first non-ASCII byte is at offset
3,593; the failing byte at 3,635 is `0x81`, part of the UTF-8 Russian comment:

```text
# URL намеренно не задан здесь: он подставляется из переменной окружения
```

Evidence chain:

1. The installed app calls
   `Config(str(self.install / "alembic.ini"))` at `app/windows_local.py:284`.
2. Alembic 1.20.0 `Config.file_config` reads that file with
   `encoding="locale"` via `compat.read_config_parser`.
3. On cp1252, decoding the real `alembic.ini` fails with exactly
   `byte 0x81 in position 3635`.
4. Forcing the actual `Config.file_config` read path to cp1252 reproduces the
   same `UnicodeDecodeError` and position.
5. The proposed explicit-UTF-8 loader reads the same file and yields the same
   Alembic head `e4b8c2d16a70` and `script_location ./alembic` under Alembic
   1.20.0.

This is therefore a product runtime encoding defect, not a CI defect.

## 4. Minimal portable fix (text proposal; not applied)

Owner: original Windows program-data/runtime TASK (lifecycle acceptance owns the
cloud criterion). Allowlist for a future scoped reopening:
- `app/windows_local.py` (helper + one call site);
- `tests/test_windows_local.py` (regression tests);
- optional targeted docs note.
No CI workflow, installer, build, dependency or `alembic.ini` content change is
required.

Proposed helper in `app/windows_local.py` (module level, near `Runtime`):

```python
def load_alembic_config(path: Path):
    """Load alembic.ini explicitly as UTF-8; never let the OS locale decode it."""
    from alembic.config import Config
    cfg = Config()
    parser = cfg.file_config          # empty parser; no file read yet
    here = path.resolve().parent.as_posix()
    parser.defaults()["here"] = here  # preserve %(here)s semantics
    cfg.config_args["here"] = here
    with path.open("r", encoding="utf-8") as stream:
        parser.read_file(stream)
    cfg.config_file_name = str(path)
    return cfg
```

Call site in `Runtime.migrate` (replace only the config construction):

```python
cfg = load_alembic_config(self.install / "alembic.ini")
```

Why this is the preferred variant:
- explicit `encoding="utf-8"` contract; independent of runner/user locale;
- no `errors="replace"/"ignore"`, no silent conversion or loss of Unicode;
- path handling stays `pathlib`/Unicode-safe; `%(here)s` and relative
  `script_location` are preserved (verified with a temp Unicode `%(here)s`
  config);
- `ScriptDirectory.from_config(cfg).get_current_head()` remains
  `e4b8c2d16a70` (verified with Alembic 1.20.0);
- no new dependency and no `PYTHONUTF8=1`/`-X utf8` process-wide workaround.

Alternatives and limitations:
- **ASCII-only `alembic.ini`**: works for this file but only masks the class of
  bug; future/user configs with non-ASCII still fail; changes documentation
  text. Not preferred.
- **`PYTHONUTF8=1`/`-X utf8`**: process-wide default change, masks the defect,
  can alter other text I/O; not an explicit config contract. Not preferred.
- **`errors="replace"`/`"ignore"`**: silent data loss; unacceptable.

## 5. Regression reproducer (no app startup/DB, Windows cp1252/code page)

All steps are read-only and can run on Linux or Windows:

1. Exact byte failure:
   ```python
   from pathlib import Path
   raw = Path("alembic.ini").read_bytes()
   try:
       raw.decode("cp1252")
       raise AssertionError("expected failure")
   except UnicodeDecodeError as e:
       assert e.start == 3635 and e.object[e.start] == 0x81
   ```
2. Actual Alembic path under cp1252 (monkeypatch only the test read):
   ```python
   import configparser
   from alembic.config import Config
   original = configparser.ConfigParser.read
   configparser.ConfigParser.read = (
       lambda self, files, encoding=None:
       original(self, files, encoding="cp1252"))
   try:
       Config("alembic.ini").file_config
       raise AssertionError("expected failure")
   except UnicodeDecodeError as e:
       assert e.start == 3635 and e.object[e.start] == 0x81
   finally:
       configparser.ConfigParser.read = original
   ```
3. Fixed loader:
   ```python
   cfg = load_alembic_config(Path("alembic.ini"))
   assert cfg.get_main_option("script_location")
   assert ScriptDirectory.from_config(cfg).get_current_head() == "e4b8c2d16a70"
   ```
   No database, no app start, no installer.

## 6. Safe unit-test plan (future scoped fix)

Add to `tests/test_windows_local.py`:
- `test_alembic_config_reads_utf8`: temp `alembic.ini` with Cyrillic and a
  `%(here)s` `script_location`; loader returns the expected option and
  interpolated path.
- `test_alembic_config_cp1252_regression`: monkeypatch
  `configparser.ConfigParser.read` to cp1252; assert the old `Config(path)`
  raises the exact `UnicodeDecodeError`; assert the new loader succeeds.
- `test_alembic_head_unchanged`: `ScriptDirectory.from_config(loader(path))
  .get_current_head() == "e4b8c2d16a70"`.
- Run in WSL `.venv/bin/python -m pytest` and in the Windows CI; no DB or
  app-start requirement.

## 7. Decision required from the user

- Reopen the **original Windows logical TASK** for a scoped product fix with
  the allowlist above, preserving its saved counters/waiver and the two reserved
  Windows Codex calls.
- Decide whether to spend one reserved Windows Codex call on an independent
  review of that product fix (not spent here).
- After the fix and review, approve **one** new cloud run. No automatic
  implementation/review/rerun is started by this diagnosis.

## 8. Non-claims

- No full Windows/UAC/lifecycle PASS; health/UI/document/PDF/restart remain
  NOT_RUN.
- CI TASK remains at 4 reviews / 4 calls; this finding does not consume or reset
  them.
