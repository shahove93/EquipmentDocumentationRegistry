# TASK-MVP-02 — независимое R2-ревью A1/C2

**Вердикт ревью: PASS.** Все AC-001…AC-010 выполнены; шесть findings
`MVP02-R2-001…006` закрыты. Новых findings: **0** (BLOCKER/MAJOR/MINOR/NIT — 0).
Это результат повторного полного ревью TASK, а не проектный PASS или итоговая
приёмка этапа. Следующий TASK ревьюер не запускает.

## Идентификация и проверенная ревизия

- Автор / роль: Codex, независимый ревьюер R2; дата 2026-10-23, Europe/Moscow.
- TASK: `docs/tasks/TASK-MVP-02.md`; замороженный checklist AC-001…AC-010.
- Подход / цикл: A1 / C2; полное ревью **2 / 2**, вызов Codex **3 / 4**
  согласно действующему dispatch. Третье полное ревью в A1 не открывается.
- Orca Run: `run_68046cea3eb4`.
- Review Task / Dispatch: `task_f5a7cda011c4` / `ctx_f8b4e389182a`.
- Терминал ревьюера: `term_27b46876-e608-426e-bd29-128220d4981e`;
  координатор: `term_e14657e9-784c-41ae-823c-412f8dc3f6f9`.
- Implementation Task / Dispatch: `task_b456188d963d` / `ctx_43c38bcb89c3`.
- Workspace: `D:\Antigravity\EquipmentDocumentationRegistry`, ветка `main`.
- Baseline: `7b84f2aa760c3ad5ec6257cb89c59d33f8993cb8` (`7b84f2a`).
- C2 commit: `fde540677fa1dc5ecc3ff359bc1c989af6f4b26c` (`fde5406`).
- Проверенный продуктовый C2 diff:
  `8894279c1098ccc63b28866ee1689776ffa02991..fde540677fa1dc5ecc3ff359bc1c989af6f4b26c`.
  `8894279` — фактический родитель C2; диапазон `7b84f2a..8894279`
  содержит только workflow-изменения координатора в STATE/HISTORY.
- HEAD при осмотре: `d6501941746dee59661c4d87562ba320b917f79a`.
  Отличия `fde5406..HEAD` — только TASK/STATE/HISTORY; текущее содержимое
  `app`, `tests`, ADR и PROJECT_STATUS совпадает с проверенной реализацией.
- Основания: [TASK](../../tasks/TASK-MVP-02.md),
  [C1 review](TASK-MVP-02.md), [C2 evidence](../evidence/TASK-MVP-02-C2.md),
  фактический diff и текущие тела тестов/реализации.

Шесть прежних инфраструктурных dispatch-попыток `agent_readiness` с HTTP 502
не являются полными ревью или FAIL-находками и не включены в их счётчики.
Действующие ограничения routing-and-budget/review-policy сохранены; новые
агенты, циклы, исправления и расширения checklist не запускались.

## Полная таблица AC

Номера строк ниже относятся к продуктовому состоянию `fde5406`, совпадающему
с workspace. Пути приведены от корня репозитория. Результаты исполнения
переиспользованы из C2 evidence; собственные запуски тестов не заявляются.

