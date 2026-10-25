# TASK-MVP-03 — независимое R2-ревью A1/C1

**Вердикт: FAIL.** Два открытых замечания MAJOR: обязательные сценарии
AC-003, AC-006 и AC-007 подтверждены не полностью. Это пробелы требуемого тестового
покрытия и соответствующих утверждений evidence; воспроизведённого нарушения
HTTP-контракта или целостности данных не установлено. Зелёные прогоны существующих
тестов не заменяют отсутствующие сценарии замороженного чек-листа.

## Идентификация и границы

- Дата ревью: 2026-10-25. Автор: независимый Codex-ревьюер R2.
- Логический TASK: TASK-MVP-03; подход A1, цикл C1; full review 1/2.
- По dispatch зарезервирован Codex call 2/4, лимит input 3 000 000 токенов.
  Точное провайдерское потребление этому ревьюеру не предоставлено; счётчики
  не изменялись и не сбрасывались.
- Review task `task_93712a9c9442`, dispatch `ctx_3f22c5d23a39`, terminal
  `term_5de79d4e-cbc7-4fd8-a73e-782a9b95fc51`, run `run_68046cea3eb4`.
- Workspace: `D:\Antigravity\EquipmentDocumentationRegistry`; ветка `main`.
- Проверяемая реализация:
  `40c6343a29ee553351aa3c96994061c3ede7b225`.
- Baseline: `db96b7a712c281c41bd69f6b000a1d94048f068f`;
  продуктовое состояние до TASK:
  `fde540677fa1dc5ecc3ff359bc1c989af6f4b26c`.
- Входы: [замороженный TASK](../../tasks/TASK-MVP-03.md),
  [evidence C1](../evidence/TASK-MVP-03-C1.md), фактический diff
  `db96b7a..40c6343`, `AGENTS.md`, правила routing-and-budget/review-policy
  skill `autonomous-development` и установленный guide `orca skills get orchestration`.
  Предыдущих findings нет.
- Фактический HEAD при чтении — `0587ccc4e96e0ac7c3b37fd196d5154e8540d3ed`.
  Между `40c6343` и этим HEAD изменены только TASK/STATE/HISTORY. Проверенные
  продуктовые файлы, тесты и миграция в workspace совпадают с `40c6343`.
  Посторонние локальные изменения ROADMAP, ADR README, APPROVALS, STATE и
  новый ADR-011 сохранены; они не входят в оцениваемый implementation diff.
- Ревьюер создал только этот отчёт. Код, тесты, миграции, evidence,
  STATE/HISTORY и очередь не изменены; коммитов и команд изменения БД нет.

## Фактический diff и allowlist

`git diff --name-status db96b7a..40c6343` содержит ровно 12 файлов,
`1531 insertions(+), 97 deletions(-)`:

| Файл | Проверка границ |
| --- | --- |
| `app/api/files/download.py` | Helper снимка и SHA-256, закрытие при ошибке конструктора response, безопасный late-read log. |
| `app/api/files/router.py` | Подготовка снимка до response, безопасные категории ошибок; остальные операции не изменены. |
| `app/models/file.py` | Только импорт/объявление Index; CHECK, FK, relationship сохранены. |
| `alembic/versions/e4b8c2d16a70_add_ix_files_document_id_id.py` | Единственная новая/изменённая миграция. |
| `tests/test_files_download_api.py` | Профильные проверки скачивания и IO/ASGI. |
| `tests/test_file.py` | Проверки metadata индекса. |
| `tests/test_files_index_migration.py` | PostgreSQL up/down/up, каталоги, list, cascade, EXPLAIN. |
| `tests/test_document_verification_event.py` | Только baseline count/head: 13 / `e4b8c2d16a70`. |
| `tests/test_document_variants_api.py` | Только count, имя и комментарий baseline-теста. |
| `docs/adr/ADR-009-document-attachments.md` | Статус сверки SHA-256 и индекса. |
| `docs/adr/README.md` | Статусные строки ADR-009. |
| `docs/PROJECT_STATUS.md` | Контрольная точка, статус SHA-256/индекса, закрытие ограничений 16/17. |

Unexpected files в оцениваемом diff отсутствуют. Запрещённые модули, старые
миграции, frontend, зависимости, `.env`, `.venv` и реальный storage в diff
не затронуты. Evidence и этот отчёт не входят в implementation commit.

## Проверка AC-001..AC-011

