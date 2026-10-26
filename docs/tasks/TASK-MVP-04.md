# TASK-MVP-04 — BatchService и Batch API

Статус: PASS (независимая Astra R2 завершена; ALL3771 passed; delivery0db1f9e). Требования:
VISION.md, ARCHITECTURE.md, ROADMAP.md, ADR-005, ADR-006, ADR-010. Этап
ROADMAP: 5.
Актуализация 2026-10-26: пользователь отозвал Nemotron-маршрут и прекратил
TASK-WF-01. Исторические сведения о маршрутизации ниже описывают только
исполнение этого TASK; текущая политика Codex — `../workflow/MODEL-ROUTING.md`.
Предшественники с обязательным PASS: TASK-MVP-03 PASS.
Класс риска: R2 (публичный HTTP-контракт, валидация Decimal/date, FK и
транзакционная семантика, OpenAPI).
Маршрут приёмки: Codex-ревьюер. Design: Codex, `task_89004862c3a1` /
`ctx_79b98b623026`; memo `msg_b797e4633a0b`, `msg_53201f873a18`; проектный PASS
дизайном не присваивается.

## Цель и область

Реализовать вертикальный срез `Batch` по образцу справочников: Pydantic-схемы,
`BatchService`, HTTP CRUD без удаления, профильные тесты, OpenAPI и статусные
документы. Существующая ORM-модель и таблица `batches` переиспользуются; новых
миграций, индексов и CHECK-ограничений нет.

В область входят ровно четыре операции:

- `POST /batches` — создание партии, `201`, `Location`;
- `GET /batches/{batch_id}` — чтение, `200`;
- `GET /batches` — глобальный список `id ASC` с `limit`/`offset`, `200`;
- `PATCH /batches/{batch_id}` — частичное изменение, `200`.

`DELETE`/`PUT`, уникальность `batch_number`, `409`, фронтенд, поиск/фильтры,
bulk/import/export, справочник единиц, привязка документа к партии/изделию,
изменение поиска документов, lifecycle/history/auth/deployment и исправление
SDR-ограничения `Product` не входят.

Целевые компоненты: `app/api/batches/`, новый `app/services/batch_service.py`,
подключение в `app/api/router.py`, четыре новых тестовых модуля и
`docs/PROJECT_STATUS.md`.

## Design-решения (приняты Codex)

### Схемы

- `BatchCreate` и `BatchUpdate`: `ConfigDict(extra="forbid")`; принимаются только
  `variant_id`, `batch_number`, `manufacture_date`, `quantity`, `quantity_unit`.
  `id`, `product_id`, `sdr`, `document_ids`, `variant`, `documents` и любые другие
  ключи дают `422`.
- `VariantId = Annotated[int, BeforeValidator(_reject_bool), Field(gt=0)]` по
  правилам `ProductId` из среза вариантов. В `BatchCreate` поле обязательно;
  `null`, `bool`, `0`, отрицательное и дробное значение отклоняются. Стандартное
  приведение `"1"` и `1.0` к `1` сохраняется. Наличие `ProductVariant` проверяет
  сервис.
- В `BatchUpdate` поле `variant_id` имеет вид `VariantId | None = None`; валидатор
  запрещает явный `null`, отсутствие поля разрешено. `PATCH` использует
  `model_dump(exclude_unset=True)` без `exclude_none`: отсутствующее поле
  сохраняется, явный `null` очищает любое из четырёх nullable-полей, `{}`
  допустим. Смена `variant_id` на вариант другого `Product` разрешена: меняется
  FK партии, а не `product_id` варианта.
- `batch_number`: `Annotated[str, StringConstraints(strip_whitespace=True,
  min_length=1, max_length=100)] | None = None`.
- `quantity_unit`: тот же строковый тип с `max_length=30`; также nullable.
  Внешние Unicode-пробелы удаляются до проверки длины; регистр и внутренние
  пробелы сохраняются; пустая/пробельная строка отклоняется. Словаря единиц,
  конверсии и требования заполнять `quantity` и `quantity_unit` вместе нет.
