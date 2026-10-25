# TASK-MVP-03 / C2 — пакет доказательств

## Идентификация

- TASK: TASK-MVP-03 — сверка SHA-256 при скачивании и индекс вложений.
- Подход / цикл: A1 / C2 (коррекция после C1 FAIL, только два MAJOR).
- Класс риска: R2; маршрут приёмки — Codex-ревьюер.
- Workspace: `D:\Antigravity\EquipmentDocumentationRegistry`
  (`/mnt/d/Antigravity/EquipmentDocumentationRegistry`), ветка `main`.
- Baseline C2: `0587ccc4e96e0ac7c3b37fd196d5154e8540d3ed`
  (`docs(workflow): record TASK-MVP-03 implementation`).
- Продуктовое состояние, проверенное ревью C1:
  `40c6343a29ee553351aa3c96994061c3ede7b225`; в C2 продуктовый код,
  миграция и статусные документы не изменялись.
- Итоговый HEAD / commit C2:
  `6827ed3ae843b1d3f497257c3796144aab44e234`
  (`test(files): cover TASK-MVP-03 R2 open race and ASGI release gaps`),
  1 файл, `398 insertions(+), 10 deletions(-)`.
- Orca: task `task_a39b81e726c5`; dispatch `ctx_6e41326def5e`; worker terminal
  `term_2ab1afeb-7e6d-46a0-a13c-6101eb0419ad`; coordinator terminal
  `term_3e8f409a-91dc-4d97-aa10-f7b5e03a69f5`.
- Дата: 2026-10-25. Автор: отдельный OpenCode-исполнитель.
- Характер работы: исправлены только пробелы `MVP03-R2-001` (AC-003) и
  `MVP03-R2-002` (AC-006, AC-007); замороженный чек-лист AC-001…AC-011 не
  менялся. Продуктовый PASS не присваивается.

## Diff и allowlist

`git diff --name-status 0587ccc..HEAD` — ровно один файл:

| Статус | Файл |
| --- | --- |
| M | `tests/test_files_download_api.py` |

`git show --stat --oneline HEAD`: `6827ed3 test(files): cover TASK-MVP-03 R2
open race and ASGI release gaps`, `1 file changed, 398 insertions(+),
10 deletions(-)`. `git diff --check 0587ccc..HEAD` — вывод пуст.

Продуктовые файлы (`app/api/files/**`, `app/models/file.py`,
`app/services/**`, `alembic/**`), `tests/conftest.py`, frontend, зависимости,
`.env`, `.venv/`, `storage/` и workflow-документы координатора не изменялись.
Посторонние локальные правки координатора (`ROADMAP.md`, ADR README,
`docs/tasks/TASK-MVP-03.md`, `APPROVALS.md`, `HISTORY.md`, `STATE.md`) и
untracked `ADR-011`, C1 evidence, review сохранены без изменений и в коммит не
входят. Evidence C2 не закоммичен.

## Что изменено в тестах

Все изменения — в `tests/test_files_download_api.py`.

| Блок | Назначение |
| --- | --- |
| `TestBrokenStorage::test_a_blob_vanishing_between_the_check_and_the_open_is_a_safe_500` | Переписан под `MVP03-R2-001`: инъекция строго между успешным `is_file()` и физическим `Path.open("rb")` реального `LocalStorageBackend.open`. |
| `AsgiObserver` / `run_app_observed` | ASGI `send`-наблюдатель: считает `response.start`, длины чанков, общую длину и потоковый SHA-256, не сохраняя тело; отдаёт реальный app без накопления сообщений. |
| `verified_disk_snapshot` | Готовит реальный `TemporaryFile` через настоящий `prepare_verified_download` поверх реального файла на диске. |
| `TestDiskSnapshotAsgiRelease` (6 тестов) | Disk-backed ASGI-выходы: EOF, read failure, send failure, disconnect ASGI 2.4, наблюдаемый disconnect ASGI 2.0, cancellation. В каждом проверяются закрытие реального снимка, ровно один `response.start` и отсутствие JSON после start. |
| `TestAsgiContract::test_the_route_streams_a_real_disk_snapshot_without_buffering` | Реальный маршрут по ASGI: реальный backend, реальный helper, перехваченный настоящий `TemporaryFile`; observer проверяет чанки/длину/hash без накопления и закрытие снимка после EOF. |

### `MVP03-R2-001` — честное описание сценария

Blob создаётся через `LocalStorageBackend.save` и строку `File` в реальной
PostgreSQL test schema; перед запросом отдельно подтверждается
`target.is_file() is True`. В тесте `monkeypatch` подменяет
`pathlib.Path.is_file` на записывающую обёртку (фиксирует `True` только для
целевого пути) и `pathlib.Path.open` на обёртку, которая для целевого пути в
режиме `"rb"` вызывает `unlink()` непосредственно перед вызовом настоящего
`Path.open`, после чего тот поднимает `FileNotFoundError`. Сам
`LocalStorageBackend.open` не подменяется: выполняются его настоящие
`_resolve()` и проверка `is_file()`, поэтому успешный `is_file` и последующее
исчезновение файла происходят на реальной границе. Это контролируемая
in-process инъекция на файловой границе, а не гонка двух процессов.

