# TASK-MVP-02 — Сверка осиротевших файлов

Статус: PASS (2026-10-23). Требования: VISION.md, ARCHITECTURE.md, ROADMAP.md,
ADR-005…010. Этап ROADMAP: 3.
Предшественники с обязательным PASS: TASK-MVP-01 PASS.
Класс риска: R2 (обход хранилища, сверка с PostgreSQL и отчётность;
cross-module, возможны гонки с attach/detach).
Маршрут приёмки: Codex-ревьюер. Design: Codex, `task_2d70042ef4d9` /
`ctx_acbb6b3c25e6`; проектный PASS дизайном не присваивается.

## Цель и область

Реализовать безопасную **report-only** сверку: обойти blob-файлы в
`STORAGE_ROOT/documents`, сравнить их `storage_key` со строками `files` и выдать
JSON-отчёт о кандидатах, для которых строки нет. Ничего не удалять, не менять
БД/журнал и не запускать фоновый планировщик.

Запуск: `python -m app.reconcile_storage` из корня репозитория. CLI использует
существующие `Settings.DATABASE_URL`, `Settings.STORAGE_ROOT` и
`Settings.LOG_FILE`; `--help` не требует `.env`/БД. HTTP API, scheduler,
автоматическая очистка, миграции и новые зависимости не входят.

## Design-решения (приняты Codex)

- Модули: `app/services/storage_reconciliation.py` — тестируемый callable
  `reconcile_storage(engine, storage: LocalStorageBackend, *, log_file)` и
  `app/reconcile_storage.py` — CLI `main(argv=None) -> int`.
- `LocalStorageBackend.iter_files(prefix)` выдаёт `StoredFileInfo`
  (`storage_key`, `size_bytes`, UTC `modified_at`). `StorageBackend` не меняется.
- Обход — только namespace `documents/`, рекурсивно; symlink не разыменовывать,
  за пределы root не выходить, содержимое blob не читать и не изменять.
- Blob — обычный файл с точным ключом
  `documents/<канонический десятичный document_id>/<канонический lowercase UUID>.<pdf|jpg|png>`.
  Каталоги, symlink, FIFO/socket, временные/посторонние имена, неверная глубина и
  другие расширения исключаются. Нулевой канонический blob считается кандидатом.
  Настройка `LOG_FILE` исключается по точному resolved-пути, даже если попала в
  namespace; `storage/logs/app.log` исключён уже областью `documents/`.
- Сначала полностью собирается файловый инвентарь, затем в отдельном соединении
  выполняется один `SELECT files.storage_key`; результат — `F \ D`, отсортированный
  по ключу. SELECT выполняется и при пустом инвентаре. Никаких DML, блокировок,
  commit/flush и запросов на каждый файл.
- Отчёт: один JSON-объект UTF-8 в stdout: `schema_version=1`,
  `mode=report_only`, `scope=documents`, `status`, `started_at`/`finished_at`
  (UTC ISO 8601), `summary`, `orphans`. Элемент `orphans`: `storage_key`,
  `size_bytes`, `modified_at`. `summary`: `scanned_blobs`, `matched_blobs`,
  `orphan_count`, `orphan_bytes`, `ignored_regular_files`.
- Exit 0 — сверка завершена при любом числе кандидатов; 1 — операционный сбой;
  2 — неверные аргументы argparse. Сбой: `status=failed`, `complete=false`,
  `summary=null`, `orphans=null`, безопасный `error` с фиксированным кодом/этапом
  и типом; stderr — короткое безопасное пояснение.
- Ошибки: отсутствующий root — fail без mkdir; пустой root или отсутствующий
  `documents` — успешный пустой отчёт только после успешного SELECT; нечитаемый
  root/подкаталог, root/namespace вместо каталога, исчезнувшая запись, ошибка
  stat/БД/конфигурации, частичный обход — fail без частичного списка.
- Отчёт не содержит DSN, паролей, абсолютных путей, `original_filename`,
  содержимого файлов, SQL, параметров и произвольного `str(error)`.

## Разрешённые файлы