- `quantity`: публичный alias `Measurement` из `app/api/variants/schemas.py` как
  `Quantity`, без импорта приватного валидатора и без рефакторинга вариантов.
  Допустим `Decimal | None`: finite, `> 0`, `<= Decimal("99999999.99")`,
  exponent `>= -2`. Принимаются `Decimal`, числовые JSON-значения и числовые
  строки; `bool`, `NaN`/`Infinity`, `0`/`-0`, отрицательные, переполнение и
  более двух дробных знаков отклоняются. Не округлять, не quantize и не
  использовать `float` в сервисе. `'1.000'` отклоняется; для точного ввода
  клиент использует строку, поскольку JSON number `1.000` может стать `1.0`.
- `manufacture_date`: `date | None = None` с обычными Pydantic-преобразованиями,
  как у `issue_date`: ISO `YYYY-MM-DD`, `datetime`/ISO datetime ровно на полночь
  и timestamp соответствующей целой даты допустимы; `bool`, пустая строка,
  невозможная дата и datetime с ненулевым временем отклоняются. Ограничения «не
  позже сегодня» нет; будущая корректная дата допустима.
- `BatchRead`: `ConfigDict(from_attributes=True)`, ровно шесть полей: `id: int`,
  `variant_id: int`, `batch_number: str | None = None`,
  `manufacture_date: date | None = None`, `quantity: Decimal | None = None`,
  `quantity_unit: str | None = None`. Write-валидаторы к прочитанным данным не
  применяются, отношения не включаются. Все шесть ключей присутствуют в ответе,
  включая `null`; дата сериализуется ISO, `Decimal` — JSON-строкой. После
  `refresh` PostgreSQL `NUMERIC(10,2)` возвращает `5.00` для входа `5`.

### Сервис

- `app/services/batch_service.py`: `BatchService` со `staticmethod`:
  `create(db, data) -> Batch`, `get_by_id(db, batch_id) -> Batch | None`,
  `list(db, limit=DEFAULT_LIMIT, offset=0) -> list[Batch]`,
  `update(db, batch_id, data) -> Batch | None`. `DEFAULT_LIMIT = 50`; `delete`
  отсутствует. Сервис не импортирует FastAPI и не открывает/закрывает `Session`.
- `BatchServiceError(Exception)`; `VariantNotFoundError(BatchServiceError)` с
  атрибутом `variant_id`. `_require_variant` использует
  `ProductVariantService.get_by_id` и поднимает ошибку, если вариант не найден.
- `create`: сначала `_require_variant`, затем `Batch(**data.model_dump())`, `add`,
  ровно один commit, `refresh`, возврат. `get_by_id`: `db.get`.
- `list`: `select(Batch).order_by(Batch.id.asc()).limit(limit).offset(offset)`;
  глобальный список без `variant_id`-фильтра, join, total и envelope. Пустая БД и
  offset за концом дают `[]`; limit/offset выполняются в SQL.
- `update`: сначала получить `Batch`; если строки нет, вернуть `None` независимо
  от нового `variant_id`. Затем `exclude_unset=True`; `{}` возвращает текущий
  объект без commit. Если `variant_id` передан, проверить его до любого
  `setattr`. Применить все поля, один commit с итоговым `variant_id`, `refresh`.
  Непустой `PATCH` коммитит один раз даже при совпадении значений; ошибочный
  новый FK не должен оставлять объект dirty или менять другие поля.
- `_commit`: `try db.commit()`; при `SQLAlchemyError` — `db.rollback()`, затем
  только конкретный FK классифицируется как `VariantNotFoundError`; остальные
  ошибки повторно поднимаются. Никаких retry и второго commit.
  `_is_variant_fk_violation` проверяет одновременно `orig.sqlstate == "23503"`,
  `orig.diag.constraint_name == "batches_variant_id_fkey"` и
  `orig.diag.table_name == "batches"`. Другие FK, `NOT NULL`, `CHECK`, PK/UNIQUE
  не маскируются как неизвестный вариант и не переводятся в `409`.
- Чтение, пустой `PATCH`, неизвестный `Batch` и precheck неизвестного варианта не
  коммитят. Precheck выполняется до изменений; отдельный rollback для обычного
  «не найдено» не нужен. Ошибка записи откатывает весь `PATCH` и делает сессию
  пригодной. Новые transaction guards, `FOR UPDATE`, UoW, savepoint и изменения
  `transaction.py` не вводятся.
