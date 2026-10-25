# TASK-MVP-03 — повторное полное R2-ревью A1/C2

**Вердикт: PASS.** Findings `MVP03-R2-001` и `MVP03-R2-002` закрыты
на `6827ed3`. Все AC-001…AC-011 подтверждены в замороженном объёме;
новых BLOCKER/MAJOR/MINOR/NIT нет. C1 FAIL и исходные замечания сохраняются
в [отчёте C1](TASK-MVP-03.md); настоящее решение относится к исправленной C2.

## Идентификация

- Дата: 2026-10-25. Автор: независимый Codex-ревьюер R2.
- TASK-MVP-03, A1/C2; последнее полное ревью подхода — **2/2**.
- По dispatch: Codex call **3/4**, input limit **3 000 000** токенов.
  Точное провайдерское потребление не предоставлено; счётчики не менялись.
- Review task `task_b03f28ce101c`, dispatch `ctx_894373b5df1a`, terminal
  `term_5de79d4e-cbc7-4fd8-a73e-782a9b95fc51`, run `run_68046cea3eb4`.
- Workspace `D:\Antigravity\EquipmentDocumentationRegistry`, ветка `main`.
- Проверенный HEAD C2: `6827ed3ae843b1d3f497257c3796144aab44e234`.
- Baseline C2: `0587ccc4e96e0ac7c3b37fd196d5154e8540d3ed`.
- Неизменённое продуктовое состояние C1:
  `40c6343a29ee553351aa3c96994061c3ede7b225`;
  исходный implementation diff — `db96b7a..40c6343`.
- Входы: [TASK и чек-лист](../../tasks/TASK-MVP-03.md),
  [C1 review](TASK-MVP-03.md), [C2 evidence](../evidence/TASK-MVP-03-C2.md),
  [C1 evidence](../evidence/TASK-MVP-03-C1.md), оба назначенных diff и AGENTS.md.
  Применены правила `autonomous-development` (routing-and-budget/review-policy)
  и ранее прочитанный version-matched guide установленного Orca.
- Исполнитель C2: OpenCode, task `task_a39b81e726c5`,
  dispatch `ctx_6e41326def5e`, terminal
  `term_2ab1afeb-7e6d-46a0-a13c-6101eb0419ad`.

## Diff, границы и сохранность прежних проверок

Фактический `git diff 0587ccc..6827ed3` содержит только
`tests/test_files_download_api.py`: **398 insertions(+), 10 deletions(-)**.
Прочитан весь этот diff, включая удалённые строки. Удалены старый неверный
VanishingStorage-сценарий и его ожидаемый StoredFileNotFoundError; вместо них
добавлена настоящая граница is_file/open с более строгими assertions.
Ни один прежний тест не удалён и не отключён, skips/xfail не добавлены;
остальные прежние тела тестов и assertions не изменены.

Read-only сравнение определений тестов показало **70 → 77**, удалённых имён
**0**, новых **7**: шесть TestDiskSnapshotAsgiRelease и один route-level
observer-тест. С учётом параметризации это согласуется с **110 → 117**
профильных pytest cases, **365 → 372** focused и **3523 → 3530** full.
Смена error_type в race-тесте на FileNotFoundError подтверждает исправленный
сценарий и не ослабляет проверку missing blob, оставшуюся отдельным тестом.

Полный `git diff 40c6343..6827ed3` дополнительно содержит только три ранее
зафиксированных workflow-файла из `0587ccc`: TASK-MVP-03.md, HISTORY.md и
STATE.md. Их изменения прочитаны: это запись реализации C1 и её evidence,
без изменения требований или критериев. Раздел замороженного чек-листа
в текущем TASK сравнён с `40c6343`: одинаковое содержимое, 3884 символа
в обоих нормализованных текстовых представлениях.

Продуктовые модули, модель, миграции и статусные документы C2 совпадают с
`40c6343`. Проверенные app/tests/alembic, PROJECT_STATUS и ADR-009 в workspace
совпадают с `6827ed3` (`git diff --exit-code` пуст, exit 0). Посторонние
локальные правки ROADMAP, ADR README, TASK, APPROVALS, HISTORY, STATE и
untracked ADR-011/C1/C2 evidence/C1 review сохранены. Они не входят в коммит
C2. Unexpected files в C2 diff нет.