«Подтверждено» означает совместную статическую проверку кода/тестов и
переиспользование фактического результата из evidence, а не новый прогон ревьюером.

| AC | Решение | Код, тесты и оценка доказательства |
| --- | --- | --- |
| AC-001 | Подтверждено | `TestStoredBytes`, сквозной upload/download для PDF/JPEG/PNG; прежний безопасный `content_disposition()`, MIME из строки, отсутствие Content-Length. Router отдаёт только `verified`. |
| AC-002 | Подтверждено | `TestIntegrityCheck`: same_length/truncated/appended, неверный digest строки, ASGI capture с единственным start=500 и безопасным JSON. Helper сравнивает hash до возврата; снимок/исходник закрываются на mismatch. Тесты проверяют отсутствие blob/digest/ключа/пути в ответе или журнале и неизменность испорченного blob. |
| AC-003 | Частично; MAJOR | Missing blob и StorageError/OSError/PermissionError дают безопасный 500 и один category log; 404 отсекается до storage. Однако заявленный race между `is_file` и `open` тестируется удалением **до** `is_file`: MVP03-R2-001. |
| AC-004 | Подтверждено | `TestPreparationFailures`, `TestVerifiedSnapshot`: read после нескольких чанков; temp create/write/flush/seek; закрытие source/temp, безопасный JSON 500; отдельная ошибка кодирования заголовка в конструкторе закрывает переданный поток. Подготовка выполняется до создания response. |
| AC-005 | Подтверждено | `TestEmptyAndStaleSize`: пустой blob с верным/неверным digest; stale size 0/1/10 000 000. Размер не используется helper/router и не исправляется; Content-Length отсутствует. |
| AC-006 | Частично; MAJOR | Один storage.open, чтение по 65536, запись того же chunk; `RecordingStream` запрещает seek/fileno/stat исходника; tamper исходного inode не меняет снимок. Helper-only tracemalloc для 1/100 MiB ограничен 8 MiB. ASGI проверяет размер чанков, но накапливает всё тело вместо требуемого наблюдения без накопления: MVP03-R2-002. |
| AC-007 | Частично; MAJOR | Оригинал закрыт до response.start; generic ASGI release/late-error проверки есть. Реальная проверенная disk copy проверяется лишь при send/disconnect ASGI 2.4; обязательное покрытие disk copy для остальных выходов отсутствует: MVP03-R2-002. |
| AC-008 | Подтверждено | Router делает один `select(File).where(id, document_id)` без блокировки и без DML/flush/commit/rollback. `TestNoSideEffects` содержит SQL listener, commit/rollback spies, success/mismatch/read_failure/missing_row и снимки metadata/status/events/blob. Ни helper, ни итератор к Session не обращаются. |
| AC-009 | Подтверждено | Единственная revision `e4b8c2d16a70` от `a3f1c72d5b90`; upgrade только create_index, downgrade только drop_index. Migration-тест запускает child Alembic с DATABASE_URL/PGOPTIONS в уникальной schema, проверяет версии/строки/constraints/indexes на up/down/up, сравнивает public version/count; seed/cascade/teardown направлены в созданную schema. |
| AC-010 | Подтверждено | Metadata ровно один nonunique Index(document_id,id); Inspector/pg_catalog проверяют порядок, valid, btree, отсутствие predicate/expression. Проверены изоляция/сортировка списка и Core DELETE cascade с соседним документом. EXPLAIN в disposable schema требует нужный Index Scan/Index Only Scan без Sort при отключённых seq/bitmap scans. Неизменённый FileService имеет тот же WHERE/ORDER BY. |
| AC-011 | Подтверждено в объёме TASK | ADR-009, ADR README и PROJECT_STATUS согласованно заявляют SHA-256 до ответа и индекс `e4b8c2d16a70`, ограничения 16/17 закрыты. Аутентификация/авторизация остаются невыполненными, ORM passive_deletes не объявлен исправленным. Устаревшие вспомогательные снимки числа тестов/строк БД перечислены ниже вне основания FAIL. |

## Evidence reuse и фактические проверки

Evidence идентифицирует implementation/baseline, автора, дату, workspace, ветку,
Run/Task/Dispatch и C1. Для обязательных команд приведены команда, CWD (корень
репозитория в WSL Ubuntu), exit и содержательный inline-результат; отдельные
сырые логи не приложены, но допускаемого review-policy inline-вывода достаточно
для переиспользования результатов этих команд. Это результаты исполнителя,
независимого прогона этих команд ревьюером не было.