- У `Batch` нет бизнес-уникальности: одинаковые партии, одинаковые номера у
  разных вариантов и несколько `null`-номеров допустимы; POST дубля создаёт новую
  строку, PATCH на совпадающие значения допустим. `BatchAlreadyExistsError` и
  unique-precheck отсутствуют.

### Router

- `batch_router = APIRouter(prefix="/batches", tags=["batches"])`; подключить
  через `api_router.include_router(batch_router)` в `app/api/router.py`; создать
  пустой `app/api/batches/__init__.py`.
- `POST ""` — `create_batch`, `201`, `BatchCreate -> BatchRead`,
  `summary="Create a batch"`; после успеха
  `Location=str(request.url_for("get_batch", batch_id=batch.id))`.
- `GET "/{batch_id}"` — `get_batch`, `200`, `summary="Get a batch by id"`.
- `GET ""` — `list_batches`, `200`, `list[BatchRead]`, `summary="List batches"`;
  `limit: Query(ge=1, le=100)=50`, `offset: Query(ge=0)=0`.
- `PATCH "/{batch_id}"` — `update_batch`, `200`, `summary="Update a batch"`.
- `batch_id: int` в path; некорректный int — `422`, несуществующие целые
  (включая `0` и отрицательные) — `404`. Вложенные маршруты и `PUT`/`DELETE` не
  добавляются; `DELETE` существующей карточки — стандартный `405`, строка
  сохраняется.
- Router только вызывает сервис, преобразует `BatchRead.model_validate` и
  `HTTPException`; SQL/commit/rollback в нём нет. `None` из get/update — `404`
  `{"detail":"Batch <id> not found"}`. `VariantNotFoundError` из POST/PATCH —
  `404` `{"detail":"Variant <id> not found"}`. Неверное тело/path/query —
  стандартный `422` до сервиса. При неизвестных Batch и Variant приоритет у
  Batch 404; при неверном теле — у `422`. Неожиданные ошибки — стандартный
  безопасный `500` при `debug=False`, без текста исключения/SQL. `Location`
  отсутствует при ошибках и PATCH.
- OpenAPI следует issuer-конвенции: без `responses=` для бизнес-ошибок. POST
  декларирует `201`/`422`; остальные три операции — `200`/`422`; runtime `404` и
  `405` проверяются HTTP-тестами. Четыре уникальных `operationId`, обязательные
  `tags` и непустые `summaries`. Два path, четыре операции, схемы
  `BatchCreate`/`BatchUpdate`/`BatchRead`, обязательный body, только
  `variant_id` обязателен в Create, Update без required-полей,
  `additionalProperties: false` у входных моделей, `date` format, nullable-поля и
  строковый `Decimal` в выходе.

### Тесты

- Создать `tests/test_batch_schemas.py`: `TestBatchCreate`, `TestBatchUpdate`,
  `TestBatchRead`; required/missing/null `variant_id`; bool/дробные/
  неположительные id; обе границы 100/101 и 30/31 после trim; Unicode-пробелы,
  пустые строки, внутренние пробелы/регистр; unknown fields; nullable и
  `exclude_unset`/`model_fields_set`; quantity `0.01`, `99999999.99`,
  overflow, `-0`/`0`, NaN/Infinity, bool, `1.005`/`1.000`, числа/строки/
  `Decimal`; date, leap day, невозможная дата, future date, midnight datetime,
  timestamp 0; ORM->Read, шесть полей, ISO-дата и строковый `Decimal`; чтение не
  повторяет write-валидацию.
- Создать `tests/test_batch_service.py`: `TestCreate`, `TestGetAndList`,
  `TestUpdate`, `TestTransactionsAndErrors`. Настоящий PostgreSQL round-trip с
  `expire_all` либо отдельной `Session`; минимальная/полная запись; Decimal scale
  после refresh; смена варианта, включая другой `Product`; все четыре
  null-очистки и сохранение отсутствующих полей; другие строки/таблицы не
  меняются; неизвестный Batch, пустой PATCH, неизвестный variant без изменений;
  `id ASC` с номерами в обратном алфавитном порядке, default limit 50 на >50
  строках, limit/offset и `[]` за концом. Одинаковые записи сохраняются
  раздельно, несколько `null`-номеров допустимы, PATCH на дубль допустим.
