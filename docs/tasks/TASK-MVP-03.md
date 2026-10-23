# TASK-MVP-03 — Сверка SHA-256 при скачивании и индекс вложений

Статус: READY (design complete; implementation pending). Требования: VISION.md,
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

## Текущее задание OpenCode

- Рабочая ветка/worktree: `main`, текущий workspace.
- Baseline: `f0727e6` (workflow-резерв design); продуктовое состояние `fde5406`;
  точный HEAD и diff фиксируются в evidence.
- Подход / цикл: A1 / C1 (новый TASK, design выполнен Codex).
- Реализовать design выше, обновить статусные документы, добавить тесты и
  миграцию, выполнить проверки, применить миграцию к локальной рабочей БД,
  закоммитить разрешённые файлы в `main`; evidence-файл не коммитить.
- Не менять запрещённые пути; не исправлять ORM cascade/`passive_deletes`; не
  добавлять Range/HEAD/ETag, download/verify CLI, лимиты и квоты.
- Пакет доказательств: создать
  `docs/workflow/evidence/TASK-MVP-03-C1.md` по шаблону `EVIDENCE.md`; приложить
  diff, execution HEAD, результаты focused/full, migration up/down/up в test
  schema, SQL trace, ASGI start/body/closure, bounded-memory наблюдения и
  `EXPLAIN JSON`.
- Формат результата: изменения, команды/CWD/exit/результаты, commit hash,
  ограничения и реальный `worker_done` по preamble Orca; проектный PASS не
  присваивать.

## Приёмка по выбранному маршруту

Решение: NOT_REVIEWED. Автор решения: Codex-ревьюер (R2). Ревизия/diff: не
проверены. Design: `task_6f36396f2464` / `ctx_9b0738b3df2d`, memo
`msg_026fcb9a8ffb`. Сводка/счётчики: ../workflow/STATE.md. История:
../workflow/HISTORY.md. Подробный отчёт: `../workflow/reviews/TASK-MVP-03.md`
после ревью. Codex calls: design 1 / 4; полное ревью 0 / 2.
