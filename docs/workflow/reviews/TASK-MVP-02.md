# TASK-MVP-02 — независимое R2-ревью A1/C1

**Вердикт ревью: FAIL.** Найдено 6 MAJOR; BLOCKER, MINOR и NIT не назначены.
Это решение по текущему TASK, а не проектный PASS или итоговая приёмка этапа.

- Автор: Codex, отдельный ревьюер, терминал `term_8f9e8c88-6cd8-4069-a250-74851ce605c0`.
- Дата: 2026-10-22, Europe/Moscow.
- Review Task / Dispatch: `task_4ac8b4f9eb5e` / `ctx_51b60231d76c`.
- Реализация: `a2b52a8e27b77e25dd0165cee9864ccf57689aed`.
- Основной проверенный diff: `e3e6f8130e223eb7871a79094769cc4dbcec400f..a2b52a8e27b77e25dd0165cee9864ccf57689aed`.
- Dispatch baseline: `040018b`; диапазон `040018b..a2b52a8` дополнительно содержит документы координатора.
- HEAD при ревью: `637473b14685f161c2f2e2431c7bae353b1b7b05`, ветка `main`, текущий workspace `D:\Antigravity\EquipmentDocumentationRegistry`.
  После реализации изменены только `docs/workflow/STATE.md` и `HISTORY.md`.
  `git diff --quiet a2b52a8 -- app tests docs/adr docs/PROJECT_STATUS.md` вернул 0:
  проверяемый продуктовый код, тесты и продуктовая документация совпадают с реализацией.
- Источники: `AGENTS.md`, замороженный `docs/tasks/TASK-MVP-02.md`, фактический diff,
  `docs/workflow/evidence/TASK-MVP-02-C1.md`, review-policy и routing-and-budget skill autonomous-development.
  Точные решения design memo `msg_2a59e2195e94` взяты из задания ревьюера:
  `status=complete`, `root_missing`, включение исключённого `LOG_FILE` в `ignored_regular_files`.

## AC → результат