- `TestTransactionsAndErrors`: commit-spy вызывает настоящий original commit;
  считать после подготовки фикстур. Create/nonempty PATCH — ровно 1;
  read/`{}`/not-found/precheck — 0. Настоящий FK failure на commit через сервис с
  временным пропуском `_require_variant`; проверить rollback и сохранность старых
  полей при PATCH, отсутствие новой строки при POST, работоспособность сессии
  после отказа. Для `_is_variant_fk_violation` подавать настоящие ошибки
  PostgreSQL: свой FK распознаётся, чужой FK/UNIQUE/NOT NULL — нет. Остальные
  `SQLAlchemyError` не получают доменную классификацию и не вызывают
  retry/второй commit.
- Создать `tests/test_batches_api.py`: `TestBatchEndpoints`, `TestBatchValidation`,
  `TestBatchErrors`, `TestBatchFixtures`. POST->Location->GET, list и PATCH с
  сохранением в БД; шесть полей, null, ISO-date, quantity строкой с двумя
  знаками; перенос `variant_id`, очищение, `{}` без commit; 404 Batch/Variant,
  приоритеты ошибок, 422 invalid body/path/query, 405 DELETE/PUT без изменений,
  дубли -> 201; безопасный 500 через
  `TestClient(raise_server_exceptions=False)` на неожиданной ошибке; Location
  только при успехе POST. `limit` 1/100, default 50, offset 0, плохие
  limit 0/101/negative и offset negative, fractional/noninteger -> 422;
  неизвестный query, как в справочниках, игнорируется. Ошибки валидации не
  меняют БД.
- Создать `tests/test_batches_openapi.py`: `TestBatchesOpenApi` без подключения к
  БД/lifespan. Проверить ровно четыре новые операции под `/batches` и
  `/batches/{batch_id}`, tags/summaries/operationId, response/request refs,
  статусы, required body/`variant_id`, Update optional fields,
  `additionalProperties:false`, nullable, date format, request quantity
  `number|string|null` и response quantity `string|null`. Нет delete/put,
  вложенных batch routes и нового API документных привязок; прежние
  issuer/variant пути остаются.
- `tests/test_batch.py` включить в focused run без изменений: он уже проверяет
  существующую таблицу, nullable, FK, отсутствие UNIQUE(`batch_number`) и
  ORM-связи. Не создавать migration test и не менять модель ради тестов.
- Переиспользовать `tests/conftest.py::engine/db`: настоящий PostgreSQL и
  временная схема с teardown. Никакого SQLite и подмены Session для happy path.
  Не запускать xdist/параллельные pytest-процессы: имя scratch-схемы фиксировано.
  Локальные manufacturer/product/variant/make_batch фикстуры разместить в новых
  модулях; существующий `conftest.py` не менять.
- API fixture сохраняет прежний `get_db` override, заменяет его только тестовой
  `Session` и восстанавливает в `finally`, не очищая весь
  `dependency_overrides`. В `TestBatchFixtures` проверить восстановление
  отсутствующего/существовавшего override и чужих overrides, в том числе после
  исключения. Для логов/storage использовать `tmp_path` и временные `Settings`;
  lifespan в `app/main.py` вызывает `get_settings` напрямую, поэтому одного
  `dependency_overrides[get_settings]` недостаточно: monkeypatch
  `app.main.get_settings` на тестовые `Settings` с временными
  `LOG_FILE`/`STORAGE_ROOT`. Откат monkeypatch после выхода из `TestClient`.
  `.env`, `storage/` и рабочие данные не менять.

## Разрешённые файлы