Изменить: `app/services/local_storage.py`, `tests/test_storage.py`,
`docs/adr/ADR-009-document-attachments.md` (только статус/открытый вопрос
сверки), `docs/adr/README.md` (только статусные строки, включая устранение
устаревшей записи о постоянном журнале), `docs/PROJECT_STATUS.md` (только статус
сверки/ограничения).
Создать: `app/services/storage_reconciliation.py`, `app/reconcile_storage.py`,
`tests/test_storage_reconciliation.py`, `tests/test_reconcile_storage_cli.py`,
`docs/workflow/evidence/TASK-MVP-02-C1.md` (не коммитить).
Не затрагивать: `app/services/storage.py`, `app/services/file_service.py`,
`app/models/**`, `app/config.py`, `app/dependencies.py`, `app/main.py`,
`app/logging_config.py`, `app/api/**`, `alembic/**`, `frontend/**`,
`requirements.txt`, `.gitignore`, `.env`, `.venv`, `storage/`, `node_modules/`,
`dist/`, workflow-документы (кроме evidence-файла).

## Критерии приёмки

Чек-лист заморожен координатором до диспатча. Ревьюер проверяет строго по нему.

| ID | Критерий | Способ независимой проверки | Severity |
| --- | --- | --- | --- |
| AC-001 | `python -m app.reconcile_storage` реально запускается; `--help` работает без `.env`/БД; CLI читает существующие настройки и не создаёт log/root. | CLI-тест с env без DATABASE_URL для `--help`; запуск на временном storage; проверка отсутствия `app.log` и новых каталогов | BLOCKER |
| AC-002 | Кандидат определяется по полному ключу: `documents/<id>/<lowercase UUID>.<pdf\|jpg\|png>`; вложенные каталоги и нулевой blob покрыты; одинаковый basename в другом документе не даёт matched. | Unit/интеграционные тесты с несколькими документами и ключами | BLOCKER |
| AC-003 | `logs/`, точный `LOG_FILE`, `.tmp`/`.part`/посторонние имена, неверная глубина/расширение, каталоги, symlink и не-обычные файлы исключены; `ignored_regular_files` и `scanned_blobs` согласованы. | Unit-тесты классификации и summary | MAJOR |
| AC-004 | Обход не выходит за `STORAGE_ROOT`: неверный prefix, symlink-файл/каталог наружу и внутрь, symlink вместо namespace и подмена каталога не дают доступа за root. | Тесты `iter_files`/scanner с временным storage и symlink | BLOCKER |
| AC-005 | Файловый инвентарь собирается до БД; ключи читаются одним `SELECT` в отдельном соединении после инвентаря, в том числе при пустом инвентаре; DML/блокировок/commit нет. | Интеграционный тест с реальной PostgreSQL, отдельными соединениями и Event/barrier; проверка SQL/состояния | BLOCKER |
| AC-006 | Сверка read-only: строки `files`, статусы/история документов, blob-файлы и журнал не меняются; повторный запуск стабилен. | Снимок строк/файлов/журнала до и после; повторный запуск | BLOCKER |
| AC-007 | JSON-контракт, сортировка, summary, stdout/stderr, коды 0/1/2 и отсутствие секретов/абсолютных путей соответствуют design; кандидаты не являются сбоем. | CLI-тесты парсят JSON, проверяют ключи, сортировку, exit/stderr и redaction | BLOCKER |
| AC-008 | Ошибки: missing root без mkdir; пустой root/`documents` — успех после SELECT; нечитаемый root/подкаталог, root/namespace-file, исчезнувшая запись, DB/config failure и частичный обход — `failed` без частичных кандидатов. | Детерминированный fault injection плюс реальный tmp storage; таблица кодов | BLOCKER |
| AC-009 | Новые тесты и регрессии storage/FileService/полный backend зелёные; миграций по-прежнему 12; frontend/зависимости не изменены; diff — только allowlist. | `pytest` новые + полный; `ls alembic/versions/*.py | wc -l`; `git diff --name-only` | BLOCKER |
| AC-010 | ADR-009, ADR README и `PROJECT_STATUS` отражают report-only реализацию: сверка выполнена, удаление/расписание не заявлены; устаревшая запись о постоянном журнале устранена. | Чтение изменённых разделов; сверка с кодом и CLI | MAJOR |

## Команды проверок

