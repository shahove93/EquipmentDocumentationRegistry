# Состояние проекта Equipment Documentation Registry

Документ описывает **фактическое** состояние проекта на момент фиксации.
Цель — чтобы новая сессия работы могла восстановить контекст без опоры на
переписку.

Дата фиксации: **2026-10-22**.

> **О прогонах тестов.** Приведённая контрольная точка — последнее
> подтверждённое значение полного прогона `pytest`. Проверки frontend
> (`typecheck` и production build) подтверждены отдельно в WSL.

---

## Контрольные точки

| Показатель | Значение | Когда подтверждено |
| --- | --- | --- |
| Тесты | **3377 passed, 1 warning** | подтверждено полным прогоном после интеграционной проверки привязок и поиска (TASK-DOC-007E) на ревизии `ba6c06e` |
| Alembic head | **`a3f1c72d5b90`** | подтверждено чтением `alembic_version` в рабочей базе; миграция применена |
| Число миграций | **12** | подтверждено подсчётом файлов в `alembic/versions/` |
| HTTP-операций | **34** (19 путей) | подтверждено генерацией OpenAPI после добавления двух операций привязки (`GET`/`PUT /documents/{id}/variants`) |
| Frontend typecheck | **успешно** (`tsc --noEmit`, exit 0) | подтверждено в WSL, Node.js v24.22.0, 2026-10-22 |
| Frontend production build | **успешно** (`vite build`, exit 0, `frontend/dist/index.html` создан) | подтверждено в WSL, Node.js v24.22.0, 2026-10-22 |
| Ветка Git | `main` | подтверждено |
| Базовая ревизия backend | `ba6c06e` | подтверждено `git log`; backend-файлы не изменялись |
| Исходный commit | `1bd17dce832660d541bc720ec297d8d55de25c1f` | подтверждено |
| Удалённый репозиторий | `origin` → приватный `shahove93/EquipmentDocumentationRegistry` | подтверждено; push не выполнялся |

Предупреждение тестового прогона — стороннее: `StarletteDeprecationWarning` о
использовании `httpx` в `starlette.testclient`. К проекту не относится.

---

## Технологический стек

| Слой | Технология | Версия |
| --- | --- | --- |
| Web | FastAPI | 0.142.2 |
| ASGI-сервер | uvicorn[standard] | 0.54.0 |
| ORM | SQLAlchemy 2.x (`DeclarativeBase`, `Mapped`/`mapped_column`) | 2.1.3 |
| Миграции | Alembic | 1.20.0 |
| Валидация | Pydantic v2 + pydantic-settings | 2.13.5 / 2.15.0 |
| Multipart | python-multipart | 0.0.32 |
| БД | PostgreSQL (драйвер `psycopg` 3) | сервер 18.6 |
| Тесты | pytest + httpx + `fastapi.testclient` | pytest 9.1.1 |
| Frontend | React + Vite + TypeScript + React Router | 19.3.1 / 8.3.4 / 7.0.2 / 7.18.4 |

Проверки выполняются в WSL Ubuntu: backend и тесты — `.venv/bin/python`,
PostgreSQL 18 онлайн; frontend — Node.js v24.22.0 из nvm. Windows-native Python
зависимостей проекта не содержит.

Архитектурный стиль — **вертикальные срезы**: `модель → схема → сервис → роутер →
тесты`. Слои связаны напрямую, без репозиториев и абстракций unit of work.
Транзакционные границы: сервис коммитит сам, ровно один раз на операцию; методы
чтения не коммитят. Общий **механизм** владения транзакцией и блокировки строк —
`app/services/transaction.py`; им пользуются и `DocumentService`, и `FileService`,
хотя **политика** у них разная: `DocumentService` усыновляет открытую на входе
транзакцию, `FileService` от неё отказывается.

---

## Готовые компоненты

Каждая из шести сущностей ниже имеет полный набор: ORM-модель, Pydantic-схемы
(`Create` / `Update` / `Read`), сервис, HTTP-маршруты и тесты.

