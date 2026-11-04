# Independent R3 review spec — CLOUD-APP-01 UTF-8 fix (original ProgramData TASK)

You are the independent Codex reviewer for the scoped reopening of
**TASK-WINDOWS-PROGRAMDATA-01** for CLOUD-APP-01. Route: **R3 Astra/high**
(MODEL-ROUTING original-task route). You are read-only: do not edit files, do
not run shell edits, do not start the app/installer/DB/VM, and do not touch
remote Git. Inspect the actual files/evidence and return one verdict.

Repository: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`,
HEAD `8e5253b31494aba2e59efe1c8741cd7374e35322`.

## Authority and accounting

- Approval: `docs/workflow/APPROVALS.md`
  §`CLOUD_APP_01_UTF8_FIX_AUTHORIZED_20261104` (user: «разрешаю»).
- This is a **scoped reopening of the original Windows ProgramData TASK**, not a
  new CI TASK and not A2. It consumes **one of the two reserved Windows Codex
  calls** (this R3 review). The second remains unspent.
- CI TASK remains 4 full reviews / 4 Codex calls. ProgramData/lifecycle
  attempts, security waiver and previous counters are preserved.
- **If this review FAILs or the provider is exhausted: stop.** No second
  reserved call, no additional fix/review.
- After PASS only: one scoped commit, one non-force push, exactly one Windows
  `workflow_dispatch` on the published headSha. No rerun on cloud failure.
- Full lifecycle/UAC PASS is not granted.

## Finding and change under review

Cloud run `41886936093` failed at app startup with
`UnicodeDecodeError: 'charmap' codec can't decode byte 0x81 in position 3635`.
RCA: `alembic.ini` is UTF-8; Alembic 1.20.0 `Config.file_config` reads it with
`encoding="locale"` (cp1252 on the runner); `app/windows_local.py:284` used
`Config(str(...))`.

Correction:
- `app/windows_local.py`: new module-level `load_alembic_config(path)` that
  creates `Config()`, reuses its empty `file_config`, sets `%(here)s` and
  `config_args["here"]` to the config parent, reads via
  `parser.read_file(stream)` with `encoding="utf-8"`, then sets
  `config_file_name`; `Runtime.migrate` calls it.
- `tests/test_windows_local.py`: three appended self-contained tests:
  UTF-8/`%(here)s`/config_file_name; forced-cp1252 regression at 3635/0x81
  with the original config path and the fixed loader; real head
  `e4b8c2d16a70` plus a Unicode `Данные` path.
- Dirty-test isolation: the file already had unrelated dirty changes. The
  commit will contain `committed-tests.py` = HEAD test file + only the new
  test block (hash `93745588…9FD92723`), not the pre-existing dirty
  comment/legacy block. Verify this.

Evidence:
- `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/cloud-app-01-fix/`
  (`frozen-checklist.md`, `baseline-hashes.txt`, `new-tests.txt`,
  `implementer/`).
- Review packet: `.../cloud-app-01-fix/review-packet/`
  (`app.diff`, `new-tests.txt`, `new-tests.diff`, `committed-tests.py`,
  `implementer-report.md`, `worker.diff`, `git-status.txt`,
  `frozen-checklist.md`).
- Diagnosis: `docs/workflow/evidence/TASK-WINDOWS-PROGRAMDATA-01/CLOUD-APP-01-diagnosis.md`.

## Checklist

1. **App fix:** explicit UTF-8 read; preserves Alembic options, `%(here)s`,
   `config_file_name`, relative `script_location` and Unicode paths; same head
   `e4b8c2d16a70`. No CLI/ACL/owner-waiver/behavior change.
2. **No workarounds:** no `PYTHONUTF8`/`-X utf8`, no
   `errors="replace"/"ignore"`, no ASCII stripping, no silent conversion.
3. **Tests:** reproduce cp1252 `UnicodeDecodeError` on the original
   `Config(file_config)` path at exactly 3635/0x81; fixed loader succeeds;
   cover UTF-8 `%(here)s`, `config_file_name`, head and a Unicode path; no host
   app/installer/working DB.
4. **Dirty-test isolation:** committed test file is HEAD + new test block only
   (`committed-tests.py`, hash `93745588…9FD92723`); pre-existing dirty
   comment/legacy-test changes are not in the commit. Stop if separation is
   not possible.
5. **Scope:** product delta only `app/windows_local.py` and the new test block;
   no lockfile, Alembic-version, toolchain, CI workflow, packaging or
   `alembic.ini` change.
6. **Evidence:** targeted WSL pytest/py_compile exit 0; no full-suite rerun;
   exact commands/CWD/exits; `git diff --check -- app/windows_local.py` 0;
   full-tree non-zero only from pre-existing HISTORY.md blank line.
7. **Accounting:** this is the one R3 Astra/high review consuming one reserved
   Windows call; second reserved call untouched; CI 4/4 preserved;
   ProgramData/lifecycle counters/waiver preserved.
8. **No host install/VM/DB/UAC/release/deploy.**

You may inspect/rerun targeted read-only checks if the evidence has a gap; do
not broaden the checklist or start the app.

## Verdict

- **PASS** — fix is correct, scoped, regression-tested and preserves behavior;
  coordinator may proceed to the approved commit/push/run. List MINOR/NIT only.
- **FAIL** — any BLOCKER/MAJOR. List stable IDs, criterion, location, observed
  result, reproduction/evidence, expectation, severity. Stop; no further
  fix/review/run.

Do not write files. End after the verdict with Orca `worker_done`
(outcome succeeded for PASS, failed for FAIL), a three-sentence summary,
findings and evidence paths.