Ревьюер создал только этот файл, без коммита. Продукт, тесты, миграции,
evidence и документы очереди не изменялись; следующий TASK не запускался.

## Закрытие findings C1

### MVP03-R2-001 — CLOSED

- **AC:** AC-003. **Исходная severity:** MAJOR.
- **Location C2:** `tests/test_files_download_api.py:824`;
  production boundary — `app/services/local_storage.py:107`.
- **Observed/repro C1:** blob удалялся до вызова backend.open, поэтому
  is_file уже видел отсутствие и повторял missing-blob случай.
- **Expectation:** реальный LocalStorageBackend.open должен получить
  успешный is_file, после которого файл исчезает перед физическим open;
  безопасный 500, отсутствие содержимого/секретов и одна корректная ERROR-запись.
- **Closure evidence:** C2 сохраняет настоящий LocalStorageBackend.open,
  Path.is_file делегирует реальному методу и записывает результат для
  целевого пути, а Path.open удаляет существующий blob непосредственно перед
  настоящим открытием в rb. Assertions `checks == [True]`,
  `removed_before_open == [True]` и отсутствие target подтверждают порядок.
  Ответ — точный безопасный JSON 500 без Content-Disposition/байтов PDF/
  storage_key/root/digest; единственная ERROR-запись имеет
  `content_open_failed`/`FileNotFoundError`; журнал не содержит ключа, пути,
  digest или имени файла. Сценарий детерминированный, in-process; evidence
  честно отличает его от межпроцессной гонки. Прогоны C2 включают этот тест.
- **Решение:** требуемая граница и closure assertions реализованы; CLOSED.

### MVP03-R2-002 — CLOSED

- **AC:** AC-006, AC-007. **Исходная severity:** MAJOR.
- **Locations C2:** `tests/test_files_download_api.py:487` (AsgiObserver),
  `:535` (FailingSnapshotStream), `:555` (verified_disk_snapshot),
  `:1850` (TestDiskSnapshotAsgiRelease), `:2169` (реальный маршрут).
- **Observed/repro C1:** ASGI capture сохранял всё тело; требуемые release
  сценарии в основном использовали BytesIO вместо проверенного disk snapshot.
- **Expectation:** observer без накопления body и прямые ASGI-проверки
  реальной проверенной копии для EOF/read/send/disconnect 2.0/2.4/cancellation,
  с закрытием snapshot и без второго start/JSON после начала ответа.
- **Closure evidence AC-006:** observer сохраняет start, числовые длины
  чанков и total, обновляет SHA-256 по поступающим байтам; body bytes не
  удерживает. В `:2169` выполняется настоящий app/route/backend/helper;
  фабрика лишь сохраняет handle настоящего TemporaryFile для assertion
  закрытия. Проверяются один start=200, PDF MIME, Content-Disposition,
  отсутствие Content-Length, точные длины чанков ≤65536, total и итоговый
  потоковый hash, `created[0].closed is True`.
- **Closure evidence AC-007:** шесть новых тестов сначала получают настоящий
  TemporaryFile через prepare_verified_download из реального файла на диске;
  исходник закрыт до передачи снимка response. EOF (`:1862`), read failure
  (`:1890`), RuntimeError из send (`:1925`), ASGI 2.4 OSError disconnect
  (`:1952`), наблюдаемый ASGI 2.0 disconnect (`:1978`) и cancellation
  (`:2015`) проверяют закрытие именно реального снимка и один start=200.
  Read-fail wrapper делегирует первое чтение и close настоящему файлу;
  проверяются partial body, отсутствие JSON, одна безопасная запись
  `content_stream_failed`/`OSError` без текста секретного пути.
  В ASGI 2.0 receive ждёт первый body chunk, затем сообщает disconnect;
  assert `0 < total_length < len(data)` подтверждает частичную передачу,
  а не отмену до старта. Cancellation наступает после наблюдаемого чанка.
  EOF и маршрут также сверяют точные длину/hash. Старые generic ASGI tests
  сохранены. Прогоны C2 включают все семь новых тестов.
- **Решение:** оба пробела обязательного ASGI-доказательства устранены; CLOSED.

## Полная проверка AC-001…AC-011