| ID | Вердикт | Независимо проверенное основание |
| --- | --- | --- |
| AC-001 | PASS | `app/reconcile_storage.py:60` разбирает argparse до Settings/engine; CLI использует существующие DATABASE_URL/STORAGE_ROOT/LOG_FILE, не инициализирует журнал и не делает mkdir. `tests/test_reconcile_storage_cli.py:96` запускает реальный модуль из tmp CWD без DATABASE_URL/.env и проверяет отсутствие root/log; `:129` проверяет настоящий успешный subprocess. Evidence №1–4 подтверждает исполнение. |
| AC-002 | PASS | `app/services/storage_reconciliation.py:29` использует fullmatch полного канонического ключа: десятичный id, lowercase UUID, pdf/jpg/png; `:166` сравнивает полный storage_key. `tests/test_storage_reconciliation.py:74`, `:158`, `:191`, `:207` покрывают форму, одинаковый basename в разных документах и нулевой blob; `tests/test_storage.py:292` — рекурсивный обход. |
| AC-003 | PASS | Scanner выдаёт только обычные файлы внутри documents; классификатор исключает неверные имена/глубину/расширения. `storage_reconciliation.py:131` отдельно считает точный resolved LOG_FILE один раз, до классификации остальных файлов. Тесты reconciliation `:227`, `:244`, `:264`, `:277` проверяют канонический/неканонический журнал, symlink/каталог и внешний журнал, summary; scanner-тест `test_special_files_are_not_yielded` исключает FIFO. LOG_FILE не входит в scanned. |
| AC-004 | PASS | `app/services/local_storage.py:135`, `:179`, `:216`, `:257`, `:315`: проверка prefix, dir_fd, O_DIRECTORY/O_NOFOLLOW, stat без разыменования symlink. Статические ссылки наружу/внутрь, namespace-symlink и неверный prefix покрыты сохранёнными тестами. Новый `tests/test_storage.py:476` подменяет проверенный documents на внешний symlink перед реальным os.open; инструменты open/stat/listdir/read не фиксируют внешнего доступа. Reconciliation-тест `:617` проверяет тот же фактический scanner, safe failure без partial report и SQL. |
| AC-005 | PASS | `storage_reconciliation.py:103` полностью завершает инвентарь до `:147` — отдельного engine.connect и единственного SELECT File.storage_key. Новый `tests/test_storage_reconciliation.py:364` использует настоящую PostgreSQL, writer-thread, два Event и отдельные соединения; writer commit предшествует завершению gated iterator, SELECT видит ключ (matched=1). Fixture `tests/conftest.py:43` использует NullPool, поэтому подключения физически отдельные. Проверены 2 checkout, один reconciliation SELECT и единственный commit writer; прежние тесты `:322`, `:464` проверяют порядок и пустой инвентарь. DML/явных locks/commit/flush в reconciliation нет. |
| AC-006 | PASS | Новый путь делает только metadata FS и SELECT; вызовов blob-open/read/save/delete, ORM-записи и logging нет. `tests/test_storage_reconciliation.py:724` сравнивает строки files, статусы документов, число событий, байты/mtime blob и журнал до/после двух запусков; summary/orphans стабильны. `:777` и CLI-тесты проверяют отсутствие созданного root/log. Тестовое создание данных не относится к действиям reconciliation. |
| AC-007 | PASS | `_success_report` (`storage_reconciliation.py:151`) возвращает status=complete, complete=true, schema_version=1, report_only/documents, сортированные orphans и согласованный summary. UTC timestamps идут из UTC datetime; failure shape остаётся failed/false/null/null. CLI `_emit`/main обеспечивают один JSON stdout, короткий безопасный stderr и exit 0/1/2. Проверены реальные subprocess-тесты успеха, кандидатов, аргументов, config/DB/missing-root failure и отсутствие DSN/путей; C2 evidence №3 фиксирует успешный CLI status=complete. |
| AC-008 | PASS | Missing root преобразуется во внешний root_missing/inventory без mkdir. Пустой root/отсутствующий documents требуют SELECT. Сохранены проверки root/namespace-file, unreadable subdirectory, vanished entry, DB/config и partial inventory. Новые fault-тесты reconciliation `:544`, `:578` и CLI `:328`, `:370` проходят фактический scanner и проверяют unreadable root/stat OSError, failed/false/null/null, точный code/stage/type, отсутствие SQL и CLI exit 1. В stat-сценарии подтверждён уже выданный элемент инвентаря. |
| AC-009 | PASS | C2 evidence №1: focused storage/reconciliation/CLI/FileService/concurrency — 386 passed, exit 0; №2: полный backend — 3483 passed, 1 warning, 0 failed, exit 0; №5: 12 миграций. Реальные имена файлов C2 diff совпадают с allowlist; дерево Git независимо содержит 12 миграций. Запрещённые пути, frontend и зависимости не изменены. C2 evidence untracked, в коммите отсутствует. |
| AC-010 | PASS | Просмотрены сохранённые изменения C1 и текущее состояние ADR-009 (`:17`, `:37`, `:580`, `:687`), ADR README (`:28`, `:66`, `:86`), PROJECT_STATUS (`:189`, `:276`, `:297`, `:306`). Они отражают report-only CLI, отсутствие удаления/DML/расписания, выполненную сверку и исправленный статус постоянного журнала. Эти документы, CLI и scanner в C2 не менялись; содержательного изменения архитектуры нет. |

## Закрытие C1 findings