Проверено: `checks == [True]` (is_file успешен), `removed_before_open == [True]`,
`target.exists() is False`, ответ `500` с ровно
`{"detail": "Stored file content is unavailable"}`, отсутствие
`Content-Disposition`, байтов PDF, `storage_key`, пути root и digest в ответе;
ровно одна ERROR-запись с `operation="file.download"`,
`failure_category="content_open_failed"`, `error_type="FileNotFoundError"`;
`storage_key`, root, digest и `scan.pdf` отсутствуют в `caplog.text`.

### `MVP03-R2-002` — ASGI/closure-наблюдения

| Сценарий | Инъекция / вход | Проверено |
| --- | --- | --- |
| EOF, ASGI 2.4 | реальный снимок `prepare_verified_download` из файла на диске; observer как `send` | `snapshot.closed is True`; один start 200; чанки по 65536 и один хвост; total = длине данных; streaming SHA-256 = SHA-256 данных; `application/pdf`; нет `Content-Length`; JSON после start отсутствует; исходный файл не изменён |
| Read failure | `FailingSnapshotStream` делегирует чтение реальному снимку и на втором `read` поднимает `OSError("cannot read /srv/secret/snapshot")` | `ClientDisconnect` (Starlette 2.4); `snapshot.closed` и `failing.closed`; один start 200; отправлен ровно один чанк 65536, JSON нет; одна запись `content_stream_failed`/`OSError`; `/srv` и `secret` не логируются |
| Send failure | `send` записывает первый чанк и поднимает `RuntimeError` | `RuntimeError` пробрасывается; `snapshot.closed`; один start 200; один чанк 65536; JSON после start отсутствует |
| Disconnect ASGI 2.4 | `send` записывает первый чанк и поднимает `OSError` (клиент ушёл) | Starlette преобразует в `ClientDisconnect`; `snapshot.closed`; один start 200; один чанк; JSON нет |
| Disconnect ASGI 2.0 | `receive` ждёт первый отправленный чанк, затем возвращает `http.disconnect`; `send` замедлен | наблюдаемый частичный streaming: `0 < total_length < len(data)`; `snapshot.closed`; ровно один start 200; JSON нет |
| Cancellation | задача ASGI отменяется после первого чанка (`task.cancel()`) | `snapshot.closed`; один start 200; один чанк 65536; JSON нет |
| EOF реального маршрута (AC-006) | реальный app, реальный `LocalStorageBackend`, настоящий `TemporaryFile` перехвачен фабрикой | observer без накопления тела: длины чанков ≤ 65536, total = длине, streaming hash совпадает; один start 200; `application/pdf`, `Content-Disposition` есть, `Content-Length` нет; JSON после start нет; перехваченный снимок `closed is True` |

«Нет JSON после start» проверяется двумя независимыми признаками: observer
ищет `b'"detail"'` в каждом body-чанке после start и тесты утверждают
`application/pdf` в start; тело нигде не объединяется в список.

## Новые и изменённые тесты (фактические имена)

- `tests/test_files_download_api.py::TestBrokenStorage::test_a_blob_vanishing_between_the_check_and_the_open_is_a_safe_500` (изменён)
- `tests/test_files_download_api.py::TestDiskSnapshotAsgiRelease::test_the_real_snapshot_is_closed_and_hashed_at_eof`
- `tests/test_files_download_api.py::TestDiskSnapshotAsgiRelease::test_a_read_failure_closes_the_real_snapshot`
- `tests/test_files_download_api.py::TestDiskSnapshotAsgiRelease::test_a_send_failure_closes_the_real_snapshot`
- `tests/test_files_download_api.py::TestDiskSnapshotAsgiRelease::test_an_asgi_2_4_disconnect_closes_the_real_snapshot`
- `tests/test_files_download_api.py::TestDiskSnapshotAsgiRelease::test_an_observed_asgi_2_0_disconnect_closes_the_real_snapshot`
- `tests/test_files_download_api.py::TestDiskSnapshotAsgiRelease::test_a_cancelled_request_closes_the_real_snapshot`
- `tests/test_files_download_api.py::TestAsgiContract::test_the_route_streams_a_real_disk_snapshot_without_buffering`

Файл профильных тестов: было 110 collected, стало 117 (+7: шесть новых
disk-backed тестов и один route-level observer-тест; изменённый тест заменён
на месте).

## Выполненные проверки

Все команды — в WSL Ubuntu; внешний CWD
`D:\Antigravity\EquipmentDocumentationRegistry`, WSL CWD — корень
`/mnt/d/Antigravity/EquipmentDocumentationRegistry`. Exit-коды фактические.

