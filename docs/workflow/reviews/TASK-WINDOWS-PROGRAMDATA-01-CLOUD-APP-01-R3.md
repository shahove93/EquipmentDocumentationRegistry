# TASK-WINDOWS-PROGRAMDATA-01 — CLOUD-APP-01 R3 review (FAIL)

- Reviewer: Codex `gpt-6-astra`, effort `high`, read-only.
- Orca Task `task_2b2fae270c13`, Dispatch `ctx_b453d727f193`,
  Run `run_b556ddaf13c3`, terminal `term_e2fae7cb-3400-4341-aff5-96c7aa0bdf51`.
- Worker result: `worker_done` msg_f031115b589a, outcome `failed` (verdict FAIL).
- Revision: `main` HEAD
  `8e5253b31494aba2e59efe1c8741cd7374e35322` plus the scoped working-tree fix.
- Evidence:
  `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/`.

## Verdict

**FAIL — no commit, push or cloud run.** The explicit UTF-8 loader, options/
`%(here)s`/`config_file_name`/head tests, dirty-test isolation (HEAD + new test
block; baseline prefix `6F1A3248…384999`), and targeted pytest/py_compile
evidence are valid. However, the fix is incomplete for the actual migration
path.

## Finding

**CLOUD-UTF8-R3-01 — MAJOR — criteria C2/C4 (app fix / regression coverage).**

- Location: `app/windows_local.py` (new loader usage) and
  `alembic/env.py:12-13`.
- Observed: `command.upgrade` loads `alembic/env.py`, which calls
  `logging.config.fileConfig(config.config_file_name)`. `fileConfig` defaults to
  locale encoding and **re-reads the same UTF-8 `alembic.ini`**, failing again at
  byte `0x81`, position `3635`. The submitted tests only inspect
  `Config`/`ScriptDirectory.get_current_head()` and never exercise this
  downstream logging read.
- Reproduction (reviewer's focused read-only WSL probe; independently
  reproduced here):
  - load `alembic.ini` through the fixed `load_alembic_config` → succeeds;
  - force `configparser.ConfigParser.read` to `encoding="cp1252"` (the runner
    locale) and call `logging.config.fileConfig(cfg.config_file_name)`;
  - result: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in
    position 3635`, exit for the probe 0, no migration environment/DB loaded.
- Supporting source: `alembic/env.py:12-13`
  `if config.config_file_name is not None: fileConfig(config.config_file_name)`;
  Python `logging.config.fileConfig` signature
  `(fname, defaults=None, disable_existing_loggers=True, encoding=None)` reads
  via `cp.read(fname, encoding=encoding)` with `encoding=None` → locale.
- NIT **CLOUD-UTF8-R3-N1**: the committed-test artifact is LF-normalized
  (`93745588…9FD92723`); its raw CRLF SHA-256 is
  `A424FC6545147551FB1473A36A045920951518BCBEB10A30E48FA5F9C7651BEE`. Not a
  blocker.

## Accounting

- Consumes **one of the two reserved Windows Codex calls** (R3 Astra/high);
  the second remains unspent.
- CI TASK remains 4 full reviews / 4 Codex calls.
- ProgramData/lifecycle attempts, security waiver and previous counters are
  preserved.
- No files were written by the reviewer; no app/installer/DB/VM/remote Git was
  started or touched.
- Per the approval: stop; no additional fix, review or cloud run under the
  current decision. Full lifecycle/UAC PASS is not granted.

## Options for a new user decision (not executed)

1. Expand the scoped allowlist to `alembic/env.py` (and tests) and pass
   `encoding="utf-8"` to `logging.config.fileConfig`, or read the logging ini
   explicitly with UTF-8 before `fileConfig`; add a regression test that
   exercises the `command.upgrade`/logging path without a real DB (e.g.,
   monkeypatch the config path/locale read).
2. Keep the app-only helper but supply an already-UTF-8 `ConfigParser` to the
   logging configuration path (more code; still a product change).
3. ASCII-only `alembic.ini` is the limited alternative; it would fix both reads
   but leaves the encoding class of bug and changes comments.

Any product change needs a new scoped approval, a decision on the remaining
reserved Windows call, and a new cloud-run approval.