| ID / AC / прежняя severity | Статус | Место, фактическая проверка и условие закрытия |
| --- | --- | --- |
| MVP02-R2-001 / AC-007 / MAJOR | CLOSED | `storage_reconciliation.py:184`: status="complete", complete=true. Callable-тесты и реальный CLI (`tests/test_reconcile_storage_cli.py:161`, `:193`) проверяют точные значения и exit 0 при кандидатах; evidence №3 соответствует исправленной ревизии. Failure report не менялся. |
| MVP02-R2-002 / AC-003,007 / MAJOR | CLOSED | `_collect_inventory` (`storage_reconciliation.py:131`) возвращает список и отдельный ignored_log_files; LOG_FILE исключается один раз, а summary начинает ignored с этого счётчика. Тест `:227` теперь ожидает ignored=1; `:244` проверяет неканоническое имя вместе с symlink и каталогом, `:264` — журнал вне documents. Scanner не выдаёт symlink/каталоги/FIFO, следовательно они не увеличивают этот счётчик. |
| MVP02-R2-003 / AC-007,008 / MAJOR | CLOSED | `storage_reconciliation.py:42`, `:113` преобразуют только storage_root_missing → root_missing; stage inventory и прочие безопасные коды сохранены. Callable `tests/test_storage_reconciliation.py:777` и subprocess CLI `tests/test_reconcile_storage_cli.py:199` проверяют код, failure shape, отсутствие root/log/секретных путей и exit 1. |
| MVP02-R2-004 / AC-004 / MAJOR | CLOSED | Новые scanner/reconciliation-тесты (`tests/test_storage.py:476`, `tests/test_storage_reconciliation.py:617`) реально выполняют rename documents и os.symlink(outside, documents) непосредственно перед реальным open после проверки каталога. O_NOFOLLOW/O_DIRECTORY приводят к storage_namespace_not_directory; нет успешного внешнего open, последующего внешнего stat/listdir/read, частичного отчёта и SQL. Тесты не заменяют scanner заранее подготовленным результатом. Они входят в успешно выполненные focused/full наборы C2. |
| MVP02-R2-005 / AC-005 / MAJOR | CLOSED | `tests/test_storage_reconciliation.py:364`: gated реальный iter_files → Event → INSERT/commit независимого PostgreSQL writer → Event → окончание инвентаря → SELECT reconciliation. NullPool исключает переиспользование физического соединения; SQLAlchemy Connection writer сохранён для отделения его SQL от SQL сверки. matched=1 доказывает видимость коммита; 1 reconciliation SELECT, 2 checkout, всего 1 commit (writer вызывает его явно). Дополнительно отсутствие commit/flush/DML/locks проверено по коду, а не только количеству событий. |
| MVP02-R2-006 / AC-008 / MAJOR | CLOSED | Добавлены PermissionError на stat(root, follow_symlinks=False) и OSError(EIO) на stat элемента при dir_fd. Реальный scanner обрабатывает исключения; callable/CLI проверяют безопасный полный failure shape и 0 SQL. Tracking wrapper в reconciliation доказывает, что a.pdf уже выдан до ошибки zzz.pdf; partial summary/orphans не публикуются. CLI main возвращает 1. Точные сценарии и коды приведены ниже; тесты выполнены в C2 focused/full. |

Изменения старых ожиданий проверены против design и реализации: `ok` →
`complete`, ignored=0 → 1 для обычного LOG_FILE, внешний missing-root code →
`root_missing`. Это исправление несовместимых ожиданий, а не сокрытие дефекта.
Новые тесты сохраняют фактические OS/scanner/reconciliation пути и проверяют
результаты, SQL и побочные эффекты, соответствующие заявленным сценариям.

## Fault matrix и ограничения доказательства

| Сценарий / проверка | error.code / stage | Проверенный результат |
| --- | --- | --- |
| Missing root; callable + CLI subprocess | root_missing / inventory | failed, complete=false, summary=null, orphans=null; exit 1; root/log не созданы, путь не раскрыт. |
| Unreadable root; реальные scanner/reconciliation + CLI main с OS-инъекцией | storage_unreadable / inventory | Точный failure shape и StorageInventoryError; 0 SQL, CLI exit 1, безопасный stderr. |
| Stat OSError после первого элемента; scanner/reconciliation + CLI main | storage_stat_failed / inventory | Точный failure shape; partial inventory не становится отчётом; 0 SQL, CLI exit 1. |
| Подмена проверенного documents на внешний symlink; scanner + reconciliation | storage_namespace_not_directory / inventory | Реальный open безопасно отказывает, внешних metadata/read нет, отчёт failed/false/null/null, 0 SQL. |
| Namespace-file; scanner + CLI subprocess | storage_namespace_not_directory / inventory | Безопасный failure, CLI exit 1, без пути в stdout/stderr и без log. |
| Root-file / vanished entry / unreadable subdirectory; сохранённые scanner-тесты | storage_root_not_directory / storage_entry_vanished / storage_unreadable | Соответствующий StorageInventoryError; общий обработчик reconciliation сохраняет безопасный failure shape. |
| Partial iterator; сохранённый reconciliation-тест | storage_walk_failed / inventory | summary/orphans=null, 0 SQL, текст исключения не раскрыт. |
| DB failure / config failure; callable и/или CLI | database_error / database; configuration_error / configuration | Безопасный failure, CLI exit 1, без DSN/SQL/путей и журнала. |

