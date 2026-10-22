# TASK-MVP-01 — Постоянный журнал компенсаций и неизвестных исходов

Статус: IN_PROGRESS. Требования: VISION.md, ARCHITECTURE.md, ROADMAP.md,
ADR-005…010. Этап ROADMAP: 2.
Предшественники с обязательным PASS: TASK-MVP-00 PASS.
Класс риска: R1 (обоснование: конфигурация `logging`, форматтер и тесты;
схема БД, API и бизнес-логика не меняются).
Маршрут приёмки: независимый OpenCode-ревьюер. Ревьюер: отдельный worker Orca.

## Цель и область

Сделать журнал компенсаций и неизвестных исходов постоянным: записи
`app.*` уровня `INFO` и выше должны дописываться в файл, переживать перезапуск
процесса и содержать машиночитаемые поля ADR-009. Формат — JSON Lines (один
JSON-объект на строку), кодировка UTF-8, режим добавления.

Целевые компоненты/файлы: `app/config.py`, новый `app/logging_config.py`,
`app/main.py`, новый `tests/test_logging_config.py`, `.env.example`,
`docs/adr/ADR-009-document-attachments.md` (только статус журнала и открытый
вопрос о форме записи), `docs/PROJECT_STATUS.md`,
`docs/workflow/evidence/TASK-MVP-01-C1.md`.
Разрешено изменять: перечисленные файлы; commit в `main`.
Не затрагивать: `app/services/file_service.py`, `app/api/files/**`,
`app/services/**`, `app/models/**`, `app/api/**` (кроме `app/main.py`),
`alembic/**`, `tests/**` (кроме нового `tests/test_logging_config.py`),
`frontend/**`, `requirements.txt`, `.gitignore`, `docs/adr/**` (кроме
ADR-009), остальные workflow-документы.
Инварианты: ADR-005…010; локальный API; никаких push/merge/deploy; формат
записи не включает произвольный `str(error)`, traceback или неизвестные
`extra`-поля.

## Критерии приёмки

Чек-лист заморожен координатором до диспатча и передан исполнителю и ревьюеру
отдельно. Ревьюер проверяет строго по этому списку.

| ID | Критерий | Способ независимой проверки | Severity |
| --- | --- | --- | --- |
| AC-001 | `Settings.LOG_FILE` имеет default `storage/logs/app.log`, отклоняет пустое значение; `.env.example` документирует параметр | Тест `tests/test_logging_config.py`; `git diff` по `app/config.py`, `.env.example` | BLOCKER |
| AC-002 | Журнал пишется как JSON Lines: один объект на строку, UTF-8, режим append; каждая запись содержит `timestamp` (ISO 8601 с UTC-смещением), `level`, `logger`, `message` | Тест читает файл построчно и парсит `json.loads`; проверяет поля и `datetime.fromisoformat` | BLOCKER |
| AC-003 | Поля аудита попадают в запись при наличии: `operation`, `document_id`, `storage_key`, `failure_category`, `error_type`, `file_id`; отсутствующие не добавляются как `null` | Тест эмитирует запись с полями и без них; проверяет состав ключей | BLOCKER |
| AC-004 | Журнал переживает перезапуск: два независимых процесса дописывают записи в один файл, первая запись не теряется | Тест запускает `sys.executable` дважды с `LOG_FILE` во временном каталоге и сравнивает две строки | BLOCKER |
| AC-005 | Произвольные `extra`-поля и текст исключения не сохраняются | Тест передаёт `secret`, `error_text`, `raw_error`; проверяет отсутствие значений и ключей в файле | BLOCKER |
| AC-006 | Повторная конфигурация не создаёт дубликатов обработчиков и строк; shutdown закрывает и снимает обработчик | Тест: configure → emit → configure → emit; ровно две строки, один обработчик; после close записей больше нет | MAJOR |
| AC-007 | `app.main` настраивает журнал на старте lifespan и закрывает его на shutdown | Тест с `TestClient(app)` в контексте, `LOG_FILE` через env, лог `app.*`; запись появляется в файле | BLOCKER |
| AC-008 | Существующие источники аудита не изменены | `git diff --name-only <baseline>..HEAD` не содержит `app/services/file_service.py`, `app/api/files/`, `tests/test_file_service.py`, `tests/test_files_*` | BLOCKER |
| AC-009 | Путь по умолчанию исключён из Git; лог-файлы не добавлены | `git check-ignore -v storage/logs/app.log`; `git ls-files '*.log'` пуст | BLOCKER |
| AC-010 | ADR-009 и `PROJECT_STATUS.md` отражают факт: журнал постоянный, путь/формат указаны, retrieval-инструмент не выдаётся за реализованный | Чтение изменённых разделов; отсутствие противоречий с кодом | MAJOR |
| AC-011 | Новые тесты и полный regression-набор зелёные; миграций по-прежнему 12 | `pytest -q tests/test_logging_config.py`; полный `pytest -q` — 0 failed, passed ≥ 3377 + новые; `ls alembic/versions/*.py \| wc -l` = 12 | BLOCKER |
| AC-012 | Evidence-пакет заполнен и не закоммичен исполнителем | `docs/workflow/evidence/TASK-MVP-01-C1.md`: команды, CWD, exit code, результаты, commit hash; файл отсутствует в коммите | MAJOR |

## Команды проверок

| Команда | CWD | Ожидаемый результат |
| --- | --- | --- |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_logging_config.py'` | корень | exit 0, все новые тесты passed |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | exit 0, 0 failed, passed ≥ 3377 + новые |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | `12` |
| `git diff --name-only <baseline>..HEAD`; `git show --stat --oneline HEAD` | корень | только разрешённые файлы; evidence не в коммите |
| `git check-ignore -v storage/logs/app.log`; `git ls-files '*.log'` | корень | путь ignored; список пуст |

## Текущее задание OpenCode

- Рабочая ветка/worktree: `main`, текущий workspace.
- Базовая ревизия: `5e9e626` (HEAD после приёмки TASK-MVP-00).
- Подход / цикл: A1 / C1.
- Метод: добавить `LOG_FILE` в `Settings`; реализовать `app/logging_config.py`
  с JSONL-форматтером и идемпотентной установкой обработчика на logger `app`;
  подключить настройку в lifespan `app/main.py`; покрыть тестами; обновить
  `.env.example`, ADR-009 и `PROJECT_STATUS.md`; закоммитить разрешённые файлы
  в `main`; evidence-файл не коммитить — координатор закоммитит его после
  приёмки.
- Замечания для исправления: нет.
- Формат результата: изменения, выполненные проверки, commit hash, ограничения
  и реальный `worker_done` по текущему preamble Orca; не присваивать PASS.

## Приёмка

Решение: NOT_REVIEWED. Автор решения: независимый OpenCode-ревьюер.
Проверенная ревизия: не назначена.
Сводка/счётчики: ../workflow/STATE.md. История: ../workflow/HISTORY.md.
Подробный отчёт: ../workflow/reviews/TASK-MVP-01.md. Пакет доказательств:
../workflow/evidence/TASK-MVP-01-C1.md. Следующий TASK: TASK-MVP-02.