| Сущность | Маршруты | Статус |
| --- | --- | --- |
| **Manufacturer** | `POST /manufacturers`, `GET /manufacturers`, `GET /manufacturers/{id}`, `PATCH /manufacturers/{id}` | ✅ готов |
| **Product** | `POST /products`, `GET /products`, `GET /products/{id}`, `PATCH /products/{id}` | ✅ готов |
| **ProductVariant** | `POST /products/{id}/variants`, `GET /products/{id}/variants`, `GET /variants/{id}`, `PATCH /variants/{id}` | ✅ готов |
| **DocumentType** | `POST /document-types`, `GET /document-types`, `GET /document-types/{id}`, `PATCH /document-types/{id}` | ✅ готов |
| **Issuer** | `POST /issuers`, `GET /issuers`, `GET /issuers/{id}`, `PATCH /issuers/{id}` | ✅ готов |
| **Document** | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `PATCH /documents/{id}`, `POST /documents/{id}/verification`, `GET /documents/{id}/verification-history` | ✅ готов |

Дополнительно: `GET /health`, файловые маршруты вложений (пять операций,
см. [ADR-009](adr/ADR-009-document-attachments.md)) и маршруты привязки документа
к типоразмерам (две операции, см.
[ADR-010](adr/ADR-010-document-variant-links-and-search.md)). Всего **19 путей и
34 HTTP-операции**; `DELETE` ровно один — удаление вложения; удаление документов
и справочников по-прежнему не реализовано сознательно.

**Document HTTP API** — шесть операций: `POST` и `GET` коллекции, `GET` и
`PATCH` карточки, `POST .../verification` (подтверждение и отклонение одним
маршрутом) и `GET .../verification-history` (история проверок). Реализован в
`app/api/documents/`, подключён в `app/api/router.py`. Бизнес-логика проверки
целиком в `DocumentService`; роутер — диспетчер и не выполняет SQL. Это локальный
API для разработки: маршруты анонимны, публичное развёртывание запрещено до
появления аутентификации.

**Файловый HTTP API вложений** — пять операций: `POST` и `GET` коллекции,
`GET` метаданных, `GET .../content`, `DELETE`. Реализован в `app/api/files/`,
подключён в `app/api/router.py`. Локальный API для разработки: маршруты
анонимны, публичное развёртывание запрещено до появления аутентификации.

**HTTP-операции привязки к типоразмерам** — две: `GET` и `PUT
/documents/{document_id}/variants`. Реализованы в `app/api/document_variants/`,
подключены в `app/api/router.py`. `PUT` — **атомарная полная замена** набора
привязок, идемпотентная и не меняющая `verification_status` документа; бизнес-логика
в `DocumentVariantService`, роутер SQL не выполняет. Заодно `GET /documents`
расширен необязательными фильтрами `material`, `standard`, `size_text`,
`variant_id`, `manufacturer_id`, `number`, `status` — материальные фильтры
сопоставляются **одному** `ProductVariant`. См.
[ADR-010](adr/ADR-010-document-variant-links-and-search.md).

Вместе эти API реализуют утверждённый жизненный цикл документа: создать
документ, приложить скан, привязать к типоразмерам материала, подтвердить,
изменить реквизиты, отклонить, заменить или удалить вложение — и увидеть каждый
переход в истории, а затем найти сертификат по материалу и размеру. Сквозные
сценарии проверены интеграционными наборами
`tests/test_documents_integration_api.py` и
`tests/test_documents_variant_search_integration_api.py`.

**Веб-интерфейс** — React 19 + Vite + TypeScript в `frontend/`, маршрутизация
React Router. Экраны: реестр документов с фильтрами, статусами и постраничным
просмотром (`/`), создание карточки (`/documents/new`), карточка документа
(`/documents/<id>`) с реквизитами, типоразмерами, вложениями и историей
проверок. Интерфейс обращается к API по относительным путям; dev-сервер Vite
проксирует API-префиксы на `127.0.0.1:8000`, поэтому CORS не включён. Сборка и
типизация подтверждены; `node_modules/` и `dist/` в Git не попадают.
Интерфейс, как и API, предназначен только для локальной разработки: без
аутентификации публиковать его нельзя.

---

## Частично готовые компоненты

