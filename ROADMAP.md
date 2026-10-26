# ROADMAP — Equipment Documentation Registry

Версия согласуемого объёма: 1.2. Продуктовый объём MVP + Batch не меняется;
изменено только управление workflow по решению пользователя от 2026-10-26.
Общее состояние: RUNNING.

## Последовательность

| Порядок | TASK | Результат | Предшественники | Критерий | Риск | Статус |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [TASK-MVP-00](docs/tasks/TASK-MVP-00.md) | Frontend baseline и исходная проверка проекта | — | `ee4e699`; 3377 backend tests; frontend build | R1 | PASS (2026-10-22) |
| 2 | [TASK-MVP-01](docs/tasks/TASK-MVP-01.md) | Постоянный журнал компенсаций и неизвестных исходов (ADR-009) | MVP-00 | Журнал переживает перезапуск; тесты | R1 | PASS (2026-10-22, `5b9d916`) |
| 3 | [TASK-MVP-02](docs/tasks/TASK-MVP-02.md) | Report-only сверка осиротевших файлов (ADR-009) | MVP-01 | Отчёт о blob без строки `files`; тесты | R2 | PASS (2026-10-23, `fde5406`) |
| 4 | [TASK-MVP-03](docs/tasks/TASK-MVP-03.md) | SHA-256 при скачивании и индекс `ix_files_document_id_id` | MVP-02 | Сверка данных и миграция | R2 | PASS (2026-10-25, `6827ed3`) |
| 5 | [TASK-MVP-04](docs/tasks/TASK-MVP-04.md) | BatchService и Batch API без удаления | MVP-03 | CRUD без DELETE/PUT, схемы, тесты, OpenAPI | R2 | PASS (2026-10-26, `0db1f9e`) |
| 6 | TASK-MVP-05 | Интерфейс партий и сквозной сценарий | MVP-04 | `typecheck`/`build`; создать партию, приложить документ, привязать, проверить, открыть историю | R1 | PLANNED; ещё не начат |
| 7 | TASK-MVP-06 | Финальная приёмка этапа | MVP-05 | Полный `pytest`, frontend `typecheck`/`build`, Codex stage acceptance, `FINAL-REPORT` | Stage | PLANNED |

## Рабочий процесс

- Codex координирует Orca Run; отдельные Codex workers реализуют TASK и
  проводят независимое ревью по классу риска. Маршрутизация моделей находится
  в [docs/workflow/MODEL-ROUTING.md](docs/workflow/MODEL-ROUTING.md).
- Nemotron не используется. Операционный TASK-WF-01 снят с исполнения по
  решению пользователя; он не является предшественником или блокировщиком
  продуктовых MVP. ADR-011 и отчёты WF-01 сохранены как история.
- Следующий TASK запускается только после routed PASS предыдущего. Статус
  исполнителя `worker_done` сам по себе не является приёмкой.
- Ветка `main`. Локальные коммиты после PASS разрешены. Push, merge и
  deployment требуют отдельного решения пользователя. Для текущей публикации
  этапа разрешён обычный fast-forward push `main` в `origin`.
- Backend/pytest выполняются в WSL Ubuntu с `.venv/bin/python`; PostgreSQL 18
  должен быть онлайн. Frontend использует WSL и nvm Node.js v24.22.0.
- Полная финальная проверка: `pytest -q`, frontend `typecheck` и `build`,
  Alembic head и количество миграций. Подтверждённые проверки не повторять без
  основания по evidence/review policy.
- При исчерпании бюджета провайдера зависимая цепочка становится BLOCKED до
  явного решения пользователя, включая после автосброса. Не сбрасывать и не
  обходить лимиты сменой аккаунта, тарифа или сессии.

## Вне текущего объёма

Аутентификация/авторизация и публичное развёртывание; связи документов с
`Product`/`Batch` (семантика не утверждена); автоматическое удаление
осиротевших blob; индексы `pg_trgm`/GIN и журнал изменений привязок;
каскадное удаление `ProductVariant`; удаление документов и пагинация истории.
Эти изменения требуют отдельного решения пользователя и, при необходимости,
нового ADR.

## История решения

ROADMAP v1.1 включал TASK-WF-01 — эксперимент с Nemotron-координатором. После
неудачных запусков пользователь отозвал это направление. Попытки и их
BLOCKED/FAIL evidence не удалены: см. [ADR-011](docs/adr/ADR-011-local-nemotron-coordinator.md),
[TASK-WF-01](docs/tasks/TASK-WF-01.md) и
[docs/workflow/HISTORY.md](docs/workflow/HISTORY.md). Изменение v1.2 касается
только workflow; продуктовые критерии и последовательность MVP-00…06 сохранены.

Текущий статус, разрешения и evidence: [docs/workflow/STATE.md](docs/workflow/STATE.md),
[docs/workflow/APPROVALS.md](docs/workflow/APPROVALS.md), [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).
