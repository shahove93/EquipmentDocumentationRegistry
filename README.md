# Equipment Documentation Registry

Локальное приложение для ведения реестра документов на материалы и оборудование: паспортов, сертификатов и сопроводительных документов.

## Возможности MVP

- Реестр производителей, изделий и типоразмеров, типов документов и выдавших их организаций.
- Карточки документов с реквизитами, вложениями PDF/JPEG/PNG, статусом проверки и историей.
- Поиск документов по материалу, стандарту, размеру, производителю, номеру и статусу; привязка документа к типоразмерам.
- Учёт партий: backend API и экран списка, просмотра, создания и редактирования.

Связь документа с партией или изделием не реализована. Приложение предназначено для локального однопользовательского использования: аутентификации и авторизации нет. Не публикуйте API или пользовательские данные в интернете.

## Локальная разработка (WSL2)

Нужны Ubuntu в WSL2, Python 3.14, Node.js 24.22.0 (через nvm) и работающий PostgreSQL 18. В WSL откройте консоль PostgreSQL командой `sudo -u postgres psql` и создайте локальную роль и базу (задайте собственный пароль):

```sql
CREATE ROLE edr LOGIN PASSWORD 'YOUR_LOCAL_PASSWORD';
CREATE DATABASE equipment_docs OWNER edr;
CREATE DATABASE equipment_docs_test OWNER edr;
\q
```

Задайте строку подключения в окружении WSL (подставьте пароль, не сохраняйте его в Git):

```bash
export PGPASSWORD='YOUR_LOCAL_PASSWORD'
export DATABASE_URL='postgresql+psycopg://edr:YOUR_LOCAL_PASSWORD@127.0.0.1:5432/equipment_docs'
```

После этого установите зависимости:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend && npm ci && cd ..
```

Задайте `DATABASE_URL` для локальной базы приложения в окружении WSL или в локальном `.env` (не добавляйте этот файл в Git). Примените миграции и запустите приложение:

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --reload
```

В отдельном терминале WSL запустите интерфейс:

```bash
cd frontend && npm run dev
```

Тесты используют отдельную disposable базу `equipment_docs_test`; не направляйте их на базу приложения или базу с нужными данными. Подготовьте её и выполните миграции именно в ней (переменные заданы только в текущем shell):

```bash
export EDR_TEST_DATABASE_URL='postgresql+psycopg://edr:YOUR_LOCAL_PASSWORD@127.0.0.1:5432/equipment_docs_test'
export DATABASE_URL="$EDR_TEST_DATABASE_URL"
.venv/bin/python -m alembic upgrade head
```

Здесь `DATABASE_URL` временно указывает на тестовую базу, потому что `alembic/env.py` и часть тестов читают эту переменную. Это отдельная команда подготовки тестов: не запускайте её с `DATABASE_URL`, указывающим на `equipment_docs`. PostgreSQL применяет `PGPASSWORD` к существующим тестовым подключениям без пароля, включая DSN `edr@127.0.0.1:5432/postgres`; workflow поэтому также создаёт базу `postgres` для этих тестов. Перед запуском приложения задайте `DATABASE_URL` обратно на `equipment_docs`.

## Проверки

```bash
DATABASE_URL="$EDR_TEST_DATABASE_URL" .venv/bin/python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

Архитектурные решения: [индекс ADR](docs/adr/README.md), [жизненный цикл проверки документа](docs/adr/ADR-008-document-verification-lifecycle.md), [вложения](docs/adr/ADR-009-document-attachments.md) и [связи с типоразмерами и поиск](docs/adr/ADR-010-document-variant-links-and-search.md). Правила разработки см. в [CONTRIBUTING.md](CONTRIBUTING.md).
