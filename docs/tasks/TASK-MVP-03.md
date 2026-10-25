# TASK-MVP-03 — Сверка SHA-256 при скачивании и индекс вложений

Статус: PASS (A1/C2; implementation `40c6343`; C2 `6827ed3`; C1 review 1/2 —
FAIL, 2 MAJOR; C2 review 2/2 — PASS; открытых findings 0). Требования: VISION.md,
ARCHITECTURE.md, ROADMAP.md, ADR-009. Этап ROADMAP: 4.
Предшественники с обязательным PASS: TASK-MVP-02 PASS.
Класс риска: R2 (целостность содержимого, потоковая выдача, публичный HTTP-контракт,
миграция индекса и реальная PostgreSQL).
Маршрут приёмки: Codex-ревьюер. Design: Codex, `task_6f36396f2464` /
`ctx_9b0738b3df2d`; design memo — `msg_026fcb9a8ffb`; проектный PASS дизайном не
присваивается.

## Цель и область

Закрыть два отложенных ограничения ADR-009:

1. **Сверка SHA-256 при скачивании.** Перед отправкой ответа скопировать blob в
   приватный дисковый `TemporaryFile`, одновременно посчитать SHA-256 теми же
   чанками `CHUNK_SIZE = 65536`, сравнить с `File.sha256` и только после успешной
   проверки начать потоковую выдачу **проверенной копии**. Несовпадение или сбой
   подготовки — безопасный `500` до `response.start`; байты blob клиенту не
   уходят.
2. **Миграция `ix_files_document_id_id`.** Добавить non-unique btree-индекс
   `(files.document_id, files.id)` и отразить его в metadata модели. Индекс
   обслуживает FK/каскад и сортировку списка вложений.

Целевые компоненты: `app/api/files/download.py`, `app/api/files/router.py`,
`app/models/file.py`, новая Alembic revision `e4b8c2d16a70`, профильные тесты и
статусные документы.

Разрешено изменять: `app/api/files/router.py`, `app/api/files/download.py`,
`app/models/file.py`,
`alembic/versions/e4b8c2d16a70_add_ix_files_document_id_id.py`,
`tests/test_files_download_api.py`, `tests/test_file.py`,
`tests/test_files_index_migration.py`, `tests/test_document_verification_event.py`
(только текущие head/count baseline assertions), `tests/test_document_variants_api.py`
(только migration-count baseline и корректное имя/комментарий теста),
`docs/adr/ADR-009-document-attachments.md` (только статус/открытый вопрос сверки
SHA-256 и индекса), `docs/adr/README.md` (только статусные строки),
`docs/PROJECT_STATUS.md` (только ограничения 16/17 и статус).
Не затрагивать: остальные `alembic/versions/*.py`, `alembic/env.py`,
`tests/conftest.py`, `app/services/**`, `app/config.py`, `app/dependencies.py`,
`app/logging_config.py`, `app/reconcile_storage.py`, `app/api/files/schemas.py`,
`app/api/files/__init__.py`, модели документов/связей, `File` FK/relationship/
`passive_deletes`, lifecycle/transaction policy, reconciliation/CLI, frontend,
зависимости, `.env`, `.venv/`, реальный `storage/`, workflow-документы.

Инварианты: один `SELECT File` по `id` + `document_id` без lock; никаких DML,
commit/rollback/flush и history со стороны route; ровно один `storage.open` до
ответа; `Content-Length` и `size_bytes` не используются для длины тела; Range,
HEAD, ETag, Last-Modified и новый download/verify CLI не вводятся; пути,
`storage_key`, digest, `original_filename`, содержимое и `str(error)` не
логируются и не попадают в ответ; отсутствующая строка/чужой документ — прежний
404; нарушение целостности — прежний безопасный 500.

## Design-решения (приняты Codex)

- `download.py` получает `prepare_verified_download(source: BinaryIO,
  expected_sha256: str) -> BinaryIO` и `DownloadIntegrityError` с фиксированным
  текстом. Helper немедленно принимает владение исходным потоком, копирует его в
  `tempfile.TemporaryFile(mode="w+b")` чанками 64 KiB, считает SHA-256, делает
  `flush`/`seek(0)` и возвращает проверенную копию; исходный поток закрывается до
  возврата helper. При любом отказе закрываются оба ресурса; при успехе
  владение переходит только копии.
