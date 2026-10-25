# TASK-MVP-03 / C1 — evidence независимой проверки

## Идентификация

- TASK: TASK-MVP-03 — сверка SHA-256 при скачивании и индекс вложений.
- Подход / цикл: A1 / C1; класс риска R2; маршрут приёмки — Codex-ревьюер.
- Workspace: `D:\Antigravity\EquipmentDocumentationRegistry`
  (`/mnt/d/Antigravity/EquipmentDocumentationRegistry`), ветка `main`.
- Baseline C1: `db96b7a712c281c41bd69f6b000a1d94048f068f`; продуктовое
  состояние до TASK: `fde540677fa1dc5ecc3ff359bc1c989af6f4b26c`.
- Проверенный HEAD / implementation commit:
  `40c6343a29ee553351aa3c96994061c3ede7b225`
  (`feat(files): verify SHA-256 on download and index attachments`).
- Orca: run `run_68046cea3eb4`; task `task_f53910e0735d`; dispatch
  `ctx_331ce3d2a440`; worker terminal
  `term_236f7648-d312-4be1-8656-1d410f717689`; coordinator terminal
  `term_18db67ad-1811-4fb6-a708-7f4049ee1ceb`.
- Дата: 2026-10-24. Автор: отдельный OpenCode-исполнитель.
- Характер работы: независимая верификация уже существующего коммита; новый
  продуктовый код не писался. Дефектов, требующих исправления в allowlist, не
  найдено, поэтому `40c6343` оставлен без изменений и новых коммитов нет.

## Diff и allowlist

`git diff --name-status db96b7a..HEAD` — ровно 12 файлов, все в allowlist:

| Статус | Файл |
| --- | --- |
| A | `alembic/versions/e4b8c2d16a70_add_ix_files_document_id_id.py` |
| M | `app/api/files/download.py` |
| M | `app/api/files/router.py` |
| M | `app/models/file.py` |
| M | `docs/PROJECT_STATUS.md` |
| M | `docs/adr/ADR-009-document-attachments.md` |
| M | `docs/adr/README.md` |
| M | `tests/test_document_variants_api.py` |
| M | `tests/test_document_verification_event.py` |
| M | `tests/test_file.py` |
| M | `tests/test_files_download_api.py` |
| A | `tests/test_files_index_migration.py` |

`git show --stat --oneline HEAD`: `12 files changed, 1531 insertions(+),
97 deletions(-)`. `git diff --check` — exit 0, ошибок нет. Diff по запрещённым
путям (`alembic/env.py`, `tests/conftest.py`, `app/services/storage.py`,
`app/services/file_service.py`, `app/services/local_storage.py`,
`app/config.py`, `app/dependencies.py`, `app/logging_config.py`,
`app/api/files/schemas.py`, `app/api/files/__init__.py`,
`app/models/document.py`) пуст. Из `alembic/versions/` изменён только
`e4b8c2d16a70_add_ix_files_document_id_id.py`. Секретов в diff нет: совпадения
`secret` — только тестовые пути/строки, проверяющие отсутствие утечки.

## Соответствие AC