Рассмотрены весь исправляющий diff, неизменённый production path, миграция,
профильные артефакты C1 и новые C2 tests/evidence. Результаты команд ниже —
результаты исполнителя, а не новые запуски ревьюера.

| AC | Решение | Подтверждение |
| --- | --- | --- |
| AC-001 | PASS | Сохранены TestStoredBytes и сквозной upload/download PDF/JPEG/PNG: точные байты, MIME, безопасный Content-Disposition, отсутствие Content-Length; маршрут C2 дополнительно проверяет потоковый hash/total и заголовки. |
| AC-002 | PASS | Сохранены same_length/truncated/appended, неверный digest строки и ASGI mismatch с единственным start=500/точным JSON; helper сверяет digest до response, снимок не передаётся при ошибке. Нет изменения БД/blob и утечки байтов/ключа/пути/digest. |
| AC-003 | PASS | Сохранены missing blob, StorageError/OSError/PermissionError и 404 до storage; исправленный реальный is_file/open race закрывает MVP03-R2-001. Safe JSON и единственная category ERROR подтверждены. |
| AC-004 | PASS | Сохранены read после нескольких чанков, temp create/write/flush/seek и constructor failure, assertions source/temp.closed и безопасный 500; prepare происходит до response. |
| AC-005 | PASS | Пустой blob с верным/неверным hash, stale size 0/1/10 000 000; размер не используется для тела и не исправляется, Content-Length не вводится. Тесты не изменены. |
| AC-006 | PASS | Сохранены один storage.open, bounded reads/writes, запрет seek/fileno/stat исходника, tamper исходного inode и helper-only 1/100 MiB tracemalloc ≤8 MiB. Новый route-level observer проверяет фактические ASGI чанки ≤65536, total/hash без удержания body. |
| AC-007 | PASS | Сохранена проверка source.closed до response.start. Новые реальные disk-backed EOF/read/send/ASGI 2.0/2.4 disconnect/cancellation и маршрут проверяют snapshot.closed; late read error не даёт второго start/JSON. MVP03-R2-002 закрыт. |
| AC-008 | PASS | Неизменённый route: один параметризованный SELECT File по id/document_id без lock, без DML/flush/commit/rollback/history/status changes. SQL listener, Session spies и snapshots success/mismatch/read_failure/404 сохранены; C2 focused/full их включают. |
| AC-009 | PASS | Единственная revision e4b8c2d16a70 от a3f1c72d5b90, только create/drop индекса. Неизменённый PostgreSQL test выполняет up/down/up в уникальной schema с DATABASE_URL/PGOPTIONS, проверяет строки/constraints/catalog/version и public version/count. Test входит в C2 focused/full. |
| AC-010 | PASS | Сохранены metadata/Inspector/pg_catalog: один nonunique valid btree(document_id,id), без predicate/expression; list изолирует документ/сортирует, Core cascade сохраняет соседний документ; EXPLAIN с seq/bitmap off показывает нужный index scan без Sort. |
| AC-011 | PASS | На закреплённой ревизии ADR-009, ADR README, PROJECT_STATUS отражают SHA-256 до ответа, индекс e4b8c2d16a70 и закрытые ограничения 16/17; auth/authorization и ORM passive_deletes не объявлены выполненными. C2 не меняет эти документы или объём требований. |

## Evidence reuse

[C2 evidence](../evidence/TASK-MVP-03-C2.md) содержит baseline/final commit,
workspace/ветку, автора, дату, Task/Dispatch исполнителя, точные команды,
CWD, exit и достаточный содержательный inline-вывод. CWD всех команд —
`/mnt/d/Antigravity/EquipmentDocumentationRegistry` в WSL Ubuntu, внешний
CWD `D:\Antigravity\EquipmentDocumentationRegistry`.

