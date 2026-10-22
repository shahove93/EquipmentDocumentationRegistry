# ROADMAP — Equipment Documentation Registry

Версия согласуемого объёма: 1.0 (утверждена 2026-10-22).
Состояние выполнения: RUNNING.
Связанные документы: [VISION.md](VISION.md), [ARCHITECTURE.md](ARCHITECTURE.md),
[docs/adr/README.md](docs/adr/README.md), [docs/workflow/APPROVALS.md](docs/workflow/APPROVALS.md).

## Последовательность

| Порядок | TASK | Результат и требования | Предшественники | Критерий этапа | Риск | Статус |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [TASK-MVP-00](docs/tasks/TASK-MVP-00.md) | Baseline: frontend закоммичен, проверки typecheck/build зелёные, backend-контрольная точка зафиксирована, `PROJECT_STATUS` актуализирован | Нет | Коммит в `main`; `3377 passed`; frontend build; нет изменений backend | R1 | IN_PROGRESS |
| 2 | TASK-MVP-01 | Постоянный журнал компенсаций и неизвестных исходов (ADR-009) | TASK-MVP-00 PASS | Журнал переживает перезапуск; тесты | R1 | PLANNED |
| 3 | TASK-MVP-02 | Сверка осиротевших файлов (ADR-009) | TASK-MVP-01 PASS | Операция сверки + тесты; отчёт об осиротевших blob | R2 | PLANNED |
| 4 | TASK-MVP-03 | Сверка SHA-256 при скачивании + миграция `ix_files_document_id_id` | TASK-MVP-02 PASS | Тесты несовпадения/совпадения SHA-256; Alembic head +1 | R2 | PLANNED |
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

## Вне утверждённого объёма

Аутентификация/авторизация, публичное развёртывание, привязка документов к
`Product`/`Batch`, индексы `pg_trgm`/GIN, журнал изменений привязок, каскадное
удаление `ProductVariant`, удаление документов. Эти пункты требуют отдельного
решения пользователя и, при необходимости, нового ADR.

После утверждения этого ROADMAP координатор автоматически диспатчит TASK-MVP-00
и переходит дальше после PASS по маршруту класса риска. Завершение исполнителя
недостаточно; итоговая приёмка этапа принадлежит Codex. FAIL не пропускается;
BLOCKED останавливает зависимую цепочку. Подробное состояние:
[docs/workflow/STATE.md](docs/workflow/STATE.md).