| ID | Статус | Доказательство |
| --- | --- | --- |
| AC-001 | выполнено | `TestStoredBytes`: PDF/JPEG/PNG байт-в-байт, MIME из строки, безопасный `Content-Disposition`, `Content-Length` отсутствует; сквозной upload/download. |
| AC-002 | выполнено | `TestIntegrityCheck[same_length/truncated/appended]`, `test_a_wrong_digest_in_the_row_is_a_safe_500`, ASGI `test_a_mismatch_is_decided_before_the_response_starts`: ровно один `500`, body = `{"detail":"Stored file content is unavailable"}`, без `Content-Disposition`, MIME вложения, digest, ключа, пути и байтов blob. |
| AC-003 | выполнено | `TestBrokenStorage`: удалённый blob, `StorageError`/`OSError`/`PermissionError`, исчезновение между проверкой и `open`; `test_a_404_never_opens_storage` (`opened_keys == []`); ровно одна ERROR-запись `operation="file.download"`, `failure_category="content_open_failed"`, безопасный `error_type`; секреты из текста ошибок не попадают в ответ/`caplog`. |
| AC-004 | выполнено | `TestPreparationFailures`: read failure после нескольких чанков, temp create/write/flush/seek; `source.closed` и `temp.closed`, `500`, без `response.start`/частичной копии; `test_a_response_constructor_failure_closes_the_verified_copy`. |
| AC-005 | выполнено | `TestEmptyAndStaleSize`: пустой blob + SHA-256(empty) → `200`/пустое тело; пустой + неверный digest → `500`; `size_bytes` 0/1/10 000 000 при верном hash → `200`, `Content-Length` отсутствует, строка не исправляется. |
| AC-006 | выполнено | `TestStreaming` (`opened_keys == 1`, чтение 64 КиБ), `TestAsgiContract` (body-чанки ≤ 65536), `TestBoundedMemory` (1 MiB и 100 MiB, Python peak ≤ 8 MiB), `TestVerifiedSnapshot.test_later_changes_to_the_source_do_not_change_the_copy`; `RecordingStream` падает на `seek`/`fileno`/`stat`, helper их не вызывает. |
| AC-007 | выполнено | `TestStreamRelease`: завершение, read failure, send failure, disconnect ASGI 2.0 и 2.4, cancellation — source/snapshot закрыт; `TestAsgiContract`: оригинал закрыт до `response.start`, поздний read failure не даёт второго start/JSON, disk snapshot закрывается при обрыве. |
| AC-008 | выполнено | `TestNoSideEffects`: success/mismatch/read failure/404 — ровно один `SELECT ... FROM files` без `FOR UPDATE/SHARE`, без DML/COMMIT/ROLLBACK; `Session.commit/rollback` запрещены; status/events/File-строка и blob не меняются. |
| AC-009 | выполнено | `tests/test_files_index_migration.py::test_upgrade_downgrade_up_creates_only_the_index`: изолированная уникальная schema, child-process Alembic с `DATABASE_URL` и `PGOPTIONS='-csearch_path=<schema>'`, последовательность `upgrade a3f1c72d5b90` → seed → `upgrade head` → `downgrade a3f1c72d5b90` → `upgrade head`; проверены `alembic_version`, строки, constraints, каталог индекса; public version/count не изменены; teardown удаляет только созданную schema. |
| AC-010 | выполнено | `tests/test_file.py::TestFileIndexes`: metadata ровно один `Index("ix_files_document_id_id", "document_id", "id", unique=False)`, порядок столбцов, без dialect options. Реальный `pg_catalog` (test schema и public) — nonunique, valid, btree, без predicate/expressions; list-запрос изолирует документ и сортирует по `id`; Core `DELETE` документа каскадно удаляет файлы; `EXPLAIN (FORMAT JSON)` при `enable_seqscan=off`/`enable_bitmapscan=off` — `Index Only Scan` по индексу без `Sort`. |
| AC-011 | выполнено | ADR-009 (шапка, «Статус реализации», раздел скачивания/миграции, «Нерешённые вопросы»), ADR README и PROJECT_STATUS отражают реализованные сверку SHA-256 и индекс `e4b8c2d16a70`; ограничения 16/17 помечены снятыми; аутентификация/авторизация по-прежнему заявлены как невыполненные. |

## Выполненные команды

WSL Ubuntu; CWD — корень репозитория. Exit-коды фактические.

| # | Команда | Exit | Фактический результат |
| --- | --- | --- | --- |
| 1 | `.venv/bin/python -m pytest -q tests/test_files_download_api.py tests/test_files_integration_api.py tests/test_file.py tests/test_files_index_migration.py tests/test_storage.py tests/test_document_verification_event.py tests/test_document_variants_api.py` | 0 | `365 passed, 1 warning in 62.25s` |
| 2 | `.venv/bin/python -m pytest -q` | 0 | `3523 passed, 1 warning in 518.03s (0:08:38)`; 0 failed; warning — прежний `StarletteDeprecationWarning` |
| 3 | `.venv/bin/python -m alembic heads` | 0 | `e4b8c2d16a70 (head)` |
| 4 | `.venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic current` | 0 | миграция уже применена (upgrade идемпотентен); `current` = `e4b8c2d16a70 (head)` |
| 5 | `ls alembic/versions/*.py \| wc -l` | 0 | `13` |
| 6 | `.venv/bin/python -m pytest -v tests/test_files_download_api.py::TestNoSideEffects::test_the_route_issues_one_select_without_a_lock_or_a_write tests/test_files_download_api.py::TestNoSideEffects::test_failure_paths_issue_one_select_and_write_nothing tests/test_files_download_api.py::TestIntegrityCheck::test_a_mismatch_is_decided_before_the_response_starts tests/test_files_download_api.py::TestAsgiContract tests/test_files_download_api.py::TestStreamRelease tests/test_files_download_api.py::TestBoundedMemory tests/test_files_download_api.py::TestStreaming::test_the_blob_is_read_in_bounded_chunks_and_then_closed tests/test_files_index_migration.py` | 0 | `19 passed, 1 warning in 20.60s` (ASGI, release, bounded memory, SQL trace, migration) |
| 7 | `git diff --check` | 0 | вывод пуст |
| 8 | `git status --porcelain=v1 --untracked-files=all` | 0 | до evidence — пусто; после создания evidence — только `?? docs/workflow/evidence/TASK-MVP-03-C1.md` |
| 9 | `git log --oneline db96b7a..HEAD` | 0 | один коммит `40c6343` |
| 10 | `.venv/bin/python -m alembic history -r a3f1c72d5b90:e4b8c2d16a70` | 0 | `a3f1c72d5b90 -> e4b8c2d16a70 (head), add ix_files_document_id_id` |