| AC | Результат | Независимая оценка кода/артефактов и переиспользованные доказательства |
| --- | --- | --- |
| AC-001 | PASS | `app/reconcile_storage.py:58` разбирает аргументы до `Settings()`/создания engine; `--help` не подключается к БД. Импорты не запускают lifespan/logging. Конструктор storage не создаёт root, CLI не настраивает журнал. `tests/test_reconcile_storage_cli.py:92` запускает модуль из tmp CWD без DATABASE_URL/.env и проверяет отсутствие root/log; тесты `:125`, `:192`, `:222` проверяют реальный subprocess и настройки. Evidence №1–5 подтверждает запуск этих тестов и CLI. Ошибки полей отчёта учтены в AC-007/008. |
| AC-002 | PASS | `storage_reconciliation.py:29` использует fullmatch полного ключа, канонический десятичный id, lowercase UUID и pdf/jpg/png. `:157` сравнивает полный storage_key с множеством БД. Тесты `test_storage_reconciliation.py:65`, `:154`, `:187`, `:203` покрывают форму, разные документы/одинаковый basename и нулевой blob; `test_storage.py:291` — рекурсию. Evidence №1–3. |
| AC-003 | FAIL | Namespace, форма ключа, symlink, FIFO и каталоги исключаются в коде; соответствующие тесты присутствуют. Но точный LOG_FILE отбрасывается до подсчёта ignored, поэтому summary не соответствует design — MVP02-R2-002. Тест `test_storage_reconciliation.py:223` закрепляет неверное значение 0. |
| AC-004 | FAIL | Для открываемых дочерних каталогов используются dir_fd, O_DIRECTORY и O_NOFOLLOW; неверный prefix, статические symlink внутрь/наружу и namespace-symlink покрыты. Однако обязательного сценария подмены каталога между проверкой и открытием/обходом нет — MVP02-R2-004. Evidence утверждает наличие «подмены», но в фактических тестах есть только vanished-entry injection. |
| AC-005 | FAIL | `storage_reconciliation.py:98` сначала завершает `_collect_inventory`, затем `:138` открывает отдельное соединение и делает один `select(File.storage_key)`, включая пустой инвентарь. DML, commit/flush и блокировок в пути нет. Тест `test_storage_reconciliation.py:285` использует реальную PostgreSQL и SQLAlchemy callbacks, проверяет один checkout/SELECT и локальный флаг. Но требуемого сценария с отдельными одновременно управляемыми соединениями и Event/barrier нет — MVP02-R2-005. |
| AC-006 | PASS | В новом пути только metadata FS и SELECT; отсутствуют чтение blob-содержимого, запись/удаление blob, изменение ORM-состояния и logging. `test_storage_reconciliation.py:407` сравнивает строки files, статусы документов, число событий, байты/mtime blob и журнал, повторяет запуск; `:460` проверяет отсутствие mkdir/log. Evidence №1–3. |
| AC-007 | FAIL | JSON stdout, безопасный stderr, exit 0/1/2, сортировка и равенство scanned=matched+orphans реализованы; failure shape — failed/false/null/null. Но успех выдаёт `status=ok`, а missing root — `storage_root_missing`; ignored не учитывает LOG_FILE. MVP02-R2-001/002/003. Успешные тесты и evidence подтверждают именно текущий, несовместимый с design контракт. |
| AC-008 | FAIL | Missing root не создаётся; пустой root/namespace требует SELECT; config/DB/namespace-file и частичный инвентарь имеют безопасный failure shape. Но missing-root code расходится с design (MVP02-R2-003), а обязательная матрица fault injection не покрывает нечитаемый root и ошибку stat (MVP02-R2-006). Не подтверждаю эти сценарии одним утверждением исполнителя. |
| AC-009 | PASS | Evidence №1: 124 passed; №2: 377 passed; №3: 3474 passed, 1 warning, 0 failed; №6: 12 миграций. Полный pytest переиспользован без повторного запуска. Фактический diff содержит ровно 9 разрешённых файлов. storage.py, file_service.py, модели, config/dependencies/main/logging_config/API, миграции, frontend, зависимости и .gitignore не изменены. Evidence не входит в коммит. Зеленые тесты не устраняют ошибки ожиданий и пробелы AC-003/004/005/007/008. |
| AC-010 | PASS | Изменённые ADR-009 (`:17`, `:38`, `:580`, `:687`), ADR README (`:28`, `:67`, `:86`) и PROJECT_STATUS (`:189`, `:276`, `:297`) отражают report-only CLI и отсутствие удаления/DML/расписания. Устаревшая запись о нереализованном постоянном журнале в README устранена. Содержательных изменений жизненного цикла/архитектуры вложений нет. |

Все пути без префикса в таблице относятся к `app/services/` либо явно указанному `tests/`.
Номера строк — для проверенной реализации, совпадающей с текущим workspace.

## Findings

### MVP02-R2-001 — неверный status успешного отчёта

- **AC:** AC-007. **Severity:** MAJOR — несовпадение JSON-контракта.
- **Место:** `app/services/storage_reconciliation.py:175`; `tests/test_reconcile_storage_cli.py:157`, `tests/test_storage_reconciliation.py:121`.
- **Наблюдение:** `_success_report()` всегда возвращает `status="ok"`; тесты ожидают `ok`, а design явно требует `complete`.
  Evidence №5 также содержит `status=ok`, поэтому это подтверждённое расхождение, а не предположение о выполнении.
- **Воспроизведение:** успешный `python -m app.reconcile_storage` при доступной БД и существующем root, включая пустой root; JSON содержит `"status": "ok"` при exit 0.
- **Ожидание:** `status="complete"`, `complete=true`, exit 0 при любом числе кандидатов.
- **Закрытие:** успешный CLI и callable соответствуют design; тесты проверяют точное `complete`; приложено актуальное evidence для исправленной ревизии.

### MVP02-R2-002 — исключённый LOG_FILE теряется из ignored_regular_files