Внешний каталог в тесте подмены не открывается успешно: реальный open ссылки
с O_NOFOLLOW отказывает, после чего код не делает stat/listdir/read её цели.
В отличие от проверки только итогового списка, инструменты наблюдают эти
OS-точки. Это доказательство конкретного согласованного swap-сценария, а не
сертификат всех возможных rename/mount-гонок. Подмена namespace происходит до
выдачи элементов; отдельный stat/partial-тест доказывает отказ уже после
частичного инвентаря. Различие не скрыто названием no_partial_report.

## Evidence reuse и собственные команды ревьюера

Все обязательные исполняемые проверки ниже взяты из
`docs/workflow/evidence/TASK-MVP-02-C2.md` для `fde5406`. Внешний CWD —
`D:\Antigravity\EquipmentDocumentationRegistry`; внутренний CWD указан
командой. У evidence есть точные команды, ревизия, exit и достаточные inline
результаты; соответствующие тела тестов просмотрены. Утверждение исполнителя
«done» само по себе основанием PASS не служило.

| Evidence | Команда / фактический результат | Решение ревьюера |
| --- | --- | --- |
| №1, focused | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_storage.py tests/test_storage_reconciliation.py tests/test_reconcile_storage_cli.py tests/test_file_service.py tests/test_file_service_concurrency.py'` — exit 0, `386 passed in 65.24s`; указан финальный повтор после коммита. | Переиспользовано без rerun; содержит все новые тесты C2 и согласованные регрессии. |
| №2, полный backend | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` — exit 0, `3483 passed, 1 warning in 429.84s (0:07:09)`, 0 failed. | Переиспользовано без rerun; warning — прежний StarletteDeprecationWarning. 9 новых тестов соответствуют приросту 3474 → 3483. |
| №3, CLI | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage; echo EXIT:$?'` — внешний exit 0, внутренний EXIT:0; status=complete, complete=true, scanned=3, matched=3, orphan_count=0, orphan_bytes=0, orphans=[]. | Переиспользовано вместе с JSON subprocess-тестами; реальный storage ревьюер не сканировал. |
| №4, help без .env | `wsl.exe -d Ubuntu -- bash -lc 'cd /tmp && env -u DATABASE_URL -u STORAGE_ROOT -u LOG_FILE PYTHONPATH=/mnt/d/Antigravity/EquipmentDocumentationRegistry /mnt/d/Antigravity/EquipmentDocumentationRegistry/.venv/bin/python -m app.reconcile_storage --help >/dev/null; echo HELP_EXIT:$?'` — внешний exit 0, HELP_EXIT:0; /tmp/storage и /tmp/logs не созданы. | Переиспользовано вместе с test_help_works_without_database_or_env_file. |
| №5, миграции | Подсчёт `ls alembic/versions/*.py` через `wc -l` в указанном WSL CWD — exit 0, `12`. | Переиспользовано; `git ls-tree -r --name-only fde5406 alembic/versions` независимо показывает 12 файлов. Миграции не менялись, Alembic current повторно не требовался. |
| №6–9, Git | Commit/stat/name-only, diff --check, статус untracked evidence. | Сверено с реальными Git-объектами и workspace, а не только списком исполнителя. |

Сокращённое описание дополнительного повтора №10 (`7 passed`) не используется
как самостоятельное обязательное доказательство: нужные тесты уже входят в
точно указанные успешные команды №1/2.

**Reviewer reruns: 0.** Пробела, требующего единственного разрешённого rerun,
не обнаружено. Полный backend, focused, CLI и help заново не запускались;
frontend не менялся, его сборка в checklist TASK не требуется.

