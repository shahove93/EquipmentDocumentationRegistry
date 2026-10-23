# TASK-MVP-02 / C2 — отчёт исполнителя

## Идентификация

- TASK: TASK-MVP-02 — report-only сверка осиротевших blob-файлов.
- Подход / цикл: A1 / C2 (ограниченная коррекция после C1 FAIL).
- Класс риска: R2.
- Baseline C2: `7b84f2a` (workflow-коммит после C1 FAIL); dispatch-коммит
  координатора `8894279`; проверенная ревьюером реализация C1 `a2b52a8`.
- Итоговый commit C2: `fde540677fa1dc5ecc3ff359bc1c989af6f4b26c` —
  `fix(storage): align reconciliation report with design`, 4 файла,
  `553 insertions(+), 19 deletions(-)`.
- Task / Dispatch Orca: `task_b456188d963d` / `ctx_43c38bcb89c3`.
- Исполнитель: отдельный OpenCode-исполнитель (Orca worker,
  `term_bd5a9824-04f7-4bf2-b933-63511ddb5cb6`).
- Среда: `D:\Antigravity\EquipmentDocumentationRegistry`
  (`/mnt/d/Antigravity/EquipmentDocumentationRegistry`), ветка `main`.
- Дата: 2026-10-23.

## Что сделано

Закрыты только findings `MVP02-R2-001…006`; архитектура, AC и failure shape
не менялись. `app/services/storage.py`, `app/services/file_service.py`, модели,
config/dependencies/main/logging_config/API, `alembic/**`, frontend, зависимости,
`.gitignore`, `.env`, `.venv`, `storage/` и workflow-документы не изменялись.
C1 evidence/review не перезаписывались.

| Файл | Изменение |
| --- | --- |
| `app/services/storage_reconciliation.py` | успешный `status="complete"`; исключённый `LOG_FILE` учитывается в `ignored_regular_files` ровно один раз; внешний код отсутствующего root — `root_missing`; прочие коды/stage сохранены |
| `tests/test_storage_reconciliation.py` | ожидания `complete`; тесты `LOG_FILE` (каноническое/неканоническое имя, вне `documents`, symlink/каталог не считаются); интеграционный Event/barrier-тест AC-005 с реальной PostgreSQL; fault matrix root/stat; детерминированная подмена каталога на symlink наружу в reconciliation |
| `tests/test_storage.py` | детерминированный тест подмены проверенного каталога `documents` на symlink во внешний каталог перед открытием/обходом для фактического `LocalStorageBackend.iter_files()` |
| `tests/test_reconcile_storage_cli.py` | ожидания `complete` и `root_missing`; CLI-тесты нечитаемого root и ошибки `stat` через фактический `main()` с проверкой отсутствия SELECT |

### Закрытие findings

- `MVP02-R2-001`: `_success_report()` возвращает точный `status="complete"` и
  `complete=true`; exit 0 не зависит от числа кандидатов. Ошибочные ожидания
  `ok` заменены в callable и CLI-тестах. Failure shape (`failed`, `complete=false`,
  `summary/orphans=null`) не изменён.
- `MVP02-R2-002`: обычный файл, являющийся точным resolved `LOG_FILE` внутри
  `documents`, не попадает в `scanned_blobs`, но один раз учитывается в
  `ignored_regular_files`; проверены каноническое и неканоническое имя.
  Каталоги, symlink, нерегулярные файлы и файлы вне `documents` не учитываются.
  Неверное ожидание `ignored=0` исправлено на `ignored=1`.
- `MVP02-R2-003`: `StorageInventoryError.code="storage_root_missing"` на внешней
  границе отчёта преобразуется ровно в `root_missing`; stage остаётся
  `inventory`, тип — `StorageInventoryError`. Остальные безопасные коды не
  переименованы. Callable и CLI-тесты согласованы.
- `MVP02-R2-004`: для фактического scanner добавлен детерминированный сценарий:
  после успешной проверки `documents` каталог подменяется symlink на внешний
  каталог непосредственно перед `open`; O_NOFOLLOW даёт безопасный отказ.
  Инструментированные `open`/`stat`/`listdir`/`read` подтверждают отсутствие
  внешнего доступа, частичного отчёта и SELECT. Реальный дефект не выявлен,
  `app/services/local_storage.py` не изменялся.