Создать: `app/api/batches/__init__.py` (пустой), `app/api/batches/schemas.py`,
`app/api/batches/router.py`, `app/services/batch_service.py`,
`tests/test_batch_schemas.py`, `tests/test_batch_service.py`,
`tests/test_batches_api.py`, `tests/test_batches_openapi.py`,
`docs/workflow/evidence/TASK-MVP-04-C1.md` (не коммитить).
Изменить: `app/api/router.py` (только импорт и `include_router`), `docs/PROJECT_STATUS.md`
(только фактический статус, счётчики/проверки и ограничения `Batch`).
Читать без изменений: `tests/test_batch.py`, `tests/conftest.py`, `app/models/**`,
`alembic/**`, существующие issuer/variant срезы.

Не затрагивать: модели, миграции, зависимости, `app/config.py`,
`app/dependencies.py`, `app/logging_config.py`, `app/main.py`, `app/services/**`
кроме нового `batch_service.py`, `app/api/**` кроме двух указанных файлов/нового
пакета, frontend, `.env`, `.venv/`, реальный `storage/`, workflow-документы
координатора. Любая необходимость нового ADR/архитектурного изменения означает
остановку и отчёт координатору до реализации.

В `PROJECT_STATUS.md` убрать утверждения об отсутствии Batch schemas/service/API
во всех статусных упоминаниях, снять ограничение ORM-only, перечислить четыре
операции и оставшиеся non-goals, обновить фактическое число HTTP-операций и
результат ALL. Не переписывать архитектуру, ADR и историю чужих задач.

## Критерии приёмки

Чек-лист заморожен координатором до диспатча. Ревьюер проверяет строго по нему.

| ID | Критерий | Способ независимой проверки | Severity |
| --- | --- | --- | --- |
| AC-001 | `BatchCreate`/`BatchUpdate`/`BatchRead` имеют ровно указанные поля; Create требует `variant_id`; Update различает отсутствующий FK и запрещённый `null`; extra запрещён; Read.from_attributes и шесть ключей. | `TestBatchCreate/Update/Read`; S, покрыто F. | BLOCKER |
| AC-002 | Общие правила trim/длины/blank, допустимость и очистка nullable-полей, отсутствие кросс-обязательности quantity/unit; date без ограничения сегодняшним днём и со стандартными Pydantic coercions. | Параметризованные схемные кейсы и HTTP round-trip/очистка; S+H, покрыто F. | BLOCKER |
| AC-003 | Decimal end-to-end: finite/positive/scale/bound, без округления; PostgreSQL scale и JSON string. | Схемные границы и real-DB quantity round-trip; S+V+H, покрыто F. | BLOCKER |
| AC-004 | `BatchService.create/get_by_id/list/update` и отсутствие delete; неизвестный Batch -> None; неизвестный variant -> VariantNotFoundError с id; успешная смена FK и отказ до применения остальных изменений. | `TestCreate/GetAndList/Update` и приоритет неизвестного Batch; V. | BLOCKER |
| AC-005 | Сервис владеет commit: successful create/nonempty PATCH один раз, read/empty PATCH/not-found/precheck ноль; ошибка записи rollback, атомарность и reusable Session; только свой FK классифицируется, прочие DB-ошибки повторно поднимаются. | `TestTransactionsAndErrors` с настоящим commit/PostgreSQL; V. | BLOCKER |
| AC-006 | Глобальный SQL-list, `id ASC`, limit/offset, default 50, `[]` за концом; одинаковые batch_number и полные дубли разрешены без 409, несколько null. | `TestGetAndList/Create/Update` и HTTP список/дубли; V+H. | BLOCKER |
| AC-007 | Четыре HTTP-операции подключены в `app/api/router.py`; POST 201 + абсолютный followable Location, GET/list/PATCH 200 с BatchRead; PATCH `{}` возвращает прежнюю запись; DELETE/PUT 405 сохраняют строку. | `TestBatchEndpoints`; H; просмотр тонкого router diff. | BLOCKER |
| AC-008 | Ошибки 404 Batch/Variant, 422 body/path/query, явный `variant_id:null` и extra; приоритеты 422/Batch404/Variant404; безопасный unexpected 500, отсутствие Location при ошибках и частичного сохранения. | `TestBatchValidation/Errors`; H. | BLOCKER |
| AC-009 | OpenAPI: два path/четыре операции, tags/summaries, уникальные operationId, schema/response refs и статусы по issuer-конвенции; write extra forbidden, nullable/date/Decimal, никаких DELETE/PUT и document-batch linking. | `TestBatchesOpenApi`; O. | BLOCKER |
| AC-010 | F и ALL проходят на конечном состоянии, прежние тесты не ослаблены; diff укладывается в allowlist, model/migrations/dependencies/frontend не менялись; `docs/PROJECT_STATUS.md` отражает только подтверждённый статус/ограничения. | Логи F/ALL и G, просмотр всех новых файлов и docs diff; заранее существовавшие изменения координатора вычитаются по стартовому snapshot; фактический test count берётся из ALL. | MAJOR |

