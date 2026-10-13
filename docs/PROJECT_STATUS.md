# Состояние проекта Equipment Documentation Registry

Документ описывает **фактическое** состояние проекта на момент фиксации.
Цель — чтобы новая сессия работы могла восстановить контекст без опоры на
переписку.

> **О прогонах тестов.** Приведённая ниже контрольная точка тестов — это
> **последнее подтверждённое значение из предыдущей сессии**. При подготовке
> этого документа тесты **не запускались**, поэтому число не является результатом
> свежего прогона и его следует перепроверить при первом же изменении кода.

---

## Контрольные точки

| Показатель | Значение | Когда подтверждено |
| --- | --- | --- |
| Тесты | **2011 passed, 1 warning** | предыдущая сессия; свежий прогон не выполнялся |
| Alembic head | **`9e6a954d41be`** | подтверждено чтением `alembic_version` при подготовке этого документа |
| Число миграций | **11** | подтверждено подсчётом файлов в `alembic/versions/` |
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
| **Модели `Document`, `Batch` и таблицы связей** | ORM-модели с CHECK-ограничениями и внешними ключами, миграции, навигационные свойства | Нет схем, сервисов и маршрутов |

---

## Пока не реализовано

| Что | Комментарий |
| --- | --- |
| **Document API** | Нет ни одного маршрута для документов. Модель `Document` и таблицы `document_products` / `document_variants` / `document_batches` существуют, сервиса документа нет |
| **API загрузки и скачивания файлов** | `FileService` и `LocalStorageBackend` готовы, но не подключены к HTTP-слою |
| **BatchService и Batch API** | Модель `Batch` есть, сервиса и маршрутов нет |
| **HTTP-операции привязки документов** | Привязка документов к изделиям, вариантам и партиям на уровне API не реализована — см. [связь сертификатов с типоразмерами](adr/DOCUMENT-VARIANT-RELATIONSHIP.md) |

Итог: центральная сущность предметной области — **документ** — пока недоступна
через HTTP. Всё, что обслуживает её, готово на уровне модели и сервисов.

---

## Схема данных

11 миграций, линейная цепочка без ветвлений, head — `9e6a954d41be`:

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

**Состояние рабочей базы:** 12 таблиц в схеме `public`, все справочники и
фактические таблицы **пусты** — в том числе `document_types`. Начального наполнения
нет, см. [ADR-007](adr/ADR-007-editable-document-type-reference.md).

---

## Известные ограничения и технический долг

| # | Ограничение |
| --- | --- |
| 1 | `Document` и `Batch` существуют только на уровне ORM — основной функциональный пробел |
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

---

## Рекомендуемый следующий этап

**Проектирование жизненного цикла `Document`.**

Это естественная следующая точка роста:

- `Document` — центральная сущность системы, вокруг неё уже построены три
  таблицы связей и подсистема файлов;
- модель, миграция `844b25c35c4b`, CHECK-ограничения и связи полностью готовы и
  покрыты тестами — **новая миграция не потребуется**;
- остальные справочники и агрегаты закрыты полностью, документ — единственная
  верхнеуровневая сущность без единого маршрута.

Ориентиры для проектирования:

1. **Контракт CRUD.** Форма маршрутов должна соответствовать уже принятому
   образцу: `POST` + `Location`, `GET` по `id`, `GET` списка с `limit`/`offset`,
   `PATCH`; 404 для неизвестного, 409 для конфликтов, 422 — валидация.
2. **`document_type_id` обязателен** (`NOT NULL`) — нужно решить, что происходит
   при ссылке на несуществующий или пустой справочник.
3. **`issuer_id` необязателен** — документ может существовать без известного
   эмитента.
4. **Проверки целостности дат.** В модели уже есть
   `ck_documents_valid_range` (`valid_to >= valid_from`, если оба заданы) и
   `ck_documents_verification_status` (`pending` / `verified` / `rejected`).
   Требуется решить, кто отвечает за их соблюдение — схема или сервис.
5. **Семантика `PATCH` по `verification_status`** — переходы между состояниями
   должны быть определены явно.
6. **Затем — операции привязки** документов к изделиям, типоразмерам и партиям,
   и только после них — загрузка и скачивание файлов.

Готовый образец для копирования структуры: `app/api/issuers/` +
`app/services/issuer_service.py` и соответствующие четыре тест-файла
(`test_issuer.py`, `test_issuer_schemas.py`, `test_issuer_service.py`,
`test_issuers_api.py`).

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
│   └── issuers/            router.py + schemas.py
├── database/connection.py  engine, SessionLocal, get_db
├── models/                 10 модулей + __init__.py с реэкспортом
└── services/               5 сервисов сущностей + file_service
                            + storage.py (ABC) + local_storage.py
alembic/versions/           11 ревизий
tests/                      29 файлов тестов + conftest.py
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
- [Связь сертификатов с типоразмерами](adr/DOCUMENT-VARIANT-RELATIONSHIP.md)
- [Корневой README](../README.md)