| Компонент | Что готово | Чего не хватает |
| --- | --- | --- |
| **FileService** | `attach()` — добавление вложения одной транзакцией: блокировка документа через общий модуль, валидация сигнатуры (PDF/JPEG/PNG), потоковая запись файла и SHA-256 на лету, строка `File`, возврат в `pending` с событием `reopened` (`file_added`); `detach()` — удаление вложения одной транзакцией с блокировкой строки файла, событием `reopened` (`file_deleted`) и удалением файла с диска **только после подтверждённого `commit`**; `upload()` — тонкая обёртка над `attach()`; `list_for_document()`; охранник `TransactionAlreadyOpenError`; компенсация добавления (`_settle` / `_compensate`); журналирование через `logging`; доменные ошибки `AttachmentNotFoundError`, `PendingDocumentChangesError` | HTTP-слой реализован: `app/api/files/` (пять операций) и `app/dependencies.py`; остаются постоянный журнал, сверка осиротевших файлов и индекс `ix_files_document_id_id` |
| **`app/services/transaction.py`** | Общий механизм владения транзакцией и блокировки: `locked_document()` (`SELECT ... FOR UPDATE` + `populate_existing=True` + проверка `inspect(document).modified`), `release()`, `transaction_existed_on_entry()`, `UncommittedChangesInSession`. Используется и `DocumentService`, и `FileService`; 35 тестов | Транзакционные ограничения вызывающего сохраняются — [ADR-008](adr/ADR-008-document-verification-lifecycle.md), раздел «Транзакционные ограничения» |
| **LocalStorageBackend** | Реализация `StorageBackend`: `save` (атомарно, через `"xb"`), `open`, `exists`, `delete`; защита от выхода за пределы корня, от абсолютных путей, от Windows-путей и от `..`; запрет NUL в ключе | Инстанцируется в `app/dependencies.py` (`get_file_service`, `get_storage`); `Settings.STORAGE_ROOT` и `Settings.MAX_UPLOAD_SIZE_BYTES` читаются там же |
| **Модели `Document`, `Batch` и таблицы связей** | ORM-модели с CHECK-ограничениями и внешними ключами, миграции, навигационные свойства | У `Document` есть Pydantic-схемы, `DocumentService` и HTTP-маршруты (`app/api/documents/`). У `Batch` по-прежнему нет ни схем, ни сервиса |
| **`DocumentService`** | `create`, `get`, `list`, `update`; верификация — `verify` и `reject`; чтение истории — `history` (сортировка `created_at ASC, id ASC`, только чтение); переходы `verified`/`rejected` → `pending` при изменении значимых реквизитов; каждый переход атомарно пишется в `document_verification_events`. **Конкурентная безопасность:** `update`, `verify` и `reject` берут блокировку строки **через общий модуль** `app/services/transaction.py` — сам `SELECT ... FOR UPDATE` с `populate_existing=True` живёт там, — проверяют незавершённые изменения вызывающего и освобождают блокировку на путях отказа и no-op; `_locked_document` делегирует в `transaction.locked_document`, `_release` — в `transaction.release` | HTTP-слой документов реализован: `app/api/documents/` (шесть операций), подключён в `app/api/router.py`. Транзакционные ограничения — [ADR-008](adr/ADR-008-document-verification-lifecycle.md), раздел «Транзакционные ограничения» |
| **`verification_history`** | Единственное место, создающее событие `reopened`: проверяет причину по закрытому множеству `significant_fields_changed` / `file_added` / `file_deleted`, проверяет статус, не коммитит и не блокирует. Вызывается из `DocumentService` (`significant_fields_changed`) и из `FileService.attach()` / `detach()` (`file_added` / `file_deleted`); 60 тестов | Все три причины передаются; сам модуль не изменялся |

---

## Пока не реализовано

| Что | Комментарий |
| --- | --- |
| **BatchService и Batch API** | Модель `Batch` есть, сервиса и маршрутов нет |
| **Привязка к `Product` и `Batch`** | Привязка к **типоразмерам** реализована (`GET` / `PUT /documents/{id}/variants`), но связь документа с изделием и партией на уровне API не утверждена и не реализована — [ADR-010](adr/ADR-010-document-variant-links-and-search.md) |
| **Каскадное удаление `ProductVariant`** | `ON DELETE CASCADE` унесёт привязки; семантика требует отдельного решения — [ADR-010](adr/ADR-010-document-variant-links-and-search.md) |
| **Журнал изменений привязок** | Изменение набора привязок не пишет событие истории — [ADR-010](adr/ADR-010-document-variant-links-and-search.md) |

