# TASK-MVP-01 / C1 — пакет доказательств

## Идентификация

- TASK: TASK-MVP-01 — Постоянный журнал компенсаций и неизвестных исходов.
- Подход / цикл: A1 / C1.
- Класс риска: R1.
- Ревизия: базовая по TASK `5e9e626`; фактический HEAD перед работой `49b79f0`
  (workflow-коммиты координатора); результат — коммит
  `5b9d916ed933214f3fbfbf3cef097bea31893069`.
- Run / Task / Dispatch Orca: `run_68046cea3eb4` / `task_b3bcd28acaf7` /
  `ctx_e67979c66846`.
- Рабочая область: `D:\Antigravity\EquipmentDocumentationRegistry`
  (`/mnt/d/Antigravity/EquipmentDocumentationRegistry`), ветка `main`.
- Исполнитель: отдельный OpenCode-исполнитель (Orca worker,
  `term_0d99fac8-4782-4b0d-8072-c3bc4cd60d32`).
- Дата: 2026-10-22.

## Что изменено

Журнал `app.*` уровня INFO и выше стал постоянным: записи дописываются в
`Settings.LOG_FILE` в формате JSON Lines (UTF-8), переживают перезапуск
процесса и содержат машиночитаемые поля ADR-009. Настройка подключена в lifespan
`app/main.py`; произвольные `extra`-поля, `str(error)` и traceback не пишутся.
Источники аудита (`app/services/file_service.py`, `app/api/files/**`) не
изменялись.

| Файл | Назначение изменения |
| --- | --- |
| `app/config.py` | `Settings.LOG_FILE` (default `storage/logs/app.log`), отклонение пустого значения, `LOG_FILE` в `repr` |
| `app/logging_config.py` | новый модуль: JSONL-форматтер, идемпотентная установка/замена обработчика на logger `app`, закрытие и снятие обработчика |
| `app/main.py` | lifespan: настройка журнала на старте, закрытие на shutdown |
| `tests/test_logging_config.py` | 23 теста: настройка, JSONL-поля, поля аудита, перезапуск двумя процессами, отсутствие секретов, идемпотентность, закрытие, TestClient lifespan |
| `.env.example` | документирован `LOG_FILE` |
| `docs/adr/ADR-009-document-attachments.md` | статус журнала и открытый вопрос о форме записи; правила вложений не менялись |
| `docs/PROJECT_STATUS.md` | фактическое состояние: постоянный журнал, контрольная точка тестов, ограничение 25 снято |

Коммит: `5b9d916` — `feat(logging): add persistent JSON Lines audit journal`,
7 файлов, `542 insertions(+), 32 deletions(-)`.

## Выполненные проверки

Все WSL-команды запускались из PowerShell с CWD
`D:\Antigravity\EquipmentDocumentationRegistry` (корень репозитория).

| # | Команда | CWD | Код выхода | Существенный результат | Лог / артефакт |
| --- | --- | --- | --- | --- | --- |
| 1 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_logging_config.py'` | корень | 0 | `23 passed, 1 warning in 3.88s`; предупреждение — стороннее `StarletteDeprecationWarning` | вывод команды в сессии исполнителя |
| 2 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | 0 | `3400 passed, 1 warning in 445.49s (0:07:25)`; 0 failed; 3377 + 23 новых | вывод команды в сессии исполнителя |
| 3 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | 0 | `12` | вывод команды в сессии исполнителя |
| 4 | `git show --stat --oneline HEAD`; `git show --name-only --format= HEAD` | корень | 0 | `5b9d916 feat(logging): add persistent JSON Lines audit journal`; 7 разрешённых файлов; evidence отсутствует | вывод команды в сессии исполнителя |
| 5 | `git diff --name-only 49b79f0..HEAD` | корень | 0 | только `.env.example`, `app/config.py`, `app/logging_config.py`, `app/main.py`, `tests/test_logging_config.py`, `docs/PROJECT_STATUS.md`, `docs/adr/ADR-009-document-attachments.md` | вывод команды в сессии исполнителя |
| 6 | `git diff --name-only 5e9e626..HEAD -- app/services/file_service.py app/api/files tests/test_file_service.py 'tests/test_files_*'` | корень | 0 | пустой вывод — источники аудита не изменены | вывод команды в сессии исполнителя |
| 7 | `git diff --name-only 5e9e626..HEAD` | корень | 0 | наши 7 файлов плюс `ROADMAP.md`, `docs/tasks/TASK-MVP-01.md`, `docs/workflow/HISTORY.md`, `docs/workflow/STATE.md` из коммитов координатора `6e5d4ef` и `49b79f0` | вывод команды в сессии исполнителя |
| 8 | `git check-ignore -v storage/logs/app.log`; `git ls-files '*.log'` | корень | 0 | `.gitignore:36:storage/	storage/logs/app.log`; список отслеживаемых `*.log` пуст (0) | вывод команды в сессии исполнителя |
| 9 | `git diff --check` | корень | 0 | ошибок пробелов нет | вывод команды в сессии исполнителя |
| 10 | `git status --porcelain=v1 --untracked-files=all` после коммита | корень | 0 | до создания evidence — пусто; после — только `?? docs/workflow/evidence/TASK-MVP-01-C1.md` | вывод команды в сессии исполнителя |