- Router копирует `sha256`, открывает blob один раз, вызывает helper **до**
  создания response и передаёт в `ClosingStreamingResponse` только проверенную
  копию. Ошибки open/read/copy/flush/rewind и mismatch до ответа — один и тот же
  `500` `{"detail":"Stored file content is unavailable"}` без
  `Content-Disposition` вложения, MIME, ETag, Content-Range и байтов blob.
- `size_bytes` не сравнивается и не исправляется; верный hash при неверном
  размере остаётся `200` без `Content-Length`. Пустой blob проверяется как
  обычный поток: `SHA-256(empty)` — успех, неверный digest — `500`.
- Один `logger.error` на отказ подготовки: `operation="file.download"`,
  `document_id`, `file_id`, `failure_category` (`content_open_failed`,
  `sha256_mismatch`, `content_prepare_failed`) и `error_type` (для mismatch —
  `DownloadIntegrityError`, иначе имя класса). Без `storage_key`, путей,
  `original_filename`, digest, байтов, `str/repr(error)`, traceback и `exc_info`.
- Поздняя ошибка чтения уже проверенной копии или `send` не может дать второй
  статус/JSON: поток прерывается, источник закрывается; для read failure helper
  пишет фиксированный безопасный `logger.error` с
  `failure_category="content_stream_failed"` и повторно поднимает исключение.
  Штатный client disconnect не считается порчей blob.
- `ClosingStreamingResponse` и `iter_blob` сохраняют закрытие при EOF, ошибке
  чтения, `send failure`, ASGI 2.0/2.4 disconnect и cancellation. Изменение
  исходного inode после проверки не меняет выдаваемые байты: отдаётся снимок.
- Миграция: `e4b8c2d16a70` от `a3f1c72d5b90`; только
  `op.create_index("ix_files_document_id_id", "files", ["document_id", "id"],
  unique=False)` в upgrade и `op.drop_index("ix_files_document_id_id",
  table_name="files")` в downgrade. Обычный btree, без CONCURRENTLY/IF EXISTS,
  partial/include/unique, без изменений FK/constraints/строк. В
  `File.__table_args__` добавить `Index("ix_files_document_id_id",
  "document_id", "id", unique=False)`; `CheckConstraint`/FK/relationship
  сохранить.
- `FileService.list_for_document` не меняется: запрос уже
  `WHERE document_id = :id ORDER BY id ASC`; левый префикс индекса обслуживает
  FK lookup, второй столбец — сортировку. ORM `db.delete(document)` и
  `passive_deletes` не исправляются; DB `ON DELETE CASCADE` проверяется только
  Core/SQL DELETE в disposable test schema.
- Тест миграции использует изолированную уникальную PostgreSQL test schema и
  child-process Alembic с `DATABASE_URL` и
  `PGOPTIONS='-csearch_path=<unique_test_schema>'`; `alembic/env.py` читает
  `Settings.DATABASE_URL`, поэтому `Config.set_main_option` недостаточно.
  Последовательность в тесте: `upgrade a3f1c72d5b90` → seed → `upgrade head` →
  `downgrade a3f1c72d5b90` → `upgrade head`; проверяются `alembic_version`,
  каталоги, данные и только созданная test schema. Public не мутировать; тест
  не печатает URL/пароль; teardown удаляет только созданную schema.

## Критерии приёмки

Чек-лист заморожен координатором до диспатча. Ревьюер проверяет строго по нему.