Итог: **вложения документа, сам документ и привязка к типоразмерам** доступны
через HTTP полностью — создание, чтение, частичное изменение, подтверждение,
отклонение и история проверок у документа; загрузка, список, метаданные,
скачивание и удаление у вложений; чтение и полная замена привязок у типоразмеров;
поиск по материалу, стандарту, размеру, производителю, номеру и статусу. Жизненный
цикл проверки, зафиксированный в
[ADR-008](adr/ADR-008-document-verification-lifecycle.md), и материальная привязка
[ADR-010](adr/ADR-010-document-variant-links-and-search.md) теперь достижимы для
пользователя, а не только из Python. Не реализованы: `Batch` (модель есть,
сервиса и маршрутов нет), привязка документов к изделиям и партиям, каскадное
удаление связанных типоразмеров и удаление документов.

---

## Реализовано и принято, но не выполнено

**Реализованные функции** (подтверждены кодом и тестами): `DocumentService` с
полным жизненным циклом верификации, атомарной историей, read-методом `history()`
и фильтрующим `list()`; `DocumentVariantService.list_variants()` /
`set_variants()`; общий модуль `app/services/transaction.py`;
`FileService.attach()` / `detach()` / `upload()` / `list_for_document()`;
автоматический возврат в `pending` с событием `reopened` (`file_added`,
`file_deleted`); компенсация добавления; удаление файла только после
подтверждённого `commit`; журналирование через `logging`; доменные ошибки
`AttachmentNotFoundError`, `TransactionAlreadyOpenError`,
`PendingDocumentChangesError`. **Document HTTP API**: шесть операций, схемы
`DocumentCreate` / `DocumentUpdate` / `DocumentOut` / `DocumentListOut` /
`DocumentVerificationRequest` / `DocumentVerificationEventOut`, отображение
доменных ошибок в `404` / `409` / `422`, сквозной интеграционный сценарий.
**File HTTP API**: пять операций, DI `get_file_service` / `get_storage`, схемы
`FileOut` / `FileListOut`, потоковая загрузка и скачивание, безопасный
`Content-Disposition`, `ClosingStreamingResponse` с закрытием потока при обрыве
и отмене, интеграционные HTTP-тесты.
**Привязка к типоразмерам и поиск**: `DocumentVariantService`, две операции
`GET` / `PUT /documents/{id}/variants`, схема `DocumentVariantLinkRequest`,
отображение доменных ошибок в `404` / `409` / `422`, расширенный `GET /documents`
с материальными фильтрами и сквозной интеграционный сценарий «труба → Ø63 → PDF».
См. [ADR-010](adr/ADR-010-document-variant-links-and-search.md).

**Локальные Document API, File API и API привязок не означают готовности
приложения к публичной эксплуатации.** Все тринадцать маршрутов документов,
вложений и привязок анонимны; до реализации аутентификации и авторизации
публичное развёртывание запрещено.

**Решения приняты, но не выполнены** (обязательны к исполнению, доказательства в
коде отсутствуют): постоянное хранилище журнала; сверка осиротевших файлов;
сверка SHA-256; миграция `ix_files_document_id_id`; аутентификация и
авторизация. Построчный перечень — в разделах «Статус реализации»
[ADR-009](adr/ADR-009-document-attachments.md) и «Ограничения» ниже.

---

## Схема данных

12 миграций, линейная цепочка без ветвлений, head — `a3f1c72d5b90`:

| Ревизия | Содержание |
| --- | --- |
| `b0c2277bc034` | create manufacturers |
| `4d64e9e30df5` | create products |
| `dc9ec9cdbb30` | make products.standard not null |
| `c3bb6dcf63cf` | create product_variants |
| `6984fcc861e6` | create batches |
| `6a736cbf733b` | create document_types |
| `6fdaae2f21ea` | create issuers |
| `844b25c35c4b` | create documents |
| `056121f44e99` | create document link tables |
| `4a43cb5a19ea` | create files |
| `9e6a954d41be` | add unique constraint product_variants (product_id, size_text) — вручную, см. [ADR-006](adr/ADR-006-unique-size-within-product.md) |
| `a3f1c72d5b90` | create document_verification_events — история проверок, см. [ADR-008](adr/ADR-008-document-verification-lifecycle.md) |

**Состояние рабочей базы:** 13 таблиц в схеме `public`, все справочники и
фактические таблицы **пусты** — в том числе `document_types` и
`document_verification_events`. Начального наполнения нет, см.
[ADR-007](adr/ADR-007-editable-document-type-reference.md).

---

## Известные ограничения и технический долг