| Evidence check | Переиспользованный результат |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_files_download_api.py tests/test_files_integration_api.py tests/test_file.py tests/test_files_index_migration.py tests/test_storage.py tests/test_document_verification_event.py tests/test_document_variants_api.py` | exit 0; 365 passed, 1 warning, 62.25s. |
| `.venv/bin/python -m pytest -q` | exit 0; 3523 passed, 1 warning, 518.03s; прежний StarletteDeprecationWarning. |
| `.venv/bin/python -m alembic heads` | exit 0; единственный `e4b8c2d16a70 (head)`. |
| `.venv/bin/python -m alembic upgrade head && .venv/bin/python -m alembic current` | exit 0; уже применённая миграция, current=`e4b8c2d16a70 (head)`. |
| `ls alembic/versions/*.py \| wc -l` | exit 0; 13. |
| Дополнительный targeted pytest (#6 evidence; точная длинная команда сохранена там) | exit 0; 19 passed, 1 warning, 20.60s; SQL/ASGI/release/memory/migration tests. |
| `git diff --check`; implementation log/stat | exit 0; чистый diff, один implementation commit `40c6343`, 12 разрешённых файлов. |
| `.venv/bin/python -m alembic history -r a3f1c72d5b90:e4b8c2d16a70` | exit 0; один переход к `e4b8c2d16a70`. |

Статически проверены тела тестов, а не только имена из evidence. Поэтому зелёные
результаты выше приняты как результаты **существующих** тестов, но утверждения
evidence «AC-003/AC-006/AC-007 выполнено» ограничены двумя findings ниже. Повторные
прогоны не выполнялись: отсутствующий сценарий не появляется от повторного
запуска той же команды. Исключений из evidence-reuse rule и reviewer rerun нет.

Read-only команды ревьюера (`git status/branch/log/rev-parse`, pinned git diff,
чтение файлов/поиск и сравнение проверяемых файлов с `40c6343`) завершились без
ошибок. Начальное состояние workspace с посторонними правками отделено от
оцениваемого diff; историческая строка evidence «после evidence только ??» не
используется как описание сегодняшнего workspace.

## Findings

### MVP03-R2-001 — тест не достигает границы is_file/open

- **AC:** AC-003; **severity:** MAJOR; **closure:** OPEN.
- **Location:** `tests/test_files_download_api.py:737` (особенно 740–743, 757);
  неизменённый `app/services/local_storage.py:107`;
  `docs/workflow/evidence/TASK-MVP-03-C1.md:58`.
- **Observed/repro:** тело `VanishingStorage.open()` сначала выполняет
  `unlink()`, затем вызывает `super().open()`. Следовательно,
  `LocalStorageBackend.open()` видит отсутствующий файл уже на `is_file()` и
  выбрасывает `StoredFileNotFoundError`; именно его требует assertion на 757.
  Это второй вариант missing-blob теста. Успешный `is_file()` с последующим
  исчезновением перед `Path.open('rb')` здесь не воспроизводится. Статическое
  чтение порядка вызовов достаточно; новый прогон результата не изменит.
- **Expectation:** замороженный AC-003 отдельно требует исчезновение между
  `is_file`/`open` на реальном tmp blob. Нужна контролируемая инъекция на этой
  границе, оставляющая настоящий backend.open, с безопасным 500, отсутствием
  байтов/секретов и единственной `content_open_failed` записью для ошибки
  фактического открытия. Имеющиеся generic OSError-инъекции не исполняют эту
  границу LocalStorageBackend.
- **Closure evidence:** тест действительно доходит до успешного is_file,
  удаляет tmp blob до физического open и подтверждает требуемые response/log
  assertions; результаты для исправленной ревизии и честное описание сценария
  в evidence. Runtime-дефект catch-блока этим finding не заявляется.

### MVP03-R2-002 — ASGI-проверки не полностью реализуют замороженные условия

- **AC:** AC-006, AC-007; **severity:** MAJOR; **closure:** OPEN.
- **Location:** `tests/test_files_download_api.py:451`, `:1618`, `:1632`, `:1676`,
  `:1690`, `:1777`, `:1812`;
  `docs/workflow/evidence/TASK-MVP-03-C1.md:62`.
- **Observed/repro:** TestStreamRelease передаёт в ClosingStreamingResponse
  `RecordingStream`/`BrokenStream` поверх BytesIO. ASGI 2.0 сразу возвращает
  disconnect; cancellation и late-read-error также работают с памятью.
  Единственный отдельный тест с результатом prepare_verified_download и
  проверкой реального `snapshot.closed` — `:1812`, send error ASGI 2.4.
  HTTP EOF выдаёт верные байты, но не сохраняет disk snapshot для assertion
  закрытия. Ни ASGI 2.0, ни cancellation, ни поздняя ошибка чтения проверенного
  дискового снимка обязательным способом не подтверждены. Для AC-006
  `test_a_verified_download_starts_after_the_original_is_closed` использует
  run_asgi, который сохраняет каждый body message в списке, а затем строит
  chunks и объединённое тело. Это небольшой фиксированный fixture и не
  доказательство утечки памяти продукта, но заданный ASGI send без накопления
  body отсутствует; helper-only tracemalloc проверяет другой участок.
- **Expectation:** замороженный AC-007 явно задаёт прямые ASGI TestStreamRelease
  с проверенной disk copy. Нужны те же выходы с реальным результатом helper,
  при необходимости с failpoint-обёрткой чтения, закрывающей настоящий файл;
  assert закрытия снимка и единственного start/отсутствия JSON после start.
  Для ASGI 2.0 нужен наблюдаемый streaming/disconnect сценарий с этим снимком.
  Для AC-006 нужен send-наблюдатель с подсчётом длины чанков/общей длины и
  потоковым hash, не сохраняющий все body bytes.
- **Closure evidence:** disk-backed ASGI tests на обязательные EOF/read failure/
  send failure/2.0 и 2.4 disconnect/cancellation, с closure assertions и
  evidence для исправленной ревизии, а также ASGI-наблюдение чанков без
  накопления тела. Существующие generic tests полезны и
  остаются принятыми, но не являются всем замороженным доказательством.
  Фактическая утечка дескриптора в этих сценариях не заявляется.

## Безопасность, миграция и остаточные риски

В изменённых error-path logger.error используются фиксированные сообщения,
идентификаторы, failure_category и имя класса ошибки. Нет digest/storage_key/
filename/содержимого, str/repr(error), traceback или exc_info. Существующий
JsonLinesFormatter не добавляет exception text. Подготовительные ошибки
превращаются в HTTPException до создания response; late read error логируется
без второго статуса/JSON. Success передаёт только приватный TemporaryFile,
исходник закрывается до старта, тело ограничено чанками. SELECT параметризован;
новых DML/lock/transaction/history действий endpoint не вводит.

Миграция сама содержит только create/drop одного nonunique btree. В up/down/up
тесте уникальный schema identifier генерируется через UUID, SQL-параметры
используются для данных, DATABASE_URL не печатается, PGOPTIONS фиксирует test
schema без public fallback. Public snapshot проверяет version/count, а
статический путь seed/cascade/drop направлен в test schema. Это подтверждает
изоляцию теста; snapshot version/count сам по себе не является побайтовым
аудитом всей public. Дополнительный public EXPLAIN/ANALYZE из evidence не
подменяет изолированный migration-тест; локальный upgrade head — отдельное
разрешённое требование TASK, не часть up/down/up в public.

Остаточные ограничения вне основания текущего FAIL:

- Обработка исключений из самого `source.close()` не входит в перечисленные
  IO failpoints; finally может заменить исходное исключение, а на успешной
  ветке исключение close произойдёт после выбора return snapshot. Этот
  отмеченный evidence крайний случай отдельно не воспроизводился.
- Приватный дисковый снимок добавляет временное место и задержку полного
  чтения до ответа; новые квоты/лимиты не входят в TASK.
- В ADR-009 остались исторические «76 тестов» и «строк: 0»; evidence сообщает
  110 собранных тестов и 3 ранее существовавшие строки public.files. PROJECT_STATUS
  также содержит исторический снимок пустой БД. Это предложения к отдельному
  обновлению снимков, не новые блокирующие требования AC-011.
- Auth/authorization, ORM passive_deletes, Range/HEAD/ETag и расписание/удаление
  reconciliation не реализованы этим TASK и не заявляются выполненными.

Решение относится только к A1/C1 на `40c6343`. Исправления и повторную приёмку
в пределах оставшегося бюджета назначает координатор; данное ревью не запускает
следующий TASK и не изменяет состояние очереди.
