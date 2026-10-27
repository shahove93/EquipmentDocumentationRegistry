# Разработка в WSL2

Это руководство сохраняет локальные инструкции для разработчиков. Пользователям Windows, которые хотят установить приложение, см. [руководство по установке](installation/windows.md).

## Требования

Нужны Ubuntu в WSL2, Python 3.14, Node.js 24.22.0 через nvm и работающий PostgreSQL 18. Backend и тесты запускаются из корня репозитория через `.venv/bin/python`; frontend — через npm из `frontend/`.

## PostgreSQL и окружение

В WSL откройте консоль PostgreSQL командой `sudo -u postgres psql` и создайте локальную роль и базы (задайте собственный пароль):

```sql
CREATE ROLE edr LOGIN PASSWORD 'YOUR_LOCAL_PASSWORD';
CREATE DATABASE equipment_docs OWNER edr;
CREATE DATABASE equipment_docs_test OWNER edr;
\q
```

Задайте переменные подключения в окружении WSL. Подставьте свой пароль и не сохраняйте его в Git:

```bash
export PGPASSWORD='YOUR_LOCAL_PASSWORD'
export DATABASE_URL='postgresql+psycopg://edr:YOUR_LOCAL_PASSWORD@127.0.0.1:5432/equipment_docs'
```

Установите зависимости:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend && npm ci && cd ..
```

Задайте `DATABASE_URL` для локальной базы приложения в окружении WSL или локальном `.env` (не добавляйте этот файл в Git). Примените миграции и запустите backend:

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --reload
```

В отдельном терминале WSL запустите интерфейс:

```bash
cd frontend && npm run dev
```

## Безопасный запуск тестов

Тесты используют отдельную disposable базу `equipment_docs_test`; не направляйте их на базу приложения или базу с нужными данными. Подготовьте тестовую базу и примените миграции именно к ней (переменные действуют только в текущем shell):

```bash
export EDR_TEST_DATABASE_URL='postgresql+psycopg://edr:YOUR_LOCAL_PASSWORD@127.0.0.1:5432/equipment_docs_test'
export DATABASE_URL="$EDR_TEST_DATABASE_URL"
.venv/bin/python -m alembic upgrade head
```

Здесь `DATABASE_URL` временно указывает на тестовую базу, потому что `alembic/env.py` и часть тестов читают эту переменную. Это отдельная команда подготовки тестов: **не запускайте её с `DATABASE_URL`, указывающим на `equipment_docs`**. PostgreSQL применяет `PGPASSWORD` к существующим тестовым подключениям без пароля, включая DSN `edr@127.0.0.1:5432/postgres`; workflow поэтому также создаёт базу `postgres` для этих тестов. Перед запуском приложения задайте `DATABASE_URL` обратно на `equipment_docs`.

Тестовая фикстура удаляет и создаёт схему `test_file_service` в выбранной базе. Не запускайте тесты на базе с нужными данными.

## Проверки

Из корня репозитория:

```bash
DATABASE_URL="$EDR_TEST_DATABASE_URL" .venv/bin/python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

Backend-тесты требуют доступного PostgreSQL. Frontend-команды запускаются из каталога `frontend/`.

## Полезные ссылки

- [Инструкция установки Windows](installation/windows.md)
- [CONTRIBUTING](../CONTRIBUTING.md)
- [Индекс ADR](adr/README.md)
- [Состояние проекта](PROJECT_STATUS.md)
