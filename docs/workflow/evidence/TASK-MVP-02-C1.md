# TASK-MVP-02 / C1 — отчёт исполнителя

## Идентификация

- TASK: TASK-MVP-02 — report-only сверка осиротевших blob-файлов.
- Подход / цикл: A1 / C1.
- Класс риска: R2.
- Baseline: design `7b785f4`; фактический HEAD перед работой `e3e6f81`
  (workflow-коммит диспатча); базовый коммит результата `a2b52a8`.
- Run / Task / Dispatch Orca: `run_68046cea3eb4` / `task_508a5a075dd1` /
  `ctx_f615074805a8`.
- Исполнитель: отдельный OpenCode-исполнитель (Orca worker,
  `term_6fac721d-ea65-4558-a11c-d809b555a6d6`).
- Среда: `D:\Antigravity\EquipmentDocumentationRegistry`
  (`/mnt/d/Antigravity/EquipmentDocumentationRegistry`), ветка `main`.
- Дата: 2026-10-22.

## Что сделано

Добавлена безопасная **report-only** сверка: `LocalStorageBackend.iter_files()`
обходит только `STORAGE_ROOT/documents` без symlink и выхода за root,
`app/services/storage_reconciliation.py` полностью собирает файловый инвентарь
до обращения к БД, затем в отдельном соединении выполняет один
`SELECT files.storage_key` и формирует `F \ D`. CLI
`python -m app.reconcile_storage` печатает один JSON-объект в stdout и
использует exit 0/1/2. Удаления, DML, commit, блокировки, запись в журнал и
расписание отсутствуют.

| Файл | Назначение |
| --- | --- |
| `app/services/local_storage.py` | `StorageInventoryError`, `StoredFileInfo`, `iter_files(prefix)`; fd-based обход без symlink, не-обычных файлов и выхода за root |
| `app/services/storage_reconciliation.py` | `reconcile_storage()`, `failure_report()`, `is_canonical_storage_key()`, `CANONICAL_BLOB_PATTERN`; инвентарь до БД, один SELECT, безопасные ошибки |
| `app/reconcile_storage.py` | CLI `main(argv=None) -> int`; `--help` без `.env`/БД, JSON, exit 0/1/2, безопасный stderr |
| `tests/test_storage.py` | `TestIterFiles`: рекурсия, метаданные, UTC, пустой файл, prefix/root/namespace, symlink, FIFO, unreadable, vanished |
| `tests/test_storage_reconciliation.py` | Контракт отчёта, канонические ключи, matched/orphans/ignored, `LOG_FILE`, порядок инвентаря и SELECT, read-only |
| `tests/test_reconcile_storage_cli.py` | `--help`, exit 2, успешный JSON/exit 0, сбои конфигурации/БД/storage, redaction |
| `docs/adr/ADR-009-document-attachments.md` | Статус сверки и открытый вопрос: report-only, без удаления и расписания |
| `docs/adr/README.md` | Статусные строки ADR-009; устранена устаревшая запись о постоянном журнале |
| `docs/PROJECT_STATUS.md` | Статус сверки, ограничения 27/28, рекомендуемый следующий этап |

Коммит: `a2b52a8e27b77e25dd0165cee9864ccf57689aed` —
`feat(storage): add report-only orphan blob reconciliation`, 9 файлов,
`1541 insertions(+), 29 deletions(-)`.

## Выполненные проверки

Все команды запускались из WSL Ubuntu; внешний CWD —
`D:\Antigravity\EquipmentDocumentationRegistry` (корень репозитория).