## Покрытие критериев приёмки

Исполнитель не присваивает проектный PASS; статусы ниже — фактические
результаты проверок, решение принимает ревьюер.

| Критерий | Статус | Чем подтверждено |
| --- | --- | --- |
| AC-001 | done | `app/config.py`: `LOG_FILE` default `storage/logs/app.log`, пустое/пробельное значение отклоняется; `.env.example` документирует параметр; проверки 1 (23 passed) и 4–5 |
| AC-002 | done | `TestJsonLinesFormat`: один JSON-объект на строку, UTF-8, append, `timestamp` с UTC-смещением парсится `datetime.fromisoformat`, поля `level`, `logger`, `message`; многострочный текст остаётся одной строкой |
| AC-003 | done | `TestAuditFields`: все шесть полей при наличии; отсутствующие и `None` не добавляются |
| AC-004 | done | `TestRestart`: два независимых процесса `sys.executable` дописывают две строки в один файл, первая сохраняется |
| AC-005 | done | `TestNoSensitiveData`: `secret`, `error_text`, `raw_error` и текст исключения с traceback не попадают в файл |
| AC-006 | done | `TestHandlerLifecycle`: повторный configure — один обработчик и две строки; смена пути — замена обработчика; shutdown закрывает поток и снимает обработчик, новые записи не пишутся |
| AC-007 | done | `TestApplicationLifespan`: `TestClient(app)` в контексте с `LOG_FILE` через env; запись `app.*` появляется в файле, после выхода обработчик снят |
| AC-008 | done | проверка 6: diff по `app/services/file_service.py`, `app/api/files`, `tests/test_file_service.py`, `tests/test_files_*` пуст |
| AC-009 | done | проверка 8: `storage/logs/app.log` игнорируется `.gitignore:36 storage/`; отслеживаемых `*.log` нет |
| AC-010 | done | ADR-009: статус постоянного журнала, путь/формат, открытый вопрос о форме записи (способ выборки не определён); `PROJECT_STATUS.md`: постоянный журнал, 3400 passed, ограничение 25 снято |
| AC-011 | done | проверки 1–3: 23 новых теста, полный прогон `3400 passed, 0 failed`, миграций 12 |
| AC-012 | done | этот файл: команды, CWD, exit code, результаты, commit hash; в коммит `5b9d916` не входит (проверка 4, 10) |

## Известные ограничения и остаточные риски

- Журнал пишется в локальный файл без ротации; инструмента чтения, поиска и
  сверки журнала нет — это зафиксировано открытым вопросом ADR-009.
- Форматтер пишет только разрешённые скалярные поля аудита; произвольные
  `extra`, `str(error)` и traceback отбрасываются сознательно.
- Полный `pytest` создаёт `storage/logs/app.log` через lifespan `TestClient` в
  существующих HTTP-тестах; файл исключён Git (`storage/`) и не коммитился.
- После полного прогона изменялась только документация (`.env.example`,
  ADR-009, `PROJECT_STATUS.md`); исполняемый код и тесты не менялись.
- Коммит локальный; push/merge/deploy не выполнялись.
- Предупреждение прогона — стороннее: `StarletteDeprecationWarning` о `httpx`
  в `starlette.testclient`.

## Ограничения доступа

Нет. Все необходимые проверки выполнены; отказов разрешений, недоступных
ресурсов и ошибок окружения не было.