| # | Ограничение |
| --- | --- |
| 1 | `Batch` существует только на уровне ORM — основной функциональный пробел. `Document` закрыта сквозным срезом: модель, схемы, сервис и шесть HTTP-операций |
| 2 | **Снято.** `Settings.STORAGE_ROOT` и `MAX_UPLOAD_SIZE_BYTES` читаются в `app/dependencies.py` (`get_file_service`, `get_storage`) |
| 3 | Лимит размера загрузки продублирован: константа определена и в `app/config.py`, и в `app/services/file_service.py` |
| 4 | Нет CI-конфигурации и pytest-конфига; нет lock-файла зависимостей |
| 5 | `conftest.py` использует одну фиксированную схему `test_file_service` для всех тестов — параллельный прогон (`pytest-xdist`) приведёт к конфликту |
| 6 | Гигиена фикстур неоднородна: `test_manufacturers_api.py` вызывает `app.dependency_overrides.clear()`, остальные сохраняют и восстанавливают только `get_db` |
| 7 | `manufacturers.name` **не уникален** — в отличие от `issuers.name` и `document_types.name`. Поведение зафиксировано тестами как намеренное |
| 8 | `ManufacturerService` не обрабатывает `IntegrityError` — без `try/rollback`, в отличие от остальных сервисов |
| 9 | Сервисы импортируют Pydantic-схемы из слоя `app.api.*` — нарушение слоёв, безвредно, но связывает бизнес-логику с транспортным слоем |
| 10 | Сравнение строк в справочниках регистрозависимо (кодировка БД `C.UTF-8`) — задокументировано тестами как текущее поведение |
| 11 | **Контроль смены SDR в `PATCH /products/{id}` ещё не реализован**; архитектурное требование закреплено в [ADR-005](adr/ADR-005-one-sdr-one-product.md). Подробности — раздел «Изменение SDR через переименование» |
| 12 | `.env` имеет права `777`; на диске Windows через DrvFs смена прав может не дать эффекта |
| 13 | **Снято.** Реализованы оба HTTP-слоя: File API — пять операций (`FileOut` / `FileListOut`, DI, `python-multipart==0.0.32`), Document API — шесть операций, включая `verification` и `verification-history`. Подтверждение и отклонение достижимы по HTTP |
| 14 | У связи `File.document` нет `passive_deletes=True`, поэтому `db.delete(document)` для документа с вложениями падает по `NOT NULL` на `files.document_id`, хотя в базе объявлен `ON DELETE CASCADE`. Обнаружено тестом; на историю проверок не влияет |
| 15 | Поведение подтверждённого документа при **замене или удалении файла** определено в [ADR-009](adr/ADR-009-document-attachments.md) и **реализовано**: добавление или удаление вложения у `verified` / `rejected` возвращает документ в `pending` и создаёт ровно одно событие `reopened` (`file_added` / `file_deleted`). Изменение состава вложений у `pending` события не создаёт |
| 16 | Индекса по `files.document_id` нет, хотя у всех трёх таблиц связей индексы на внешнем ключе есть — конвенция проекта не соблюдена. `ON DELETE CASCADE` выполняет полное сканирование на каждый документ. Индекс `ix_files_document_id_id` принят в [ADR-009](adr/ADR-009-document-attachments.md), миграция отложена на отдельное задание |
| 17 | `sha256` файла вычисляется и хранится, но **нигде не сверяется** — ни при чтении, ни при сверке |
| 18 | **Успешный `_commit` сервиса фиксирует все незавершённые изменения в своей сессии**, включая правки чужих объектов. На пути успеха чужая работа не защищена — в отличие от пути отказа |
| 19 | `db.in_transaction()` показывает наличие транзакции, но **не является универсальным доказательством владения**. Правило трактует его консервативно: чужая транзакция не откатывается |
| 20 | При транзакции, существовавшей на входе в `DocumentService`, **блокировка после отказа может удерживаться до действий вызывающего кода**. В HTTP-запросе это снимает `get_db`, закрывая сессию |
| 21 | `db.refresh()` после успешного коммита открывает новую транзакцию чтения через autobegin. Блокировок она не держит |
| 22 | `_commit` обрабатывает только `IntegrityError`; обработка ошибок иного рода не укреплена — отдельное задание |
| 23 | **Снято.** Общая граница транзакции определена и реализована: `attach()` и `detach()` владеют **одной** транзакцией и коммитят ровно один раз; `FileService._register` устранён. Общий — только **механизм** (`app/services/transaction.py`); **политика** у сервисов разная: `DocumentService` усыновляет транзакцию, `FileService` отвергает чужую охранником `TransactionAlreadyOpenError` |
| 24 | **Реализовано.** `detach()` берёт блокировку строки файла (`SELECT ... FOR UPDATE` с фильтром по `File.id` **и** `File.document_id`) строго **после** блокировки документа, порядок `Document` → `File` сохранён. `attach()` файловую строку не блокирует — осознанная асимметрия: строка к этому моменту ещё не существует |
| 25 | **Реализовано, но журнал непостоянен.** `_cleanup` удалён; неудачи компенсации и неизвестные исходы пишутся через `logging` с полями `operation`, `document_id`, `storage_key`, `failure_category`, `error_type` (произвольный `str(error)` не пишется). **Постоянного хранилища журнала нет** — ни обработчиков, ни места хранения: при перезапуске записи теряются |
| 26 | Потеря соединения во время `COMMIT` оставляет неизвестный исход: откат не отменяет уже принятый сервером коммит. **Компенсация по типу исключения запрещена** — исход определяется данными: `attach` опрашивает строку по `storage_key`, а `detach` **физический файл сохраняет** (отсутствие строки там неотличимо от успеха). Осиротевший файл восстановим сверкой, потерянный — нет |
| 27 | **Сверка осиротевших файлов не реализована.** Именно она делает безопасным сохранение файла при неизвестном исходе и закрывает вопрос «файл на диске без строки в базе». Пока её нет, осиротевшие файлы накапливаются молча |
| 28 | **При неизвестном исходе `detach` физический файл остаётся на диске** — осознанный компромисс: удалить его значило бы рисковать потерей данных при уже принятом коммите. Цена — осиротевший blob до появления сверки |
| 29 | **`attach` сверяет исход коммита в той же сессии после `rollback()`**, а [ADR-009](adr/ADR-009-document-attachments.md) предписывает новое соединение. Отступление зафиксировано в самом ADR; при нечитаемой сессии исход трактуется как неизвестный, то есть файл сохраняется |
| 30 | **Порядок блокировок `Document` → `File` сегодня ненаблюдаем**: ни один рабочий путь не берёт файловый лок раньше документного, поэтому дедлок-теста нет. Инвариант держится порядком вызовов, а не проверкой |
| 31 | **`upload()` и `attach()` — два имени одного поведения** (`upload()` оставлен тонкой обёрткой ради прежней сигнатуры); `PendingDocumentChangesError` в обычном вызове недостижим, так как `attach` отвергает открытую транзакцию раньше |
| 32 | **Конкурентный набор `tests/test_file_service_concurrency.py` чувствителен к нагрузке машины**: при нормальной нагрузке детерминирован и проходит за ~10 с, под тяжёлой нагрузкой прогон растягивался до ~110 с с падениями в посторонних тестах по таймауту |
| 33 | **Отсутствующий blob — `500`, а не `404`.** Если строка `File` есть, а физического файла нет, скачивание отвечает безопасным `500` (`Stored file content is unavailable`) и пишет `logger.error` с `operation="file.download"`; `404` остаётся для отсутствующей строки и несоответствия `document_id`. Решение зафиксировано в [ADR-009](adr/ADR-009-document-attachments.md) |
| 34 | **Нарушение уникальности не переводится в `409`.** `IntegrityError` в `FileService` остаётся `500`; [ADR-009](adr/ADR-009-document-attachments.md) описывает фактическое поведение и прямо указывает, что конфликт уникальности в `409` не переводится |
| 35 | **Снято.** Комментарий в `app/api/files/router.py` приведён в соответствие с [ADR-009](adr/ADR-009-document-attachments.md) ещё в TASK-DOC-005W: он описывает `500` для отсутствующего blob, а не устаревший `404` |


