# Независимое ревью TASK-MVP-01

Ревьюер: отдельный OpenCode worker Orca
(`task_1d61cb577817` / `ctx_7ef3ef86a791`,
`term_36209588-e15f-4904-8d3d-7296271607c8`). Маршрут: R1 (независимый
OpenCode). Решение ревью: **PASS**. Это вердикт по TASK-MVP-01, а не проектный
PASS: фиксацию в STATE/HISTORY/ROADMAP выполняет координатор.

## Подход A1 / цикл C1 / общий цикл 1

- Вид: initial-review.
- Dispatch: `ctx_7ef3ef86a791`; task `task_1d61cb577817`; run `run_68046cea3eb4`.
- Проверенный diff реализации: `49b79f0..5b9d916`; итоговый коммит
  `5b9d916ed933214f3fbfbf3cef097bea31893069`. Итоговое состояние кода —
  `5b9d916`: коммит `9254b4d` после него меняет только
  `docs/workflow/HISTORY.md` и `docs/workflow/STATE.md`.
- Baseline: `5e9e626` (PASS TASK-MVP-00); dispatch baseline `6e5d4ef` /
  `49b79f0`. Общий диапазон `5e9e626..5b9d916` дополнительно содержит
  workflow-документы координатора (`ROADMAP.md`, `docs/tasks/TASK-MVP-01.md`,
  `docs/workflow/HISTORY.md`, `docs/workflow/STATE.md`); продуктовый код —
  только 7 файлов коммита `5b9d916`.
- Чек-лист: [TASK-MVP-01](../tasks/TASK-MVP-01.md), AC-001…AC-012; не
  расширялся.
- Пакет: [evidence/TASK-MVP-01-C1.md](../evidence/TASK-MVP-01-C1.md)
  (untracked).
- Слоты полных ревью: 1 из 2 использован; FAIL: 0.

## Сверка критериев приёмки

| Критерий | Проверенный артефакт/факт | Кто проверял | Результат |
| --- | --- | --- | --- |
| AC-001 | `app/config.py`: `DEFAULT_LOG_FILE = "storage/logs/app.log"`, поле `LOG_FILE` и валидатор, отклоняющий пустое/пробельное значение; `.env.example` документирует `LOG_FILE` | Ревьюер (diff); исполнитель (23 теста) | PASS |
| AC-002 | `app/logging_config.py`: `JsonLinesFormatter` — один JSON-объект на строку, `ensure_ascii=False`, `FileHandler(mode="a", encoding="utf-8")`; поля `timestamp` (UTC, `+00:00`), `level`, `logger`, `message`; `TestJsonLinesFormat` парсит строки `json.loads` и `datetime.fromisoformat` | Ревьюер (код/тесты); исполнитель (прогон) | PASS |
| AC-003 | `AUDIT_FIELDS` и фильтрация в `JsonLinesFormatter`: шесть полей пишутся только при наличии; `TestAuditFields` проверяет полный набор, отсутствие полей и `None` | Ревьюер (код/тесты); исполнитель (прогон) | PASS |
| AC-004 | `TestRestart`: `subprocess.run` дважды запускает `sys.executable` с `RESTART_SCRIPT`, оба процесса дописывают в один файл; обе строки сохранены | Ревьюер (тест); исполнитель (прогон) | PASS |
| AC-005 | Форматтер не использует `record.exc_info`, `exc_text` и неизвестные `extra`; `TestNoSensitiveData` передаёт `secret`, `error_text`, `raw_error` и исключение и проверяет отсутствие значений/ключей/трейсбека | Ревьюер (код/тесты); исполнитель (прогон) | PASS |
| AC-006 | `configure_logging` идемпотентен по пути, заменяет обработчик при другом пути; `shutdown_logging` снимает, закрывает его и возвращает уровень; `TestHandlerLifecycle` подтверждает один обработчик, две строки, `stream is None` и отсутствие записей после close | Ревьюер (код/тесты); исполнитель (прогон) | PASS |
| AC-007 | `app/main.py`: `lifespan` вызывает `configure_logging(get_settings().LOG_FILE)` на старте и `shutdown_logging()` в `finally`; `TestApplicationLifespan` с `TestClient(app)` и `LOG_FILE` через env проверяет запись `app.lifespan` и снятие обработчика | Ревьюер (diff/тест); исполнитель (прогон) | PASS |
| AC-008 | `git diff --name-only 5e9e626..5b9d916 -- app/services/file_service.py app/api/files tests/test_file_service.py 'tests/test_files_*'` — пусто; источники аудита не изменены | Ревьюер (фактический diff) | PASS |
| AC-009 | `git check-ignore -v storage/logs/app.log` → `.gitignore:36:storage/`; `git ls-files '*.log'` → пусто | Ревьюер (рабочее дерево) | PASS |
| AC-010 | ADR-009: статус постоянного журнала, путь/формат и открытый вопрос только о способе выборки; `PROJECT_STATUS.md`: постоянный журнал, `3400 passed`, ограничение 25 снято; retrieval-инструмент нигде не заявлен реализованным | Ревьюер (diff документов) | PASS |
| AC-011 | Evidence: новые тесты `23 passed`; полный прогон `3400 passed, 1 warning`, 0 failed (3377 + 23); миграций `12`; независимо: в `tests/` 56 файлов тестов, `alembic/versions/*.py` — 12 | Исполнитель; ревьюер переиспользовал evidence | PASS |
| AC-012 | Evidence содержит команды, CWD (корень), exit codes, результаты и commit hash; `git log --all -- docs/workflow/evidence/TASK-MVP-01-C1.md` пуст, `git status` показывает файл только как `??`; в коммитах `5b9d916` и `9254b4d` его нет | Ревьюер (git) | PASS |