| ID | Критерий | Способ независимой проверки | Severity |
| --- | --- | --- | --- |
| AC-001 | Верный SHA-256 → `200`, точные байты PDF/JPEG/PNG и прежние безопасные заголовки; `Content-Length` отсутствует. | HTTP-тесты на реальной PostgreSQL и `LocalStorageBackend(tmp_path)`, включая сквозной upload/download. | BLOCKER |
| AC-002 | Порча blob той же длины, truncation, append и неверный digest в БД → одинаковый безопасный `500` **до** `response.start`; ни одного байта вложения, digest, ключа или пути. | HTTP и capture ASGI `send`; body ровно JSON detail; снимки БД/blob до и после. | BLOCKER |
| AC-003 | 404/чужой `document_id` не открывает storage; missing blob и ошибки open/stat → безопасный `500`; одна безопасная ERROR-запись нужной категории. | Реальный удалённый tmp blob, исчезновение между `is_file`/`open`, инъекция `StorageError`/`OSError`/`PermissionError` с секретами в тексте; `caplog`/JSON Lines formatter. | BLOCKER |
| AC-004 | Ошибки `source.read` после нескольких чанков и temp create/write/flush/seek до response → безопасный `500`, частичная копия не выдана, оба ресурса закрыты; ошибка конструктора response закрывает готовую копию. | Контролируемые IO failpoints поверх реального tmp storage; проверки `source.closed`/`temp.closed`, отсутствие `response.start`; отдельный тест конструктора. | BLOCKER |
| AC-005 | Пустой blob с `SHA-256(empty)` → `200` с пустым телом; пустой с неверным digest → `500`; верный hash при неверном `size_bytes` → `200` без `Content-Length` и без исправления строки. | Ручной `seed_file` в реальной БД; завышенный и заниженный `size_bytes`; upload MIME/empty policy не расширять. | BLOCKER |
| AC-006 | Ровно один `storage.open`; bounded reads/writes; ASGI body chunks ≤ 65536; нет `seek`/`fileno`/`stat` исходного stream; изменение исходного файла после проверки не меняет выдаваемые байты. | Nonseekable `RecordingStream`; tmp snapshot + tamper исходного inode после helper; ASGI send без накопления body; helper-only `tracemalloc` на lazy 1 MiB и 100 MiB — Python peak ≤ 8 MiB. | BLOCKER |
| AC-007 | Оригинал закрыт до начала ответа; snapshot закрыт при EOF/read failure/send failure/disconnect ASGI 2.0/2.4/cancellation; поздняя ошибка не создаёт второй `response.start`/JSON. | Прямые ASGI `TestStreamRelease` с проверенной disk copy; late read fail после start проверяет abort/closure, а не невозможный `500`. | BLOCKER |
| AC-008 | Для success/mismatch/read failure/404 остаётся ровно один `SELECT File` без `FOR UPDATE/SHARE` и без DML/commit/route rollback/history/status changes. | SQLAlchemy `before_cursor_execute` + spies `Session.commit/rollback`; snapshots File/Document/events, hash blob до/после; teardown `Session.close` не считать действием endpoint. | BLOCKER |
| AC-009 | Ровно новая ревизия `e4b8c2d16a70` с верным predecessor; реальный up/down/up создаёт/удаляет только индекс и сохраняет строки/constraints. | Изолированная уникальная PostgreSQL schema; child-process Alembic с `PGOPTIONS`; проверка `alembic_version`, каталогов и данных; public не мутировать. | BLOCKER |
| AC-010 | В metadata и живом `pg_catalog` один nonunique valid btree на `files(document_id, id)` в данном порядке; список сортируется/изолируется по документу; DB cascade работает. | `Inspector` + `pg_index`/`pg_indexes`; list и Core cascade tests с соседним документом; `ANALYZE` + `EXPLAIN(FORMAT JSON)`; при малых таблицах допустим Seq Scan, отдельно `enable_seqscan=off`/`enable_bitmapscan=off` показывает доступность Index Scan без Sort. | BLOCKER |
| AC-011 | ADR-009, ADR README и `PROJECT_STATUS` отражают выполненную сверку SHA-256 и созданный индекс; снятые ограничения 16/17 закрыты, нереализованные пункты не заявлены. | Чтение изменённых разделов; сверка с кодом, миграцией и фактическим поведением. | MAJOR |

## Команды проверок

| Команда | CWD | Ожидаемый результат |
| --- | --- | --- |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_files_download_api.py tests/test_files_integration_api.py tests/test_file.py tests/test_files_index_migration.py tests/test_storage.py tests/test_document_verification_event.py tests/test_document_variants_api.py'` | корень | exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | exit 0, 0 failed, последовательно без xdist |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m alembic heads'` | корень | ровно `e4b8c2d16a70 (head)` |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic current'` | корень | миграция применена; current = `e4b8c2d16a70 (head)` |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | `13` |
| `git diff --name-only <baseline>..HEAD`; `git show --stat --oneline HEAD` | корень | только allowlist; evidence не в коммите |