| Команда исполнителя из evidence C2 | Exit / переиспользованный результат |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_files_download_api.py tests/test_files_integration_api.py tests/test_file.py tests/test_files_index_migration.py tests/test_storage.py tests/test_document_verification_event.py tests/test_document_variants_api.py` | 0; **372 passed, 1 warning in 57.70s**. |
| `.venv/bin/python -m pytest -q` | 0; **3530 passed, 1 warning in 467.62s**; 0 failed, прежний StarletteDeprecationWarning. |
| `.venv/bin/python -m pytest -q tests/test_files_download_api.py` | 0; **117 passed, 1 warning in 16.21s**, выполнено исполнителем после коммита. |
| `.venv/bin/python -m alembic heads` | 0; **e4b8c2d16a70 (head)**. |
| `ls alembic/versions/*.py \| wc -l` | 0; **13**. |
| `.venv/bin/python -m alembic current` | 0; **e4b8c2d16a70 (head)**. |
| `git diff --name-status 0587ccc..HEAD`; `git show --stat --oneline HEAD` | 0; один разрешённый файл, 398 additions / 10 deletions, 6827ed3. |
| `git diff --check 0587ccc..HEAD`; `git status --porcelain=v1 --untracked-files=all` | 0; diff без ошибок, посторонние изменения и незакоммиченные evidence отделены. |

Evidence связывает полный прогон до коммита с тем же содержимым файла,
закоммиченным без последующих правок; отдельный post-commit прогон 117 cases
явно отличён от full. Фактические git diff/HEAD и семь новых определений
согласуются с указанной ревизией и численными результатами. Сырые отдельные
логи не приложены; inline-результат допустим review-policy и не содержит
неоднозначности, требующей нового запуска.

Из C1 переиспользованы доказательства неизменённого production state,
локального `alembic upgrade head && current`, линейного predecessor, SQL trace,
bounded-memory и catalog/EXPLAIN/up-down-up. Сами тесты миграции/SQL/памяти
вновь включены исполнителем в C2 suites. Ошибочные утверждения C1 о полноте
AC-003/006/007 не переиспользуются: их заменяют новые C2 сценарии и closure
выше. Исторические счётчики C1 не выдаются за текущие C2.

**Reviewer rerun: 0.** Пробелов, для которых требовался бы разрешённый
однократный rerun, нет. Выполнены только чтение/поиск и git-сравнения;
backend/frontend suites, Alembic и запросы к БД ревьюером не запускались.

## Безопасность, новые findings и остаточные риски

Продуктовый код повторно просмотрен и совпадает с принятой в C1 частью
реализации. SHA-256 считается одновременно с копированием в приватный
TemporaryFile; ответ получает только эту копию после сравнения. Ошибки
подготовки дают безопасный 500 до response.start, поздняя ошибка чтения
прерывает уже начатый поток. В category logger.error нет digest/storage_key/
filename/байтов/str(error)/traceback/exc_info; безопасные имя класса и
идентификаторы не заменены содержимым ошибки. SQL остаётся параметризованным,
без новых блокировок и побочных записей. Тестовые secret-пути используются
только как failpoint и проверяются на отсутствие в журнале.

Миграция, metadata и schema isolation не изменены. Up/down/up, seed,
Core cascade и teardown направлены в disposable schema, public не является
целью этих операций. Snapshot public version/count — дополнительный контроль,
а не побайтовый аудит всех данных; сам ревьюер БД не изменял.

Новых findings нет. Открытых findings текущего TASK после C2 — **0**.
Сохраняются известные внеблокирующие ограничения C1, без расширения чек-листа:

- Исключение из самого source.close() не входит в перечисленные IO failpoints;
  оно может маскировать исходную ошибку. Этот крайний случай не исправлялся
  и отдельно не воспроизводился.
- Disk snapshot требует места и полного чтения до ответа; квоты и новые
  ограничения ресурсов не входят в TASK. Read failure в тесте — failpoint
  поверх настоящего файла, а не аппаратная ошибка диска.
- ASGI 2.0 проверяет наблюдаемый частичный streaming, без требования точного
  числа чанков до disconnect. Race-test проверяет файловую границу
  детерминированной инъекцией, а не вероятностной гонкой процессов.
- Исторические числовые снимки в ADR/PROJECT_STATUS (тесты, строки БД,
  контрольная точка C1) требуют отдельной актуализации; текущие C2 результаты
  находятся в evidence. Это не незакрытые требования AC-011 о SHA-256/индексе.
- Auth/authorization, ORM passive_deletes, Range/HEAD/ETag и удаление/расписание
  reconciliation остаются за пределами реализации этого TASK.

Это TASK-level PASS A1/C2 на `6827ed3`, не итоговая приёмка всего этапа.
Запись результата в очередь/STATE/HISTORY и дальнейшие действия принадлежат
координатору; ревьюер их не выполняет. Третье полное ревью A1 не назначается.