### Реальная миграция в test schema

`test_upgrade_downgrade_up_creates_only_the_index` использует schema
`test_mvp03_<uuid>`. Alembic запускается дочерним процессом с
`DATABASE_URL` и `PGOPTIONS=-csearch_path=<schema>`; тест проверяет
`alembic_version`, каталог `pg_index`/`pg_indexes`, столбцы, constraints и
строки на каждом шаге up/down/up. `public_snapshot()` до и после теста
фиксирует `public.alembic_version` и `count(public.files)` — они не менялись.
Teardown выполняет только `DROP SCHEMA IF EXISTS "<schema>" CASCADE`; URL и
пароль в вывод не печатаются.

## SQL trace, ASGI, память, EXPLAIN

- SQL trace: `test_the_route_issues_one_select_without_a_lock_or_a_write` и
  `test_failure_paths_issue_one_select_and_write_nothing[mismatch/read_failure/
  missing_row]` слушают `before_cursor_execute` и требуют ровно один
  `SELECT ... FROM files`; `FOR UPDATE`, `FOR SHARE`, DML, `COMMIT`, `ROLLBACK`
  отсутствуют; `Session.commit/rollback` заменены на `AssertionError`.
- ASGI: `test_a_verified_download_starts_after_the_original_is_closed` —
  `http.response.start` только после `source.closed == True`, ровно один
  `storage.open`, body-чанки ≤ 65536;
  `test_a_late_read_failure_produces_no_second_start_or_json` — один start
  `200`, без JSON-detail, одна запись
  `content_stream_failed`.
- Память: `test_verification_keeps_python_memory_bounded[1048576]` и
  `[104857600]` — `tracemalloc` peak ≤ 8 MiB, все чтения исходника по 65536.
- `EXPLAIN (FORMAT JSON)` на public DB при `enable_seqscan=off`,
  `enable_bitmapscan=off` после `ANALYZE files`:
  `Node Type = "Index Only Scan"`, `Index Name = "ix_files_document_id_id"`,
  дочерних узлов и `Sort` нет. Каталог: `(indisunique=False, indisvalid=True,
  no_predicate=True, no_expressions=True, amname="btree",
  "CREATE INDEX ix_files_document_id_id ON public.files USING btree
  (document_id, id)")`, столбцы `["document_id", "id"]`.
  План на public — дополнительная проверка; тот же результат в изолированной
  schema утверждает migration-тест.

## Ограничения и остаточные риски

- Продуктовый код, тесты и статусные документы не изменялись; новых коммитов
  нет. Evidence не закоммичен (`??`).
- Push, merge, deploy, удаление важных данных и следующий TASK не выполнялись;
  проектный PASS не присваивался.
- Миграция применена к локальной рабочей БД; `upgrade head` был идемпотентен.
  В `public.files` на момент проверки 3 ранее существовавшие строки
  (uploaded_at 2026-10-20, не созданные TASK и не изменённые проверками).
- Остаточные документационные наблюдения вне AC-011/allowlist: ADR-009 всё ещё
  указывает «76 тестов» для `tests/test_files_download_api.py`, тогда как
  `--collect-only` даёт 110; строка «Рабочая БД … строк: 0» не учитывает
  3 существующие строки. Эти снимки не противоречат заявлениям AC-011 о
  SHA-256/индексе и оставлены без правки, чтобы не выходить за разрешённый
  объём.
- Риск helper при исключении из `source.close()` в `finally` (маскирование
  исходной ошибки) не покрыт AC и не воспроизводился; штатные файловые потоки
  закрываются без ошибок.
- Реальные числа зафиксированы по выводу команд выше; не измеренные значения
  не приводятся.
