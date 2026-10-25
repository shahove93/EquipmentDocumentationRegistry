# ROADMAP — Equipment Documentation Registry

Версия согласуемого объёма: 1.1 (утверждена 2026-10-24; дополнение workflow).
Состояние выполнения: RUNNING.
Связанные документы: [VISION.md](VISION.md), [ARCHITECTURE.md](ARCHITECTURE.md),
[docs/adr/README.md](docs/adr/README.md), [docs/workflow/APPROVALS.md](docs/workflow/APPROVALS.md).

## Последовательность

| Порядок | TASK | Результат и требования | Предшественники | Критерий этапа | Риск | Статус |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [TASK-MVP-00](docs/tasks/TASK-MVP-00.md) | Baseline: frontend закоммичен, проверки typecheck/build зелёные, backend-контрольная точка зафиксирована, `PROJECT_STATUS` актуализирован | Нет | Коммит `ee4e699`; `3377 passed`; frontend build; backend не изменён | R1 | PASS (2026-10-22) |
| 2 | [TASK-MVP-01](docs/tasks/TASK-MVP-01.md) | Постоянный журнал компенсаций и неизвестных исходов (ADR-009) | TASK-MVP-00 PASS | Журнал переживает перезапуск; тесты | R1 | PASS (2026-10-22, `5b9d916`) |
| 3 | TASK-MVP-02 | Сверка осиротевших файлов (ADR-009) | TASK-MVP-01 PASS | Операция сверки + тесты; отчёт об осиротевших blob | R2 | PASS (2026-10-23, `fde5406`) |
| 4 | [TASK-MVP-03](docs/tasks/TASK-MVP-03.md) | Сверка SHA-256 при скачивании + миграция `ix_files_document_id_id` | TASK-MVP-02 PASS | Тесты несовпадения/совпадения SHA-256; Alembic head +1 | R2 | IN_PROGRESS (design complete) |
| 5 | TASK-MVP-04 | `BatchService` + Batch API по образцу справочников (CRUD без delete) + тесты | TASK-MVP-03 PASS | HTTP-операции партий; схемы; тесты; OpenAPI | R2 | PLANNED |
| 6 | TASK-MVP-05 | Завершение frontend: экран партий, сквозной сценарий, приёмка | TASK-MVP-04 PASS | `typecheck`/`build`; сценарий «создать → вложить → привязать → подтвердить → история» | R1 | PLANNED |
| 7 | TASK-MVP-06 | Финальная приёмка этапа: полный `pytest`, frontend build, Codex stage acceptance, `FINAL-REPORT` | TASK-MVP-05 PASS | Все проверки зелёные; отчёт Codex PASS | Stage | PLANNED |

## Условия выполнения

- Рабочая ветка: `main`; локальные коммиты после PASS каждого TASK; push, merge
  и deployment — только по отдельному разрешению.
- Backend-проверки — WSL Ubuntu, `.venv/bin/python`; PostgreSQL 18 онлайн.
- Frontend-проверки — WSL, Node.js nvm `v24.22.0`.
- Полный финальный набор: `pytest -q` (ожидается 3377+ passed), frontend
  `typecheck` и `build`, `alembic current` = head, 12+ миграций.
- Артефакты: TASK-файлы, evidence-пакеты, review-отчёты, STATE/HISTORY,
  FINAL-REPORT; коммиты в `main`.

## Отдельное дополнение workflow — ADR-011

Это дополнение не меняет семизадачный продуктовый объём MVP + Batch. После
независимого R2 PASS по TASK-MVP-03 координатор подготовит отдельный
`TASK-WF-01` на интеграцию локального Nemotron в роль OpenCode-координатора,
заморозит критерии, зарезервирует маршрут и сначала обновит STATE/HISTORY.
TASK-WF-01 выполняется до диспатча TASK-MVP-04; обязательные предшественники —
TASK-MVP-03 PASS и отсутствие незавершённой передачи/активного исполнителя.

Утверждённый результат TASK-WF-01:

1. Новый координатор OpenCode запускается Orca с явной моделью
   `local-nemotron/nemotron-bolt`; фактическая модель подтверждена в launch
   receipt, и координатор привязан к существующему Run.
2. Передача Run проходит без двух одновременно действующих координаторов.
   Координатор читает фактический статус через Orca-инструмент и не принимает
   решения о продвижении очереди по выдуманным данным.
3. Исполнитель сохраняет маршрут `deepseek-v4.1-flash-free`, R1-ревьюер —
   независимый OpenCode `minimax-m3.1-flash-free`, R2/R3 — Codex по
   `routing-and-budget.md`.
4. Глобальная модель OpenCode и другие проекты не меняются. Если локальный
   сервер/модель/инструменты не подтверждены, цепочка получает BLOCKED; тихий
   fallback к облачной модели запрещён.
5. Код и данные продукта не меняются. Синтетическая проверка подтверждает
   маршрутизацию модели, вызов инструмента Orca, локальный zero-cost usage и
   отсутствие передачи координаторской задачи облачному провайдеру.

Текущий TASK-MVP-03 остаётся на исходном R2 review Codex; его чек-лист,
счётчики, исполнитель, Dispatch и состояние не меняются. Сводку workflow и
постановку TASK-WF-01 ведёт OpenCode-координатор.

## Вне утверждённого объёма

Аутентификация/авторизация, публичное развёртывание, привязка документов к
`Product`/`Batch`, индексы `pg_trgm`/GIN, журнал изменений привязок, каскадное
удаление `ProductVariant`, удаление документов. Эти пункты требуют отдельного
решения пользователя и, при необходимости, нового ADR.

Утверждение ROADMAP v1.0 разрешает последовательность TASK-MVP-00…06; дополнение
v1.1 разрешает TASK-WF-01 в указанной точке после PASS TASK-MVP-03. Координатор
переходит дальше только после PASS по маршруту класса риска. Завершение
исполнителя недостаточно; итоговая приёмка этапа принадлежит Codex. FAIL не
пропускается; BLOCKED останавливает зависимую цепочку. Подробное состояние:
[docs/workflow/STATE.md](docs/workflow/STATE.md).