| # | Команда | CWD | Exit | Фактический результат |
| --- | --- | --- | --- | --- |
| 1 | `.venv/bin/python -m pytest -q tests/test_files_download_api.py tests/test_files_integration_api.py tests/test_file.py tests/test_files_index_migration.py tests/test_storage.py tests/test_document_verification_event.py tests/test_document_variants_api.py` | корень | 0 | `372 passed, 1 warning in 57.70s` |
| 2 | `.venv/bin/python -m pytest -q` | корень | 0 | `3530 passed, 1 warning in 467.62s (0:07:47)`; 0 failed; warning — прежний `StarletteDeprecationWarning` |
| 3 | `.venv/bin/python -m pytest -q tests/test_files_download_api.py` (повтор после коммита) | корень | 0 | `117 passed, 1 warning in 16.21s` |
| 4 | `.venv/bin/python -m alembic heads` | корень | 0 | `e4b8c2d16a70 (head)` |
| 5 | `ls alembic/versions/*.py \| wc -l` | корень | 0 | `13` |
| 6 | `.venv/bin/python -m alembic current` | корень | 0 | `e4b8c2d16a70 (head)` (плюс две INFO-строки Alembic) |
| 7 | `git diff --name-status 0587ccc..HEAD`; `git show --stat --oneline HEAD` | корень | 0 | `M tests/test_files_download_api.py`; `6827ed3`, 1 файл, `398 insertions(+), 10 deletions(-)` |
| 8 | `git diff --check 0587ccc..HEAD`; `git status --porcelain=v1 --untracked-files=all` | корень | 0 | diff без ошибок; в status только посторонние правки/untracked документы координатора и новый untracked evidence C2 |

Полный прогон (#2) выполнен на рабочем дереве, содержимое
`tests/test_files_download_api.py` которого побайтово совпадает с коммитом
`6827ed3`: после прогона файл был закоммичен без правок, а повтор #3 после
коммита дал тот же результат. Продуктовый код и миграции между прогонами не
менялись.

## Покрытие затронутых критериев

| Критерий | Статус | Чем подтверждено |
| --- | --- | --- |
| AC-003 | done (в объёме finding) | Изменённый `test_a_blob_vanishing_between_the_check_and_the_open_is_a_safe_500`: успешный `is_file`, удаление ровно перед настоящим `Path.open`, безопасный 500 без байтов/секретов, ровно одна запись `content_open_failed`/`FileNotFoundError`. Прежние тесты missing blob и `StorageError`/`OSError`/`PermissionError`, а также 404-без-storage сохранены. |
| AC-006 | done (в объёме finding) | `AsgiObserver` не накапливает тело: длины чанков ≤ 65536, total = длине, потоковый hash; применён к EOF-снимку и к реальному маршруту (`test_the_route_streams_a_real_disk_snapshot_without_buffering`). Существующие проверки одного `storage.open`, bounded reads/writes и helper-only tracemalloc сохранены. |
| AC-007 | done (в объёме finding) | Шесть disk-backed ASGI-тестов `TestDiskSnapshotAsgiRelease` для EOF, read failure, send failure, ASGI 2.4/2.0 disconnect и cancellation: реальный снимок закрыт, ровно один start, JSON после start отсутствует; read failure логируется одной безопасной записью. Прежние generic release-тесты сохранены. |

AC-001, AC-002, AC-004, AC-005, AC-008, AC-009, AC-010, AC-011 не
затрагивались; их прежние тесты, миграция `e4b8c2d16a70` (13 миграций) и
статусные документы сохранены.

## Известные ограничения и остаточные риски

- Инъекция `MVP03-R2-001` — контролируемая подмена `Path.is_file`/`Path.open`
  на реальном `LocalStorageBackend.open` в одном процессе. Она детерминированно
  воспроизводит границу «успешный `is_file` → удаление → физический `open`», но
  не является межпроцессной гонкой.
- Read failure проверен failpoint-обёрткой над реальным дисковым снимком: она
  делегирует чтение настоящему файлу и закрывает его; это не физическая ошибка
  диска.
- В сценарии ASGI 2.0 disconnect проверяется наблюдаемый частичный streaming
  (`0 < total_length < len(data)`), а не точное число чанков: Starlette
  штатно гоняет отмену с следующим `send`, поэтому число отправленных чанков до
  disconnect не фиксируется контрактом.
- Отмеченный в C1 крайний случай исключения из `source.close()` в `finally`
  helper по-прежнему не покрыт AC; продуктовый код не менялся. Остаточные
  документационные снимки из C1 (число тестов/строк) вне allowlist C2 и не
  исправлялись.
- Push, merge, deploy, изменение реального storage и запуск следующего TASK не
  выполнялись; проектный PASS не присвоен. Evidence C2 не закоммичен.