---

## Рекомендуемый следующий этап

**1. Переход к задачам MVP.**

Накопленные изменения TASK-DOC-007B–007E закоммичены в `ba6c06e`
(«feat(documents): add variant links and certificate search»), а существующий
frontend зафиксирован baseline-коммитом на `main`. Push не выполнялся. Дальше
работа идёт по ROADMAP v1.0: постоянный журнал компенсаций (TASK-MVP-01),
сверка осиротевших файлов (TASK-MVP-02), сверка SHA-256 и миграция индекса
(TASK-MVP-03), `BatchService` и Batch API (TASK-MVP-04), завершение frontend
(TASK-MVP-05) и финальная приёмка этапа (TASK-MVP-06).

**2. Оставшиеся задачи, не входящие в Document API.**

1. **Аутентификация и авторизация.** До неё публичное развёртывание обоих API
   запрещено: все тринадцать маршрутов документов, вложений и привязок анонимны.
2. **Постоянное хранилище журнала.** Настроить обработчики `logging`, чтобы
   записи компенсации переживали перезапуск процесса (ограничение 25).
3. **Сверка осиротевших файлов.** Именно она делает безопасным сохранение
   файла при неизвестном исходе (ограничения 27, 28).
4. **Сверка SHA-256** при чтении вложения (ограничение 17).
5. **Миграция индекса `ix_files_document_id_id`** (ограничение 16).
6. **Привязка документов к изделиям и партиям** — привязка к типоразмерам уже
   реализована ([ADR-010](adr/ADR-010-document-variant-links-and-search.md));
   семантика связей с `Product` и `Batch` ещё не утверждена.