| # | Команда | CWD | Exit | Фактический результат | Источник |
| --- | --- | --- | --- | --- | --- |
| 1 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_storage.py tests/test_storage_reconciliation.py tests/test_reconcile_storage_cli.py'` | корень | 0 | `124 passed` | вывод исполнителя |
| 2 | та же команда с добавлением `tests/test_file_service.py tests/test_file_service_concurrency.py` | корень | 0 | `377 passed in 65.47s` (финальный повтор после коммита) | вывод исполнителя |
| 3 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | 0 | `3474 passed, 1 warning in 465.84s (0:07:45)`; 0 failed; 3474 = 3400 + 74 | вывод исполнителя |
| 4 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage --help >/dev/null; echo "HELP_EXIT:$?"'` | корень | 0 | `HELP_EXIT:0`; help без `.env`/БД | вывод исполнителя |
| 5 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage; echo "EXIT:$?"'` | корень | 0 | Валидный JSON: `status=ok`, `scanned_blobs=3`, `matched_blobs=3`, `orphan_count=0`, `orphan_bytes=0`; `EXIT:0` | вывод исполнителя |
| 6 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | 0 | `12` | вывод исполнителя |
| 7 | `git show --stat --oneline HEAD`; `git show --name-only --format= HEAD` | корень | 0 | `a2b52a8 ...`; 9 разрешённых файлов; evidence отсутствует | вывод исполнителя |
| 8 | `git diff --name-only e3e6f81..HEAD` | корень | 0 | только 9 файлов из allowlist | вывод исполнителя |
| 9 | `git diff --check e3e6f81..HEAD` | корень | 0 | ошибок пробелов нет | вывод исполнителя |
| 10 | `git status --porcelain=v1 --untracked-files=all` до создания evidence | корень | 0 | пусто | вывод исполнителя |
| 11 | `git status --porcelain=v1 --untracked-files=all` после создания evidence | корень | 0 | только `?? docs/workflow/evidence/TASK-MVP-02-C1.md`; evidence не закоммичен | вывод исполнителя |

Предупреждение полного прогона — прежнее
`StarletteDeprecationWarning` (`httpx` в `starlette.testclient`), не связано с
TASK.

## Соответствие критериям приёмки

Исполнитель не присваивает проектный PASS; таблица фиксирует фактические
доказательства для ревьюера.

| ID | Статус | Доказательство |
| --- | --- | --- |
| AC-001 | done | Проверки 4–5; CLI-тесты `--help` без `DATABASE_URL`, отсутствие создания `STORAGE_ROOT`/`LOG_FILE`, запуск на временном storage |
| AC-002 | done | `TestCanonicalKey`; тесты полного ключа, нескольких документов, одинакового basename в другом документе, вложенных каталогов и нулевого blob |
| AC-003 | done | `test_classifies_ignored_regular_files` (7 ignored, 1 scanned), `test_log_file_is_excluded_even_when_it_looks_canonical`; symlink/каталоги/не-обычные файлы не попадают в счётчики |
| AC-004 | done | `TestIterFiles`: неверные prefix, symlink файла/каталога/namespace внутрь и наружу root, подмена и исчезновение записи, unreadable и отсутствующий root |
| AC-005 | done | `test_inventory_finishes_before_one_select_in_its_own_connection` (1 checkout, 1 SELECT, инвентарь завершён), `test_select_runs_even_with_empty_inventory`; DML/`FOR UPDATE` отсутствуют |
| AC-006 | done | `test_files_database_blobs_and_journal_are_unchanged` (строки/статусы/история/blob/mtime/журнал до и после, два запуска), `test_does_not_create_root_or_journal` |
| AC-007 | done | CLI-тесты JSON-контракта, сортировки, summary, stdout/stderr, exit 0/1/2; проверки отсутствия temp-пути, DSN и SQL; кандидаты не дают exit 1 |
| AC-008 | done | Тесты missing root без mkdir; пустой root/`documents` — успех после SELECT; namespace-file; DB/config failure; partial inventory без кандидатов и без SELECT; unreadable/vanished в `TestIterFiles` |
| AC-009 | done | Проверки 1–3, 6–10; миграций по-прежнему 12; frontend, зависимости, storage/FileService/API/модели/config не изменены; diff только allowlist |
| AC-010 | done | ADR-009 (статус, ограничение, открытый вопрос), ADR README (статусные строки, устаревшая запись о журнале удалена), PROJECT_STATUS (статус, ограничения 27/28, следующий этап); удаление и расписание нигде не заявлены |

## Ограничения и открытые риски

- Реализация строго **report-only**: кандидаты не удаляются, автоматического
  расписания и экспорта нет; разбор отчёта остаётся ручным.
- `scanned_blobs` считает только канонические ключи; посторонние обычные файлы
  учитываются отдельно в `ignored_regular_files`.
- `LOG_FILE` исключается по точному resolved-пути; файлы журнала вне
  `documents/` в область сканирования не входят.
- При гонке с `attach`/`detach` или изменении дерева во время обхода
  инвентарь может завершиться безопасной ошибкой; частичный список кандидатов
  не возвращается.
- Отчёт при сбое содержит только фиксированные `code`, `stage` и имя типа
  исключения; DSN, абсолютные пути, SQL и `str(error)` не выводятся.
- Повторный запуск стабилен на неизменном storage; снимок БД читается после
  файлового инвентаря, поэтому отражает состояние на момент SELECT.
- Push, merge, deploy и изменение blob не выполнялись.
