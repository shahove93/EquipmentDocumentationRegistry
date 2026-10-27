# Участие в разработке

## Среда

Разработка и проверки выполняются в Ubuntu под WSL2. Нужны Python 3.14, PostgreSQL 18, Node.js 24.22.0 через nvm и npm. Установите Python- и frontend-зависимости командами из раздела «Локальная разработка» в [README](README.md).

Настройте `DATABASE_URL` для локальной базы приложения. Для полного набора тестов используйте отдельную disposable базу `equipment_docs_test`, задайте локальный `PGPASSWORD` (hardcoded тестовые DSN подключаются как `edr@127.0.0.1:5432/postgres` и не содержат пароль), затем временно направьте `DATABASE_URL` и `EDR_TEST_DATABASE_URL` на `equipment_docs_test`. В URL для `DATABASE_URL` и `EDR_TEST_DATABASE_URL` укажите пароль роли `edr`: `tests/test_database.py` проверяет, что пароль сохранён в URL приложения. Примените Alembic миграции к тестовой базе до pytest: `DATABASE_URL="$EDR_TEST_DATABASE_URL" .venv/bin/python -m alembic upgrade head`. Команды создания роли и отдельной тестовой базы приведены в [README](README.md). Никогда не запускайте эту миграцию с URL базы приложения `equipment_docs`; оставьте `DATABASE_URL` на тестовую базу до завершения pytest. Тестовая фикстура удаляет и создаёт схему `test_file_service` в выбранной базе. Не запускайте тесты на базе с нужными данными.

## Перед отправкой изменений

Запустите проверки из корня репозитория:

```bash
DATABASE_URL="$EDR_TEST_DATABASE_URL" .venv/bin/python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

Backend-тесты требуют доступного PostgreSQL. Frontend-checks запускаются из `frontend/`. Опишите в pull request область изменения и фактически выполненные проверки; если проверка не запускалась, укажите причину. Не включайте в изменения `.env`, локальные данные и файлы из `storage/`.

## Сообщения об ошибках и запросы функций

Используйте формы GitHub. Не прикладывайте реальные документы, персональные, коммерческие или иные чувствительные данные, секреты и содержимое `.env`. Для воспроизведения опишите минимальный обезличенный пример.
