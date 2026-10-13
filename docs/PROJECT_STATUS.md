# Состояние проекта Equipment Documentation Registry

Документ описывает **фактическое** состояние проекта на момент фиксации.
Цель — чтобы новая сессия работы могла восстановить контекст без опоры на
переписку.

> **О прогонах тестов.** Приведённая контрольная точка — последнее
> подтверждённое значение полного прогона `pytest`.

---

## Контрольные точки

| Показатель | Значение | Когда подтверждено |
| --- | --- | --- |
| Тесты | **2384 passed, 1 warning** | подтверждено полным прогоном после интеграции истории проверок в `DocumentService` |
| Alembic head | **`a3f1c72d5b90`** | подтверждено чтением `alembic_version` в рабочей базе; миграция применена |
| Число миграций | **12** | подтверждено подсчётом файлов в `alembic/versions/` |
| Ветка Git | `main` | подтверждено |
| Исходный commit | `1bd17dce832660d541bc720ec297d8d55de25c1f` | подтверждено |
| Удалённый репозиторий | `origin` → приватный `shahove93/EquipmentDocumentationRegistry` | подтверждено |

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
| БД | PostgreSQL (драйвер `psycopg` 3) | сервер 18.6 |
| Тесты | pytest + httpx + `fastapi.testclient` | pytest 9.1.1 |

Архитектурный стиль — **вертикальные срезы**: `модель → схема → сервис → роутер →
тесты`. Слои связаны напрямую, без репозиториев и абстракций unit of work.
Транзакционные границы: сервис коммитит сам, ровно один раз на операцию; методы
чтения не коммитят.

---

## Готовые компоненты

Каждая из пяти сущностей ниже имеет полный набор: ORM-модель, Pydantic-схемы
(`Create` / `Update` / `Read`), сервис, HTTP-маршруты и тесты.

| Сущность | Маршруты | Статус |
| --- | --- | --- |
| **Manufacturer** | `POST /manufacturers`, `GET /manufacturers`, `GET /manufacturers/{id}`, `PATCH /manufacturers/{id}` | ✅ готов |
| **Product** | `POST /products`, `GET /products`, `GET /products/{id}`, `PATCH /products/{id}` | ✅ готов |
| **ProductVariant** | `POST /products/{id}/variants`, `GET /products/{id}/variants`, `GET /variants/{id}`, `PATCH /variants/{id}` | ✅ готов |
| **DocumentType** | `POST /document-types`, `GET /document-types`, `GET /document-types/{id}`, `PATCH /document-types/{id}` | ✅ готов |
| **Issuer** | `POST /issuers`, `GET /issuers`, `GET /issuers/{id}`, `PATCH /issuers/{id}` | ✅ готов |

Дополнительно: `GET /health`. Всего в приложении **21 маршрут**, из них
**ни одного `DELETE` и ни одного `PUT`** — удаление для справочников пока не
реализовано сознательно.

---

## Частично готовые компоненты

| Компонент | Что готово | Чего не хватает |
| --- | --- | --- |
| **FileService** | `upload()` — проверка сигнатуры (PDF/JPEG/PNG), ограничение размера, вычисление SHA-256 на лету, сохранение в хранилище, регистрация строки `File`, откат и удаление файла при ошибке регистрации; `list_for_document()` | Нет HTTP-маршрутов, нет DI — сервис не подключён к приложению |
| **LocalStorageBackend** | Реализация `StorageBackend`: `save` (атомарно, через `"xb"`), `open`, `exists`, `delete`; защита от выхода за пределы корня, от абсолютных путей, от Windows-путей и от `..`; запрет NUL в ключе | Не инстанцируется приложением; `Settings.STORAGE_ROOT` и `Settings.MAX_UPLOAD_SIZE_BYTES` **объявлены, но нигде не используются** |
| **Модели `Document`, `Batch` и таблицы связей** | ORM-модели с CHECK-ограничениями и внешними ключами, миграции, навигационные свойства | У `Document` есть Pydantic-схемы и `DocumentService`; маршрутов и DI нет. У `Batch` по-прежнему нет ни схем, ни сервиса |
| **`DocumentService`** | `create`, `get`, `list`, `update`; верификация — `verify` и `reject`; переходы `verified`/`rejected` → `pending` при изменении значимых реквизитов; каждый переход атомарно пишется в `document_verification_events` | HTTP-маршрутов нет; не подключён к приложению. Правила — [ADR-008](adr/ADR-008-document-verification-lifecycle.md) |

---

## Пока не реализовано

| Что | Комментарий |
| --- | --- |
| **Document API** | Ни одного маршрута для документов. Модель `Document`, Pydantic-схемы и `DocumentService` готовы и покрыты тестами; не подключены к приложению |
| **API загрузки и скачивания файлов** | `FileService` и `LocalStorageBackend` готовы, но не подключены к HTTP-слою. Из-за этого `verify` недостижим для пользователя — см. [ADR-008](adr/ADR-008-document-verification-lifecycle.md) |
| **BatchService и Batch API** | Модель `Batch` есть, сервиса и маршрутов нет |
| **HTTP-операции привязки документов** | Привязка документов к изделиям, вариантам и партиям на уровне API не реализована — см. [связь сертификатов с типоразмерами](adr/DOCUMENT-VARIANT-RELATIONSHIP.md) |