## Команды проверок

Все команды — из `D:\Antigravity\EquipmentDocumentationRegistry`; PostgreSQL 18
online; последовательно, без xdist. S/V/H/O — отдельные группы; F включает их и
обязателен; перед приёмкой достаточно одного F и одного ALL на конечном
состоянии.

| Команда | Ожидаемый результат |
| --- | --- |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch_schemas.py'` | S: exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch_service.py tests/test_batch.py'` | V: exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batches_api.py'` | H: exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batches_openapi.py'` | O: exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch.py tests/test_batch_schemas.py tests/test_batch_service.py tests/test_batches_api.py tests/test_batches_openapi.py tests/test_issuer_schemas.py tests/test_issuer_service.py tests/test_issuers_api.py tests/test_variant_schemas.py tests/test_variant_service.py tests/test_variants_api.py'` | F: exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | ALL: exit 0, 0 failed; фактический count в evidence |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic heads'` | ровно `e4b8c2d16a70 (head)` |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | `13` |
| `git status --short`; `git diff --check`; `git diff --name-only a405968401eefe6bcbbc2ca3302d14072eb63509`; `git ls-files --others --exclude-standard`; `git diff -- docs/PROJECT_STATUS.md`; `git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- app/models alembic` | только allowlist; отсутствие изменений model/migrations; evidence untracked |

Миграций в TASK нет; `alembic upgrade/downgrade/autogenerate` и новый migration
test не нужны. Сохранить baseline `e4b8c2d16a70` / 13 ревизий. Frontend checks
не требуются, frontend не меняется.

## Риски и non-goals

- PostgreSQL без CHECK позволяет обходить API-валидацию прямыми SQL; модель и
  миграция не меняются.
- До Pydantic JSON parser может потерять лексические нули/точность numeric input;
  для точного ввода количества клиент использует строку. Read сознательно
  отражает существующее хранение.
- FK остаётся окончательным барьером после precheck; classifier узкий, без
  анализа текста SQL.
- Простые PATCH имеют семантику справочников без optimistic locking/версий, а
  offset pagination не является snapshot при конкурентных вставках.
- Смена `batch.variant_id` не переписывает документы или их привязки и не создаёт
  историю/verification events.
- Отдельная чистая Session обязательна для изоляции посторонних изменений.
- Non-goals: DELETE/PUT, uniqueness/409, новые таблицы/индексы/CHECK/миграции,
  Batch frontend/Vite proxy, поиск и фильтры партий, bulk/import/export, единицы
  как справочник и конверсия, документ-партия/документ-изделие API, изменение
  поиска документов, lifecycle/history/auth/deployment, исправление известного
  SDR-ограничения Product. ADR-005/006 сохраняются; ADR-010 не расширяется.

## Приёмка по выбранному маршруту

Реализацию выполняет отдельный Codex-исполнитель (`gpt-6.1-sol` / medium по
разрешению CODEX_NEMOTRON_20261026), затем независимый Codex-ревьюер R2
(`gpt-6-astra` / high) проверяет
AC-001…AC-010 по этому чек-листу. Исполнитель коммитит только allowlist в
`main`, evidence C1 не коммитит; push/merge/deploy и следующий TASK запрещены.
Design: `task_89004862c3a1` / `ctx_79b98b623026`, memo
`msg_b797e4633a0b`, `msg_53201f873a18`; design PASS не присвоен. Сводка и
счётчики: `../workflow/STATE.md`. История: `../workflow/HISTORY.md`.

