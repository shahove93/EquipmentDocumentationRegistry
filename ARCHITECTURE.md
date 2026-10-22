# ARCHITECTURE — Equipment Documentation Registry

Версия: 1.0 (утверждена 2026-10-22).
Базовые решения: ADR-005…ADR-010 в [docs/adr/](docs/adr/README.md).
Фактическое состояние: [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Стек

| Слой | Технология |
| --- | --- |
| HTTP | FastAPI, uvicorn |
| ORM | SQLAlchemy 2.x (`DeclarativeBase`, `Mapped`) |
| БД | PostgreSQL, драйвер psycopg 3 |
| Миграции | Alembic |
| Валидация | Pydantic v2 |
| Тесты | pytest, httpx, `fastapi.testclient` |
| Frontend | React 19 + Vite + TypeScript, React Router |
| Файлы | локальный `LocalStorageBackend` под `Settings.STORAGE_ROOT` |

## Стиль и слои

Вертикальные срезы: `model → schema → service → router → tests`. Слои связаны
напрямую; репозиториев и unit of work нет. Сервис владеет транзакцией и коммитит
ровно один раз на операцию; read-методы не коммитят. Общий механизм владения
транзакцией и блокировки строк — `app/services/transaction.py`.

## Данные

Основные сущности: `Manufacturer`, `Product`, `ProductVariant`, `Batch`,
`DocumentType`, `Issuer`, `Document`, `File`, `DocumentVerificationEvent`.
Связи документа: `document_variants` (утверждена ADR-010), `document_products` и
`document_batches` (в модели есть, API и семантика не утверждены).

Ключевые инварианты:

- один SDR — отдельное изделие (ADR-005);
- типоразмер уникален в пределах изделия по `(product_id, size_text)` (ADR-006);
- статус документа — `pending` / `verified` / `rejected`; изменение значимых
  реквизитов или состава вложений возвращает документ в `pending` и пишет событие
  истории (ADR-008, ADR-009);
- вложения добавляются и удаляются одной транзакцией; файл удаляется с диска
  только после подтверждённого коммита (ADR-009);
- `PUT /documents/{id}/variants` — атомарная полная замена набора привязок,
  идемпотентная и не меняющая статус (ADR-010).

## API и frontend

API состоит из 19 путей и 34 HTTP-операций: справочники, документы, проверка,
история, вложения и привязка к типоразмерам. Все маршруты локальные и анонимные;
публичное развёртывание запрещено до появления аутентификации.

Frontend обращается к API по относительным путям; dev-сервер Vite проксирует
`/documents`, `/products`, `/variants`, `/manufacturers`, `/issuers`,
`/document-types` и `/health` на `127.0.0.1:8000`. CORS не включён.

## Окружение

Разработка и проверки — в WSL2 Ubuntu 26.04: Python 3.14 в `.venv`,
PostgreSQL 18 (кластер `18/main`), Node.js через nvm. Windows-native Python не
содержит зависимостей проекта; frontend-зависимости установлены под Linux.
Команды проверок — в [AGENTS.md](AGENTS.md).

## Границы

- Локальный однопользовательский MVP; аутентификация и публичное развёртывание
  вне объёма.
- Push, merge в `main`, deployment и удаление важных данных — только по
  отдельному разрешению.
- Принятые ADR не переписываются; новое архитектурное решение оформляется
  отдельным ADR и требует согласования.