Итог: центральная сущность предметной области — **документ** — пока недоступна
через HTTP. На уровне модели, схем и сервисов она закрыта полностью, включая
жизненный цикл проверки и его историю.

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
| 1 | `Batch` существует только на уровне ORM — основной функциональный пробел. `Document` закрыта на уровне модели, схем и сервиса, но недоступна через HTTP |
| 2 | `Settings.STORAGE_ROOT` и `MAX_UPLOAD_SIZE_BYTES` не используются production-кодом |
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
| 13 | **`FileService` не подключён к HTTP-слою**, поэтому пользователь не может прикрепить файл, а значит и подтвердить документ: `verify` требует вложения. Весь подтверждённый жизненный цикл программный — см. [ADR-008](adr/ADR-008-document-verification-lifecycle.md) |
| 14 | У связи `File.document` нет `passive_deletes=True`, поэтому `db.delete(document)` для документа с вложениями падает по `NOT NULL` на `files.document_id`, хотя в базе объявлен `ON DELETE CASCADE`. Обнаружено тестом; на историю проверок не влияет |
| 15 | Поведение подтверждённого документа при **замене или удалении файла** не определено и не реализовано: вердикт остаётся, хотя содержимое скана изменилось. Механизм не утверждён |

---

## Рекомендуемый следующий этап

**Подключение `FileService` к HTTP-слою — до подключения Document API.**

Порядок здесь не свободный. `DocumentService.verify` требует хотя бы одного
прикреплённого файла, а загрузить файл через приложение сейчас нельзя. Поэтому
Document API, подключённый раньше, дал бы пользователю возможность создать
документ, но невозможность его подтвердить — половину жизненного цикла без
смысла.

Ориентиры:

1. **Контракт загрузки.** Форма маршрутов соответствует уже принятому образцу:
   `POST` с телом файла + `Location`, `GET` списка вложений документа,
   скачивание по `storage_key`; 404 для неизвестного документа или файла,
   422 — валидация типа и размера.
2. **DI.** `FileService` сейчас создаётся вручную и нигде не инстанцируется
   приложением. `Settings.STORAGE_ROOT` и `MAX_UPLOAD_SIZE_BYTES` объявлены,
   но не используются production-кодом — их задействование естественно ложится
   именно на этот этап.
3. **Транзакционная граница.** Загрузка файла и регистрация строки `File` —
   разные операции; существующий `upload()` откатывает регистрацию при ошибке
   и удаляет сохранённый файл. Эта пара соглашений должна сохраниться при
   появлении HTTP-обёртки.

**Затем — Document API.** Проектирование его контракта уже частично выполнено:
модель `Document`, схемы `DocumentCreate` / `DocumentUpdate` / `DocumentOut` и
`DocumentService` существуют, а правила верификации зафиксированы в
[ADR-008](adr/ADR-008-document-verification-lifecycle.md). Открытыми остаются:

1. **Отображение доменных ошибок на коды ответа.** `DocumentTypeNotFoundError`
   и `IssuerNotFoundError` — 404 либо 422, `InvalidValidityPeriodError` — 422,
   `DocumentHasNoFilesError` и `RejectionReasonRequiredError` — решение
   требуется. Они возникают при `PATCH` и при подтверждении, то есть в маршрутах,
   которых ещё нет.
2. **`PATCH /documents/{id}` не принимает `verification_status`** — это
   зафиксированное решение, а не пробел. Подтверждение и отклонение получают
   отдельные маршруты; их форма ещё не выбрана.
3. **`document_type_id` обязателен** (`NOT NULL`), и справочник по умолчанию
   пуст — нужно решить, чем отвечать на попытку создать документ в пустом
   справочнике.
4. **Затем — операции привязки** документов к изделиям, типоразмерам и партиям,
   см. [связь сертификатов с типоразмерами](adr/DOCUMENT-VARIANT-RELATIONSHIP.md).

Готовый образец для копирования структуры: `app/api/issuers/` +
`app/services/issuer_service.py` и соответствующие четыре тест-файла
(`test_issuer.py`, `test_issuer_schemas.py`, `test_issuer_service.py`,
`test_issuers_api.py`). Для `documents/` образец уже наполовину собран:
`app/api/documents/` содержит схемы без роутера.

---

## Карта проекта

```
app/
├── main.py                 точка входа, подключение роутеров
├── config.py               Settings; маскирование DATABASE_URL в repr/выводе
├── api/
│   ├── router.py           /health + подключение пяти роутеров
│   ├── manufacturers/      router.py + schemas.py
│   ├── products/           router.py + schemas.py
│   ├── variants/           router.py + schemas.py (без prefix)
│   ├── document_types/     router.py + schemas.py
│   ├── issuers/            router.py + schemas.py
│   └── documents/          schemas.py (роутера нет)
├── database/connection.py  engine, SessionLocal, get_db
├── models/                 11 модулей + __init__.py с реэкспортом
└── services/               6 сервисов сущностей + file_service
                            + storage.py (ABC) + local_storage.py
alembic/versions/           12 ревизий
tests/                      33 файла тестов + conftest.py
docs/                       эта документация
```

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
- [Связь сертификатов с типоразмерами](adr/DOCUMENT-VARIANT-RELATIONSHIP.md)
- [Корневой README](../README.md)