Ограниченное исключение пользователя действует до 2026-10-27 00:00
Europe/Moscow. Реализация возможна только после WF-01 acceptance; повторное
подтверждение старта не требуется. Фактическое исчерпание провайдера
останавливает цепочку и требует нового решения даже после reset. Функциональные
AC и allowlist неизменны; глобальные модели/аккаунты, операции с кредитами,
push/merge/deploy не разрешены.

## Актуальное исключение CODEX_COORD_20261026

Новое явное решение пользователя 2026-10-26 передаёт очередь Codex-координатору;
Nemotron больше не управляет очередью. MVP-04 разрешён при BLOCKED WF-01.
Этот раздел имеет приоритет над предыдущими ролевыми ограничениями и требованием
WF-01 PASS перед продуктовым dispatch. Codex ведёт workflow/ожидание; отдельный
gpt-6.1-sol medium реализует MVP-04 по готовому design, независимый
gpt-6-astra high проводит R2 review. Полный маршрут и точная цитата:
docs/workflow/MODEL-ROUTING.md и docs/workflow/APPROVALS.md.
AC, allowlist, архитектура, срок сегодняшнего исключения и весь расход сохранены.
WF-01 BLOCKED/NOT_ACCEPTED, 3/4 calls, 1/2 reviews; его исправление не запускается.
Commit только после routed PASS. Push/merge/deploy/reset/account changes запрещены.

## Утверждённая поправка MVP04_OPENAPI_COUNTERS_20261026

Пользователь ответил «Разрешаю» на точечное расширение allowlist после
ALL7 failed/3764 passed. Дополнительно разрешено менять только глобальные
OpenAPI totals19→21 paths/34→38 operations в:
tests/test_document_variants_api.py,
tests/test_documents_integration_api.py,
tests/test_documents_search_api.py,
tests/test_files_api.py,
tests/test_files_delete_api.py,
tests/test_files_download_api.py,
tests/test_files_upload_api.py.
Два test names с прежними числами обновить соответственно. Другие assertions
и поведение не менять. AC-010 сохраняется, это явное расширение allowlist
пользователем; функциональный контракт не расширяется.
Исполнитель Sol medium continuation call3/4, отдельный Astra high call4/4.
Старый failed ALL сохранить; повторить ALL на новом конечном состоянии,
F1094 и S/V/H/O переиспользовать, если их код не менялся.

MVP04_INPUT_12M_20261026: явное решение пользователя увеличивает input ceiling до12M, сохраняет actual7686005+новый расход и максимум4 calls; продолжать текущий ctx_7ff92b6ea59a и ALL без дублирования. Astra high call4 только после ALL/остатка бюджета. Новый provider exhaustion блокирует цепочку.


Финальный checkpoint26.10: Astra call4 BLOCKED/NOT_ACCEPTED; calls4/4, review1/2, input12016680/12000000. Отчёт docs/workflow/reviews/TASK-MVP-04-C1.md; никакого PASS/commit. Требуется явное новое решение по ресурсу для завершения недостающего evidence review, без повторных тестов.

MVP04_ASTRA_EVIDENCE_CALL5_20261026: user явно разрешил один дополнительный Astra high call5/5 и input ceiling12400000 без сброса12016680. Только завершение F/ALL/G evidence review, без code changes/повторных тестов; review slot2/2, reserve300000 включая финализацию. Старый BLOCKED остаётся историей.

Окончательная приёмка26.10: PASS AC001..010, MVP04-R2-001 CLOSED; reviews/TASK-MVP-04-evidence-final.md. Calls5/5, review2/2, input12285453/12400000. Delivery0db1f9ede4b4e4b462ded4ce49a2b45967712732. Предыдущие отказы/BLOCKED и бюджеты сохранены; следующих MVP/worker не запущено.

## Актуальное решение после MVP-04

Пользователь прекратил работу с Nemotron: ADR-011 отозван, TASK-WF-01 снят с
исполнения. Устаревшие разрешения/ограничения в исторических разделах выше
описывают только состояние на момент выполнения MVP-04 и не задают текущую
маршрутизацию. Для будущей работы действует
`docs/workflow/MODEL-ROUTING.md`; следующий продуктовый этап — MVP-05.