## Самостоятельные проверки ревьюера

Все команды выполнялись из корня
`D:\Antigravity\EquipmentDocumentationRegistry` на рабочем дереве, итоговый
код — `5b9d916` (рабочее дерево чисто, кроме untracked evidence).

| # | Команда | Результат |
| --- | --- | --- |
| 1 | `git show --stat --oneline 5b9d916` | 7 файлов, `542 insertions(+), 32 deletions(-)`; совпадает с evidence |
| 2 | `git diff --name-status 49b79f0..5b9d916` | ровно заявленные 7 файлов: `.env.example`, `app/config.py`, `A app/logging_config.py`, `app/main.py`, `docs/PROJECT_STATUS.md`, `docs/adr/ADR-009-document-attachments.md`, `A tests/test_logging_config.py`; незаявленных файлов нет |
| 3 | `git diff --stat 5b9d916..HEAD` | только `docs/workflow/HISTORY.md`, `docs/workflow/STATE.md` (коммит `9254b4d`); код и тесты после проверенной ревизии не менялись |
| 4 | `git diff --name-only 5e9e626..5b9d916 -- alembic frontend requirements.txt .gitignore app/models app/api app/services` | пусто: миграции, frontend, зависимости, `.gitignore`, модели и сервисы не изменены; `app/main.py` — разрешённое исключение |
| 5 | `git check-ignore -v storage/logs/app.log`; `git ls-files '*.log'` | `.gitignore:36:storage/ storage/logs/app.log`; список отслеживаемых `*.log` пуст |
| 6 | `git log --all --oneline -- docs/workflow/evidence/TASK-MVP-01-C1.md`; `git status --short` | evidence никогда не коммитился; единственная запись — `?? docs/workflow/evidence/TASK-MVP-01-C1.md` |
| 7 | `git ls-files 'tests/test_*.py' \| Measure-Object -Line`; `git ls-files 'alembic/versions/*.py' \| Measure-Object -Line` | 56 файлов тестов; 12 миграций |
| 8 | Поиск по diff `password|secret|token|api[_-]?key|PRIVATE` | только тестовые фикстуры (`example.invalid`, `s3cr3t-token` в негативных проверках, `hunter2` в проверке отсутствия утечки); реальных секретов нет |

Переиспользовано по evidence без перезапуска: новые тесты (`23 passed`),
полный `pytest -q` (`3400 passed, 1 warning in 445.49s`), подсчёт миграций
(`12`), `git diff --check`, состав коммита. Пакет полный и однозначный;
расхождений с фактическим diff не найдено, поэтому тестовые команды не
перезапускались. Пункты 1–8 — самостоятельная сверка фактического diff и
рабочего дерева, требуемая заданием ревью, а не дублирование прогонов.

## Находки

Находок в границах замороженного чек-листа нет: BLOCKER/MAJOR/MINOR/NIT — 0.
Все AC-001…AC-012 подтверждены кодом, тестами и evidence.

## Остаточные риски

- Ротации журнала нет; инструмента чтения, поиска и сверки записей нет — это
  явно зафиксировано в ADR-009 как открытый вопрос, за реализованный
  инструмент не выдаётся.
- `LOG_FILE` — относительный путь по умолчанию (`storage/logs/app.log`),
  разрешается относительно CWD процесса; это согласуется с существующим
  `STORAGE_ROOT` и не противоречит чек-листу.
- Межпроцессная дописываемость проверена двумя последовательными процессами;
  одновременная конкурентная запись многих процессов не тестировалась
  (вне AC-004).
- Полный `pytest` создаёт `storage/logs/app.log` через lifespan существующих
  HTTP-тестов; путь исключён Git, в коммиты не попадает.

## Вердикт

**PASS** по TASK-MVP-01 (A1/C1): все AC-001…AC-012 пройдены, незаявленных
файлов, секретов и изменений источников аудита, миграций, frontend и
зависимостей нет. Координатору: зафиксировать вердикт в STATE/HISTORY,
закоммитить evidence-пакет и переходить к следующему утверждённому TASK.