- `MVP02-R2-005`: добавлен интеграционный тест AC-005 на реальной PostgreSQL с
  двумя управляемыми соединениями и `threading.Event`-барьером. Инвентарь
  удерживается; writer-соединение вставляет и коммитит `files.storage_key`;
  SELECT сверки после завершения инвентаря видит подтверждённый ключ
  (`matched_blobs=1`). На соединении сверки ровно один SELECT, DML/
  `FOR UPDATE` отсутствуют; commit-событие только у writer. Существующие
  проверки пустого инвентаря и одного SELECT сохранены.
- `MVP02-R2-006`: добавлена детерминированная fault matrix для нечитаемого
  root и ошибки `stat` через фактический scanner/reconciliation и через CLI
  `main()`. Инъекция не зависит от прав процесса (надёжна и при запуске от
  root). После частичного инвентаря БД не опрашивается.

## Выполненные проверки

Все команды запускались из WSL Ubuntu; внешний CWD —
`D:\Antigravity\EquipmentDocumentationRegistry`, WSL CWD —
`/mnt/d/Antigravity/EquipmentDocumentationRegistry`.

| # | Команда | CWD | Exit | Фактический результат |
| --- | --- | --- | --- | --- |
| 1 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_storage.py tests/test_storage_reconciliation.py tests/test_reconcile_storage_cli.py tests/test_file_service.py tests/test_file_service_concurrency.py'` | корень | 0 | `386 passed in 65.24s` (финальный повтор после коммита) |
| 2 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | 0 | `3483 passed, 1 warning in 429.84s (0:07:09)`; 0 failed; 3483 = 3474 + 9 новых тестов; warning — прежний `StarletteDeprecationWarning` |
| 3 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage; echo EXIT:$?'` | корень | 0 | Валидный JSON: `status=complete`, `complete=true`, `scanned_blobs=3`, `matched_blobs=3`, `orphan_count=0`, `orphan_bytes=0`, `orphans=[]`; `EXIT:0` |
| 4 | `wsl.exe -d Ubuntu -- bash -lc 'cd /tmp && env -u DATABASE_URL -u STORAGE_ROOT -u LOG_FILE PYTHONPATH=/mnt/d/Antigravity/EquipmentDocumentationRegistry /mnt/d/Antigravity/EquipmentDocumentationRegistry/.venv/bin/python -m app.reconcile_storage --help >/dev/null; echo HELP_EXIT:$?'` | `/tmp` (без `.env`) | 0 | `HELP_EXIT:0`; `/tmp/storage` и `/tmp/logs` не созданы |
| 5 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | 0 | `12` |
| 6 | `git show --stat --oneline HEAD`; `git show --name-only --format= HEAD` | корень | 0 | `fde5406 ...`; ровно 4 разрешённых файла; evidence отсутствует |
| 7 | `git diff --name-only 8894279..HEAD` | корень | 0 | 4 файла: `app/services/storage_reconciliation.py`, `tests/test_storage.py`, `tests/test_storage_reconciliation.py`, `tests/test_reconcile_storage_cli.py` |
| 8 | `git diff --check` | корень | 0 | ошибок пробелов нет |
| 9 | `git status --porcelain=v1 --untracked-files=all` после создания evidence | корень | 0 | только `?? docs/workflow/evidence/TASK-MVP-02-C2.md`; evidence не закоммичен |
| 10 | точечный повтор Event/barrier ×3 + `TestFaultMatrix` + scanner-swap + CLI fault tests | корень | 0 | `7 passed in 2.48s` |

Диапазон `7b84f2a..HEAD` дополнительно содержит только workflow-коммит
координатора `8894279` (`docs/workflow/STATE.md`, `HISTORY.md`); он не входит
в коммит исполнителя и не изменялся.

## Fault matrix AC-008 / AC-004