Собственные действия ревьюера: чтение ограниченных инструкций/TASK/review/evidence,
исходников и тестов; `git branch --show-current`, `git rev-parse`,
`git show --format=fuller --stat fde5406`, `git show --format= --name-only fde5406`,
`git diff --name-status/--stat` указанных диапазонов, просмотр фактических diff,
`git diff --check 8894279 fde5406`, `git ls-tree` и read-only проверки совпадения.
Все эти Git-проверки завершились exit 0; в частности:

- `git diff --quiet fde5406 -- app tests docs/adr docs/PROJECT_STATUS.md` — 0.
- `git diff --quiet 7b84f2a fde5406 --` запрещённые C2-пути — 0.
- `git diff --quiet a2b52a8 fde5406 --` scanner/CLI и три статусных документа — 0.
- `git diff --quiet fde5406 HEAD --` C1 evidence/review — 0.
- `git diff --quiet` и `git diff --cached --quiet` до создания отчёта — 0.

Windows `rg` отсутствует (CommandNotFoundException); чтение файлов и поиск
сигнатур выполнены доступными PowerShell средствами. Это не тестовый rerun
или скрытая успешная проверка отсутствующим инструментом.
Orca check на естественных checkpoints возвращал пустой inbox активного
dispatch; heartbeat отправлен с обоими lifecycle IDs. Ожидание работников
и координация очереди не выполнялись.

## Границы diff и состояние workspace

`git show --name-only` и `git diff --name-status 8894279 fde5406`
подтверждают ровно четыре файла, `553 insertions(+), 19 deletions(-)`:

```text
M app/services/storage_reconciliation.py
M tests/test_storage.py
M tests/test_storage_reconciliation.py
M tests/test_reconcile_storage_cli.py
```

`local_storage.py`, `storage.py`, `file_service.py`, модели/config/API,
logging/dependencies/main, миграции, frontend, зависимости, .gitignore и
tracked storage в C2 не менялись. Диапазон `7b84f2a..fde5406` дополнительно
содержит только coordinator workflow-коммит `8894279` в STATE/HISTORY.
Исторические C1 evidence/review сохранены; C2 evidence не входит в C2 commit.
Сохранённые продуктовые/документационные изменения C1 просмотрены для всех AC.

Содержимое C2 diff просмотрено; реальных секретов не обнаружено. Поиск
private-key/API-token сигнатур через Select-String не дал совпадений;
secret/DSN в просмотренных тестах — синтетические данные и redaction fixtures.
Содержимое .env, реального storage и журналов ревьюер не читал и не изменял.
Git не доказывает состояние ignored storage; отсутствие побочных эффектов
подтверждается read-only тестами и просмотром пути reconciliation.

До создания отчёта единственное untracked-изменение:
`docs/workflow/evidence/TASK-MVP-02-C2.md`. Собственный разрешённый результат
ревьюера — только новый untracked `docs/workflow/reviews/TASK-MVP-02-C2.md`.
Продуктовый код, тесты, C1 review/evidence, другие workflow-файлы, индекс и
HEAD ревьюер не менял; commit/push/merge/deploy не выполнялись.

Завершающая проверка после создания отчёта: tracked diff, index diff и
product diff к `fde5406` — exit 0; HEAD остался `d650194`. В status ровно
два untracked-файла: исходный C2 evidence и этот новый отчёт. Проверка
`git ls-files --error-unmatch` для отчёта вернула 1: файл не отслеживается.

## Новые findings и остаточные риски

Новых findings нет; таблица ID/AC/severity/location/repro/expectation/closure
для новых нарушений пуста. Открытых BLOCKER/MAJOR и обязательных условий
закрытия не осталось; backlog за рамками замороженного checklist не расширен.

- Report-only выдаёт кандидатов для ручного разбора и не разрешает удаление.
  Файловый инвентарь и SELECT не являются единой атомарной транзакцией;
  изменения после снимков отражаются последующим запуском.
- Event/barrier подтверждает writer commit до SELECT; writer соединение
  закрывается до выдачи сигнала, а reconciliation открывает своё после
  инвентаря. NullPool обеспечивает физическое разделение. Тест не моделирует
  все возможные уровни изоляции или изменения после SELECT.
- OS fault injection детерминированно покрывает root/stat и не зависит от
  эффективных permission-битов; дополнительные гонки вне проверенной точки
  подмены не заявляются доказанными. Рабочая среда — согласованная WSL Ubuntu.
- Итоговая приёмка этапа и проектный PASS остаются отдельными решениями.
  Координатор получает этот bounded PASS по TASK и ведёт workflow/счётчики;
  ревьюер не запускает successor и не делает дополнительных исправлений.