- **AC:** AC-003, AC-007. **Severity:** MAJOR — неверный summary.
- **Место:** `app/services/storage_reconciliation.py:130`; `tests/test_storage_reconciliation.py:234`.
- **Наблюдение:** `_collect_inventory()` делает `continue` для точного log_path, прежде чем `_success_report()` начинает считать ignored.
  Тест с журналом, похожим на канонический blob, явно ожидает 0; design требует учитывать обычные файлы, исключённые по форме ключа **или LOG_FILE**.
- **Воспроизведение:** существующий `documents/1/<uuid>.pdf` назначить LOG_FILE и рядом оставить один настоящий канонический blob; текущая проверка `test_log_file_is_excluded_even_when_it_looks_canonical` получает scanned=1, ignored=0.
  То же выпадение происходит для обычного неканонического LOG_FILE внутри documents.
- **Ожидание:** журнал не кандидат и не scanned; ignored=1 в этом сценарии. Счётчик не должен включать каталоги, symlink или файлы вне documents.
- **Закрытие:** сохранить учёт исключённых обычных LOG_FILE и проверить каноническое/неканоническое имя; обновить неверное ожидание теста и evidence.

### MVP02-R2-003 — missing-root code не соответствует фиксированному design

- **AC:** AC-007, AC-008. **Severity:** MAJOR — несовпадение машинного кода ошибки.
- **Место:** `app/services/local_storage.py:184`, `:205`; передача наружу в `app/services/storage_reconciliation.py:108`; `tests/test_reconcile_storage_cli.py:213`.
- **Наблюдение:** оба FileNotFoundError в `_open_root()` дают `storage_root_missing`, который без преобразования попадает в JSON/stderr; design фиксирует `root_missing`.
- **Воспроизведение:** запуск CLI с отсутствующим STORAGE_ROOT; существующий subprocess-тест `test_missing_storage_root_fails_without_creating_it` закрепляет `error.code=storage_root_missing`.
- **Ожидание:** exit 1, status=failed, complete=false, summary/orphans=null, code=`root_missing`; никаких mkdir/секретных путей.
- **Закрытие:** внешний код ошибки точно `root_missing` для отсутствующего root; согласованные тесты callable/CLI и новое evidence.

### MVP02-R2-004 — нет обязательного доказательства безопасности при подмене каталога

- **AC:** AC-004. **Severity:** MAJOR — обязательное поведение не имеет своего теста.
- **Место:** `tests/test_storage.py:384`, `:423`, `:461`; проверяемые ветви `app/services/local_storage.py:179`, `:216`, `:315`.
- **Наблюдение:** тесты создают статические symlink либо добавляют `ghost.pdf` в listdir. Ни один не подменяет каталог между stat/open/listdir.
  Упоминание «подмены» в evidence не подкреплено тестом в фактическом diff.
  Из наличия O_NOFOLLOW на последнем компоненте нельзя автоматически вывести результат всех подмен пути до открытия root.
- **Воспроизведение пробела:** чтение всего `TestIterFiles` и поиск rename/replace/swap/барьеров показывают отсутствие сценария.
  Требуемый проверочный сценарий: после проверки настоящего каталога подменить его symlink на внешний каталог перед открытием и проконтролировать отсутствие внешнего stat/listdir/метаданных в результате.
- **Ожидание:** детерминированный тест подмены подтверждает отсутствие доступа за root; невозможность безопасно продолжить даёт failure без частичного отчёта.
- **Закрытие:** добавить и выполнить такой тест для реально используемого scanner, предоставить результат на исправленной ревизии; выявленные им дефекты закрыть в пределах AC.
  В этом ревью выход за root динамически не воспроизводился и как установленный факт не заявляется.

### MVP02-R2-005 — нет согласованного межсоединительного сценария Event/barrier

- **AC:** AC-005. **Severity:** MAJOR — неполное обязательное доказательство порядка снимков.
- **Место:** `tests/test_storage_reconciliation.py:285`.
- **Наблюдение:** тест оборачивает iterator локальным boolean и слушает SQLAlchemy events; это проверяет последовательность вызовов и число checkout.
  Другого управляемого соединения, изменения/commit ключа во время инвентаря и Event/barrier в тесте нет.
  SQLAlchemy callback не является барьером между независимыми участниками; fixture использует реальную PostgreSQL, но это не восполняет отсутствующий сценарий.