7. **BatchService и Batch API** (ограничение 1).
8. **Индексы под материальный поиск** (`pg_trgm`/GIN) и **журналирование
   изменений привязок** — открытые пункты
   [ADR-010](adr/ADR-010-document-variant-links-and-search.md).

Удаление документов и пагинация истории в MVP не реализованы
сознательно; их появление потребует отдельного решения. Готовый образец для
копирования структуры вертикального среза — `app/api/issuers/` +
`app/services/issuer_service.py` и четыре соответствующих тест-файла
(`test_issuer.py`, `test_issuer_schemas.py`, `test_issuer_service.py`,
`test_issuers_api.py`).

---

## Карта проекта

```
app/
├── main.py                 точка входа, подключение роутеров
├── config.py               Settings; маскирование DATABASE_URL в repr/выводе
├── dependencies.py         get_file_service, get_storage
├── api/
│   ├── router.py           /health + подключение восьми роутеров
│   ├── manufacturers/      router.py + schemas.py
│   ├── products/           router.py + schemas.py
│   ├── variants/           router.py + schemas.py (без prefix)
│   ├── document_types/     router.py + schemas.py
│   ├── issuers/            router.py + schemas.py
│   ├── documents/          router.py + schemas.py
│   ├── document_variants/  router.py + schemas.py  привязка к типоразмерам
│   └── files/              router.py + schemas.py + download.py
├── database/connection.py  engine, SessionLocal, get_db
├── models/                 11 модулей + __init__.py с реэкспортом
└── services/               7 сервисов сущностей
                            + transaction.py  общий механизм блокировки и транзакции
                            + verification_history.py  общий механизм reopened
                            + file_service.py
                            + document_variant_service.py  привязка документ ↔ типоразмер
                            + storage.py (ABC) + local_storage.py
alembic/versions/           12 ревизий
tests/                      55 файлов тестов + conftest.py
frontend/                   React 19 + Vite + TypeScript
├── src/                    App, pages, components, hooks, api, utils
├── index.html
├── vite.config.ts          прокси API на 127.0.0.1:8000
└── package.json            typecheck / build / dev
docs/                       эта документация
```

`frontend/node_modules/` и `frontend/dist/` в Git не попадают: они исключены
`.gitignore`.

Тесты покрывают каждый слой отдельно: модель, схемы, сервис, HTTP. Общая
фикстура `engine` создаёт временную схему `test_file_service`, поднимает в ней
таблицы через `Base.metadata.create_all` и удаляет схему после теста — поэтому
тесты **изолированы от схемы `public`** рабочей базы.

---

## Навигация

- [Индекс архитектурных решений](adr/README.md)
- [ADR-005. Один SDR — отдельное изделие](adr/ADR-005-one-sdr-one-product.md)
- [ADR-006. Уникальность типоразмера внутри изделия](adr/ADR-006-unique-size-within-product.md)
- [ADR-007. Редактируемый справочник типов документов](adr/ADR-007-editable-document-type-reference.md)
- [ADR-008. Жизненный цикл проверки документа и история верификации](adr/ADR-008-document-verification-lifecycle.md)
- [ADR-009. Архитектура вложений документа](adr/ADR-009-document-attachments.md)
- [ADR-010. Привязка документов к типоразмерам и материальный поиск](adr/ADR-010-document-variant-links-and-search.md)
- [Черновик. Связь сертификатов с типоразмерами](adr/DOCUMENT-VARIANT-RELATIONSHIP.md)
- [Корневой README](../README.md)