## C2 correction (выполнено; PASS 2/2)

- Рабочая ветка/worktree: `main`, текущий workspace.
- Baseline C2: `0587ccc`; продуктовое состояние `40c6343`; точный HEAD и diff
  фиксируются в evidence C2.
- Подход / цикл: A1 / C2; исправить только пробелы, указанные в
  `reviews/TASK-MVP-03.md`; замороженный checklist AC-001…AC-011 не меняется.
- MVP03-R2-001 (AC-003): добавить контролируемую инъекцию на границе
  `is_file`/`open` реального `LocalStorageBackend`: `is_file()` должен успешно
  пройти, tmp blob удаляется непосредственно перед физическим `Path.open`, затем
  безопасный `500`, отсутствие байтов/секретов и ровно одна запись
  `content_open_failed`. Не заменять сценарий удалением до `is_file`.
- MVP03-R2-002 (AC-006, AC-007): добавить disk-backed ASGI-проверки с реальным
  результатом `prepare_verified_download` для EOF, read failure, send failure,
  disconnect ASGI 2.0 и 2.4, cancellation: проверять закрытие реального снимка и
  единственный `response.start`/отсутствие JSON после start. Для AC-006 добавить
  ASGI-наблюдатель, который считает длины чанков/общую длину и потоковый hash,
  не накапливая body.
- Разрешённые изменения C2: `tests/test_files_download_api.py` и новый
  `docs/workflow/evidence/TASK-MVP-03-C2.md`; при доказанной необходимости —
  только тестовые файлы из allowlist TASK. Продуктовый код, миграция,
  `app/services/**`, `alembic/env.py`, `tests/conftest.py`, frontend,
  зависимости, `.env`, `.venv/`, реальный `storage/` и workflow-документы
  координатора не менять.
- Выполнить focused и полный `pytest`, подтвердить 13 миграций и неизменность
  `e4b8c2d16a70`; закоммитить только тестовые изменения в `main`, evidence C2 не
  коммитить.
- Пакет доказательств: `docs/workflow/evidence/TASK-MVP-03-C2.md` по шаблону
  `EVIDENCE.md`: diff, execution HEAD, новые тесты с фактическими именами,
  команды/CWD/exit/результаты, ASGI/closure-наблюдения и честное описание
  сценариев.
- Формат результата: изменения, команды/CWD/exit/результаты, commit hash,
  ограничения и реальный `worker_done` по preamble Orca; проектный PASS не
  присваивать.

## Приёмка по выбранному маршруту

Решение C1: FAIL (2 MAJOR); решение C2: PASS. Автор решений: Codex-ревьюер
(R2). Findings `MVP03-R2-001`, `MVP03-R2-002` (MAJOR) закрыты на `6827ed3`;
новых findings 0. Отчёты: `../workflow/reviews/TASK-MVP-03.md` (C1 FAIL) и
`TASK-MVP-03-C2.md` (C2 PASS). Ревизия/diff C1: `40c6343`, C2: `6827ed3`;
evidence C1/C2: `../workflow/evidence/TASK-MVP-03-C1.md`,
`TASK-MVP-03-C2.md`. Design:
`task_6f36396f2464` / `ctx_9b0738b3df2d`, memo `msg_026fcb9a8ffb`;
implementation `task_f53910e0735d` / `ctx_331ce3d2a440`; C1 review
`task_93712a9c9442` / `ctx_3f22c5d23a39`; C2 `6827ed3` (`task_a39b81e726c5` /
`ctx_6e41326def5e`); C2 review `task_b03f28ce101c` / `ctx_894373b5df1a`.
Сводка/счётчики: ../workflow/STATE.md. История: ../workflow/HISTORY.md.
Codex calls: design 1 / 4; C1 review 2 / 4; C2 review 3 / 4; полные ревью
2 / 2 использовано. Следующий TASK — TASK-WF-01 (Nemotron-координатор) до
TASK-MVP-04.