- **Воспроизведение пробела:** прочитать `TestDatabaseInteraction`; ни один тест не удерживает инвентарь и не синхронизирует commit другого соединения до SELECT.
- **Ожидание:** предусмотренная AC-005 интеграционная проверка с реальной PostgreSQL, отдельными соединениями и Event/barrier доказывает, что SELECT видит подтверждённый ключ после завершения инвентаря; один SELECT, без DML/блокировок/commit со стороны сверки.
- **Закрытие:** выполненный детерминированный межсоединительный тест с фактическим SQL/результатом и новым evidence; существующие проверки пустого инвентаря и одного SELECT сохранены.

### MVP02-R2-006 — неполная обязательная матрица ошибок инвентаря

- **AC:** AC-008. **Severity:** MAJOR — обязательные fault-сценарии не имеют тестов.
- **Место:** `tests/test_storage.py:444`, `:461`; `tests/test_storage_reconciliation.py:372`; `tests/test_reconcile_storage_cli.py:191`.
- **Наблюдение:** unreadable проверен только для вложенного каталога через chmod; vanished — через ghost listdir; partial — через iterator, вручную бросающий StorageInventoryError.
  Нет детерминированной проверки нечитаемого **root** и ошибки **stat** с прохождением до failure report. Обычный partial-тест не выполняет эти ветви OS/scanner.
  Реализация содержит обработчики, но evidence не доказывает требуемую полную матрицу.
- **Воспроизведение пробела:** сопоставить TestIterFiles, TestDatabaseInteraction и TestFailureReports со списком ошибок AC-008; отсутствуют root PermissionError и stat OSError сценарии/ожидаемые коды.
- **Ожидание:** fault injection проверяет эти случаи через фактический scanner и reconciliation/CLI: failed, complete=false, summary/orphans=null, безопасный фиксированный код/этап, exit 1 для CLI; после частичного инвентаря БД не опрашивается.
- **Закрытие:** добавить и выполнить недостающие случаи, зафиксировать таблицу scenario → code/stage/result и evidence на исправленной ревизии. Это требование AC-008, а не расширение чек-листа.

## Проверенные границы diff

`git diff --name-status e3e6f81..a2b52a8` независимо подтверждает ровно 9 файлов:

```text
A app/reconcile_storage.py
M app/services/local_storage.py
A app/services/storage_reconciliation.py
M docs/PROJECT_STATUS.md
M docs/adr/ADR-009-document-attachments.md
M docs/adr/README.md
A tests/test_reconcile_storage_cli.py
M tests/test_storage.py
A tests/test_storage_reconciliation.py
```

Они совпадают с allowlist. Незаявленных продуктовых файлов, зависимостей или изменений
запрещённых tracked-путей в диапазоне нет. Содержимое diff просмотрено: реальных
секретов не обнаружено; `secret`/DSN тестов — синтетические данные redaction/fixtures.
Поиск сигнатур private keys/API tokens в изменённых Python-файлах не дал совпадений
(`rg` exit 1 означает отсутствие совпадений). `.env` и содержимое реального storage
не читались и не изменялись. Изменения ignored/untracked содержимого storage невозможно
доказать одним Git diff; для отсутствия побочных эффектов переиспользован read-only тест.

До создания отчёта `git status --short --untracked-files=all` показывал только
`?? docs/workflow/evidence/TASK-MVP-02-C1.md`. Отчёт создаётся без коммита;
продуктовый код, тесты, другие workflow-документы, индекс и HEAD ревьюер не меняет.
При завершающей проверке появились параллельные изменения координатора в
`docs/workflow/STATE.md` и `HISTORY.md`: они регистрируют именно активный review
dispatch и его бюджет. Эти изменения просмотрены и сохранены без правок;
`git diff --quiet` для всего workspace поэтому вернул 1. Повторная сверка
продуктовых путей с `a2b52a8` вернула 0, HEAD остался `637473b`.
Собственное изменение ревьюера — только новый untracked-файл этого отчёта.