| Сценарий | Инъекция | `error.code` / `stage` | Отчёт | БД | Тест |
| --- | --- | --- | --- | --- | --- |
| отсутствующий root | фактически отсутствующий каталог | `root_missing` / `inventory` | `failed`, `complete=false`, `summary=null`, `orphans=null`, exit 1, mkdir нет | SELECT не выполняется | callable + CLI subprocess |
| нечитаемый root | `PermissionError` на `stat(root, follow_symlinks=False)` | `storage_unreadable` / `inventory` | то же | 0 SQL-запросов | callable + CLI in-process |
| ошибка `stat` записи | `OSError(EIO)` на `stat` элемента после уже собранного `a.pdf` | `storage_stat_failed` / `inventory` | то же; частичный инвентарь не публикуется | 0 SQL-запросов, частичный список не отдан | callable + CLI in-process |
| подмена каталога `documents` | после проверки каталог заменён symlink на внешний каталог перед `open` | `storage_namespace_not_directory` / `inventory` | то же; внешний доступ (`stat`/`listdir`/`open`/`read`) отсутствует | SELECT не выполняется | фактический scanner + reconciliation |
| частичный обход | итератор бросает `StorageInventoryError` после одного элемента | `storage_walk_failed` / `inventory` | то же | SELECT не выполняется | существующий тест |
| namespace — файл | реальный файл `documents` | `storage_namespace_not_directory` / `inventory` | то же | SELECT не выполняется | существующий callable + CLI |
| сбой БД | engine.connect() бросает `OperationalError` | `database_error` / `database` | то же | безопасный отчёт без SQL/DSN | существующий callable + CLI |
| сбой конфигурации | отсутствует `DATABASE_URL` | `configuration_error` / `configuration` | то же | подключения нет | существующий CLI |

Пустой root и отсутствующий `documents` по-прежнему дают успешный пустой отчёт
только после одного SELECT; пустой инвентарь не является сбоем.

## Соответствие затронутым AC

Исполнитель не присваивает проектный PASS; таблица фиксирует доказательства
для ревьюера.

| ID | Статус | Доказательство |
| --- | --- | --- |
| AC-003 | done | `test_log_file_is_excluded_even_when_it_looks_canonical` (`ignored=1`), `test_non_canonical_log_file_is_counted_once_as_ignored`, `test_log_file_outside_documents_is_not_counted`; symlink/каталог не увеличивают счётчик; `test_classifies_ignored_regular_files` сохранён |
| AC-004 | done | `test_directory_swapped_for_outside_symlink_is_not_followed` (scanner) и `test_directory_swapped_for_outside_symlink_has_no_partial_report` (reconciliation); внешний доступ отсутствует, safe failure без частичного отчёта |
| AC-005 | done | `test_committed_key_from_another_connection_is_seen_after_inventory`: реальная PostgreSQL, отдельные соединения, Event/barrier, 1 SELECT, matched=1, commit/DML/`FOR UPDATE` со стороны сверки отсутствуют; `test_select_runs_even_with_empty_inventory` сохранён |
| AC-007 | done | `status=complete` в callable/CLI; CLI exit 0 при кандидатах; `root_missing`; failure shape не менялся |
| AC-008 | done | fault matrix выше; нечитаемый root и ошибка `stat` проверены через фактический scanner/reconciliation/CLI; после частичного инвентаря БД не опрашивается |
| AC-009 | done | проверки 1–2, 5–8: 386 passed, 3483 passed / 0 failed, 12 миграций, diff только allowlist, evidence не закоммичен |

AC-001, AC-002, AC-006 и AC-010 не затрагивались; их прежние тесты и
документация сохранены.

## Ограничения и остаточные риски

- Реализация строго **report-only**: кандидаты не удаляются, расписания и
  автоматической очистки нет; разбор отчёта остаётся ручным.
- Файловый инвентарь и снимок БД не являются общей атомарной транзакцией.
  Ключ, закоммиченный другим соединением во время инвентаря, виден SELECT после
  завершения инвентаря; это подтверждено тестом AC-005. Обратное окно
  (изменение БД после SELECT) по-прежнему относится к следующему запуску.
- Тест подмены каталога детерминированно моделирует гонку в точке `open` после
  проверки; он не является универсальным доказательством для любых
  rename/mount-сценариев, но подтверждает отсутствие выхода за root в
  требуемом AC-004 сценарии.
- Fault matrix использует контролируемую инъекцию OS-точек, а не реальные
  permission-биты, поэтому результат не зависит от запуска от root.
- Push, merge, deploy, удаление blob и фоновые процессы не выполнялись;
  проектный PASS не присвоен, следующий TASK не запускался.
