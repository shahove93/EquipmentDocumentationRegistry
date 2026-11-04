# Independent R3 review spec — CLOUD-APP-01 repeat (env.py fileConfig)

You are the independent Codex reviewer for the **repeat R3 Astra/high** review
of the original TASK-WINDOWS-PROGRAMDATA-01 / CLOUD-APP-01 fix. This consumes the
**last remaining reserved Windows Codex call**. You are read-only: do not edit
files, run shell edits, start the app/installer/DB/VM or touch remote Git.

Repository: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`,
HEAD `8e5253b31494aba2e59efe1c8741cd7374e35322`.

## Authority and accounting

- Approval: `docs/workflow/APPROVALS.md`
  §`CLOUD_APP_01_ENV_FILE_CONFIG_FIX_AUTHORIZED_20261104` (user: «Разрешаю.»).
- Original logical TASK; not a new TASK/approach. Previous R3 FAIL
  CLOUD-UTF8-R3-01 is retained as history.
- This is the **last** reserved Windows Codex call (Astra/high). After it:
  reserved Windows calls = **0**.
- CI TASK remains 4 full reviews / 4 Codex calls. ProgramData/lifecycle
  attempts, security waiver and counters are preserved.
- **If this review FAILs or the provider is exhausted: stop.** No new
  fix/review/run.
- After PASS only: one scoped commit, non-force push, exactly one Windows
  `workflow_dispatch`. No rerun on cloud failure.
- Full lifecycle/UAC PASS is not granted.

## Finding and correction

Previous R3 FAIL: `alembic/env.py:12-13` re-reads the UTF-8 `alembic.ini` through
`logging.config.fileConfig(config.config_file_name)` with locale encoding
(cp1252), after the app loader was fixed.

Correction:
- `app/windows_local.py`: `load_alembic_config` explicit UTF-8 (already reviewed
  as correct).
- `alembic/env.py`: `fileConfig(config.config_file_name, encoding="utf-8")`.
- `tests/test_windows_local.py`: fourth test
  `test_alembic_env_fileconfig_reads_utf8_chain`:
  - loads the real ini via `load_alembic_config`;
  - forces `ConfigParser.read` to cp1252 when `encoding in (None, "locale")`;
  - asserts the old direct `fileConfig` path raises `UnicodeDecodeError` at
    3635/0x81;
  - runs real offline `command.upgrade(cfg, "head", sql=True)` with
    `context.configure`/`begin_transaction`/`run_migrations` patched, so
    `env.py`/`fileConfig` executes without a DB and succeeds;
  - negative control (reverting env.py) failed exactly in env.py/fileConfig.
- Dirty-test isolation: final committed test file = HEAD + all four new tests.
  Raw CRLF packet file SHA-256 `9D46EB07…B0DACDF0`; git LF-normalized blob
  `E109E27B…E0FF9E8`. Pre-existing dirty legacy block excluded.

Evidence:
- `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/env-fileconfig/`
  (`frozen-checklist.md`, `baseline-hashes.txt`, `implementer/`).
- Review packet: `.../env-fileconfig/review-packet/`
  (`app.diff`, `env.diff`, `new-tests.txt`, `committed-tests.py`,
  `implementer-report.md`, `negative-control.txt`, pytest/py_compile logs,
  `git-status.txt`).
- Previous diagnosis: `.../CLOUD-APP-01-diagnosis.md`; prior R3 FAIL:
  `docs/workflow/reviews/TASK-WINDOWS-PROGRAMDATA-01-CLOUD-APP-01-R3.md`.

## Checklist

1. **App + env fix:** explicit UTF-8 in both `load_alembic_config` and
   `alembic/env.py fileConfig`; preserves Config options, `%(here)s`,
   `config_file_name`, relative scripts, Unicode paths and non-Windows behavior.
2. **All startup reads covered:** no other read of the same ini in the affected
   `command.upgrade`/env path; no architecture expansion.
3. **Real-chain regression:** the fourth test actually executes
   `load_alembic_config -> command.upgrade -> env.py -> fileConfig`, reproduces
   the old downstream cp1252 failure and passes after the fix; no DB/app/
   installer. Negative control supports this.
4. **Dirty isolation:** committed test file = HEAD + four new tests; raw CRLF
   `9D46…`, LF blob `E109…`; pre-existing dirty legacy block excluded. Stop if
   separation is not possible.
5. **Scope:** product delta only `app/windows_local.py`, `alembic/env.py`,
   test block; no toolchain/deps/packaging/CI-guard changes.
6. **Evidence:** targeted pytest 4 passed (or equivalent), py_compile 0,
   `git diff --check` scope clean, exact commands/CWD/exits.
7. **Accounting:** last R3 Astra/high reserved call; after it 0; CI 4/4 and
   ProgramData counters/waiver preserved.
8. **No host install/VM/DB/UAC/release/deploy.**

You may rerun a targeted read-only check only for a genuine evidence gap; do
not broaden the checklist or start the app.

## Verdict

- **PASS** — fix closes CLOUD-UTF8-R3-01, scoped, regression-tested; coordinator
  may proceed to the approved commit/push/run. List MINOR/NIT only.
- **FAIL** — any BLOCKER/MAJOR. List stable IDs, criterion, location, observed
  result, reproduction/evidence, expectation, severity. Stop; no further
  fix/review/run.

Do not write files. End after the verdict with Orca `worker_done`
(outcome succeeded for PASS, failed for FAIL), a three-sentence summary,
findings and evidence paths.