## Evidence reuse и команды ревьюера

Все проверки ниже относятся к реализации `a2b52a8`; внешний CWD — корень
`D:\Antigravity\EquipmentDocumentationRegistry`, WSL CWD —
`/mnt/d/Antigravity/EquipmentDocumentationRegistry`.
Источник выполненных тестов — evidence исполнителя, а не собственный запуск ревьюера.
Его AC-таблица `done` сама по себе не использовалась как независимое доказательство:
проверены реальные тела тестов и реализация.

| Проверка из evidence | Команда / результат | Использование |
| --- | --- | --- |
| №1, новые/storage | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_storage.py tests/test_storage_reconciliation.py tests/test_reconcile_storage_cli.py'`; exit 0, `124 passed` | Переиспользовано; не перезапускалось. |
| №2, регрессии | Та же команда с `tests/test_file_service.py tests/test_file_service_concurrency.py`; exit 0, `377 passed in 65.47s`, evidence указывает финальный повтор после коммита | Переиспользовано; не перезапускалось. |
| №3, полный backend | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'`; exit 0, `3474 passed, 1 warning in 465.84s`, 0 failed | Переиспользовано; полный pytest повторно не запускался. |
| №4, help | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage --help >/dev/null; echo "HELP_EXIT:$?"'`; внешний exit 0, внутренний `HELP_EXIT:0` | Переиспользовано совместно с subprocess-тестом без .env/БД; сама команда из repo этого условия не доказывает. |
| №5, CLI | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage; echo "EXIT:$?"'`; внешний exit 0, внутренний `EXIT:0`; status=ok, scanned=3, matched=3, orphan_count=0, orphan_bytes=0 | Переиспользовано; подтверждает MVP02-R2-001. Реальный storage ревьюер не сканировал. |
| №6, миграции | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'`; exit 0, `12` | Переиспользовано; дерево Git также содержит 12 файлов миграций, миграционный diff отсутствует. |
| №7–11, Git | evidence фиксирует stat/name-only, diff --check exit 0 и статус до/после evidence | Сверено с реальным диапазоном и текущим состоянием, а не принято на веру по списку исполнителя. |

Ревьюер отдельно выполнил read-only осмотр `git log`, `git status`, `git rev-parse`,
`git branch --show-current`, `git diff --stat/--name-status/--quiet`, `git ls-tree`,
чтение исходников/тестов/изменённых документов и `rg`. Git-команды осмотра завершились
exit 0; `git diff --quiet a2b52a8 -- app tests docs/adr docs/PROJECT_STATUS.md` — 0.
Поиск отсутствующих тестовых сценариев подтверждён чтением всех трёх изменённых
тестовых файлов, а не только поиском названий.

**Перезапущенных исполняемых проверок нет.** Evidence зелёных команд содержит CWD,
ревизию и достаточные численные результаты. Повтор зелёного набора не добавил бы
отсутствующие тесты и не исправил бы ошибочные ожидания контрактов.
Воспроизведения findings выше — описание существующих тестов/путей кода либо
предписанного отсутствующего сценария; новые динамические эксперименты не заявляются.

## Остаточные риски и следующий владелец

- Даже после устранения findings report-only результат остаётся кандидатом для
  ручного разбора; FS-инвентарь и снимок БД не являются общей атомарной транзакцией.
  Это согласованное ограничение, а не новый AC.
- Замена каталогов и полная матрица ошибок не подтверждены существующим evidence;
  отсутствие выхода за root в условиях подмены не сертифицировано этим ревью.
- Полный suite зелёный, но часть новых тестов проверяет неверный контракт, а
  обязательные сценарии отсутствуют; число passed не отменяет FAIL.
- Исправления и актуализация evidence принадлежат отдельному OpenCode-исполнителю
  после решения координатора; координатор ведёт C2/счётчики и workflow-документы.
  Ревьюер не запускает следующий TASK, не делает commit/push/merge/deploy.

Отчёт завершает одно независимое полное ревью A1/C1; новая реализация в рамках этого
dispatch не принималась и дополнительные циклы не открывались.