| Команда | CWD | Ожидаемый результат |
| --- | --- | --- |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage --help'` | корень | exit 0, help без БД/.env |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_storage.py tests/test_storage_reconciliation.py tests/test_reconcile_storage_cli.py tests/test_file_service.py tests/test_file_service_concurrency.py'` | корень | exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | exit 0, 0 failed, passed ≥ 3400 + новые |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m app.reconcile_storage'` | корень | exit 0, валидный JSON; кандидаты допустимы |
| `git diff --name-only <baseline>..HEAD`; `git show --stat --oneline HEAD` | корень | только allowlist; evidence не в коммите |
| `ls alembic/versions/*.py \| wc -l` | корень | `12` |

## Текущее задание OpenCode

- Рабочая ветка/worktree: `main`, текущий workspace.
- Baseline: `7b785f4` (design), затем workflow-коммит TASK-MVP-02; точный HEAD
  фиксируется в evidence.
- Подход / цикл: A1 / C1.
- Реализовать design выше, обновить документацию, покрыть тестами, выполнить
  проверки, закоммитить разрешённые файлы в `main`; evidence-файл не коммитить.
- Не менять источники аудита, API, модели, конфигурацию, журнал, миграции,
  frontend и зависимости; не удалять blob; не запускать фоновые процессы.
- Формат результата: изменения, команды/CWD/exit/результаты, commit hash,
  ограничения и реальный `worker_done` по preamble Orca; проект PASS не
  присваивать.

## C2 — ограниченная коррекция после C1 FAIL

Baseline: review C1 на `a2b52a8`; новый commit — только в allowlist ниже.
Закрыть только `MVP02-R2-001…006`:

- `_success_report`: точный `status="complete"`; обновить тесты/CLI.
- `ignored_regular_files`: обычный файл, исключённый как точный `LOG_FILE`,
  учитывать один раз; он не входит в `scanned_blobs`. Симлинки, каталоги,
  нерегулярные файлы и файлы вне `documents` не учитывать. Проверить оба имени:
  каноническое и неканоническое.
- `StorageInventoryError`: отсутствующий root → внешний `error.code="root_missing"`;
  прочие безопасные коды/stage сохранить.
- Добавить детерминированный тест подмены проверенного каталога на symlink вне
  root для фактического scanner; при выявлении дефекта исправить в пределах AC-004.
- Добавить интеграционный тест AC-005: реальная PostgreSQL, отдельные соединения,
  Event/barrier; инвентарь удерживается, другое соединение вставляет/коммитит
  `files.storage_key`, затем SELECT после инвентаря видит подтверждённый ключ;
  ровно один SELECT, без DML/блокировок со стороны сверки.
- Добавить fault injection для нечитаемого root и ошибки stat через фактический
  scanner/reconciliation/CLI: `failed`, `complete=false`, `summary/orphans=null`,
  безопасный фиксированный код/stage, exit 1; после частичного инвентаря БД не
  опрашивается.

Остальные AC, allowlist, запреты и команды проверок не меняются. Evidence:
`../workflow/evidence/TASK-MVP-02-C2.md` (не коммитить до PASS). C1 evidence и
review сохраняются.

## Приёмка

C1: **FAIL** (6 MAJOR). Автор решения: Codex-ревьюер (R2), `task_4ac8b4f9eb5e` /
`ctx_51b60231d76c`. Проверенная ревизия: `a2b52a8`.
Находки `MVP02-R2-001…006`: `status=complete`; учёт `LOG_FILE` в
`ignored_regular_files`; код `root_missing`; детерминированный тест подмены
каталога; межсоединительный Event/barrier-тест порядка инвентаря и SELECT;
матрица ошибок root/stat. Подробности: `../workflow/reviews/TASK-MVP-02.md`.
C2: **PASS**. Автор решения: Codex-ревьюер (R2), `task_f5a7cda011c4` /
`ctx_f8b4e389182a`. Повторное полное ревью 2 / 2 ревизии `fde5406`:
AC-001…AC-010 PASS; `MVP02-R2-001…006` закрыты; новых findings 0. Отчёт:
`../workflow/reviews/TASK-MVP-02-C2.md`; evidence переиспользовано,
reviewer reruns 0. Codex calls 3 / 4; проектный PASS не присвоен.
Сводка/счётчики: ../workflow/STATE.md. История: ../workflow/HISTORY.md.
Пакеты доказательств: C1 `../workflow/evidence/TASK-MVP-02-C1.md`;
C2 `../workflow/evidence/TASK-MVP-02-C2.md`.
Следующий TASK: TASK-MVP-03.
