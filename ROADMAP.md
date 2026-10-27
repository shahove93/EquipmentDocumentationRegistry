# ROADMAP — Equipment Documentation Registry

Версия согласуемого объёма: 1.3. MVP + Batch завершён; добавлен утверждённый
пользователем этап устанавливаемой локальной поставки Windows.
Общее состояние: утверждённые TASK выполнены локально; TASK-WINDOWS-LOCAL-01 принят по C1 и дополнению G01/G02 PASS. Внешняя публикация не выполнялась.

## Последовательность

| Порядок | TASK | Результат | Предшественники | Критерий | Риск | Статус |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | [TASK-MVP-00](docs/tasks/TASK-MVP-00.md) | Frontend baseline и исходная проверка проекта | — | `ee4e699`; 3377 backend tests; frontend build | R1 | PASS (2026-10-22) |
| 2 | [TASK-MVP-01](docs/tasks/TASK-MVP-01.md) | Постоянный журнал компенсаций и неизвестных исходов (ADR-009) | MVP-00 | Журнал переживает перезапуск; тесты | R1 | PASS (2026-10-22, `5b9d916`) |
| 3 | [TASK-MVP-02](docs/tasks/TASK-MVP-02.md) | Report-only сверка осиротевших файлов (ADR-009) | MVP-01 | Отчёт о blob без строки `files`; тесты | R2 | PASS (2026-10-23, `fde5406`) |
| 4 | [TASK-MVP-03](docs/tasks/TASK-MVP-03.md) | SHA-256 при скачивании и индекс `ix_files_document_id_id` | MVP-02 | Сверка данных и миграция | R2 | PASS (2026-10-25, `6827ed3`) |
| 5 | [TASK-MVP-04](docs/tasks/TASK-MVP-04.md) | BatchService и Batch API без удаления | MVP-03 | CRUD без DELETE/PUT, схемы, тесты, OpenAPI | R2 | PASS (2026-10-26, `0db1f9e`) |
| 6 | TASK-MVP-05 | Интерфейс партий и сквозной сценарий | MVP-04 | `typecheck`/`build`; создать партию, приложить документ, привязать, проверить, открыть историю | R1 | PASS A2/C1 Sol medium; A1 FAIL/FAIL preserved |
| 7 | TASK-MVP-06 | Финальная приёмка этапа | MVP-05 | Полный `pytest`, frontend `typecheck`/`build`, Codex stage acceptance, `FINAL-REPORT` | Stage | PASS / COMPLETE; FINAL-REPORT,2026-10-27 |
| 8 | [TASK-WINDOWS-LOCAL-01](docs/tasks/TASK-WINDOWS-LOCAL-01.md) | Устанавливаемый локальный режим Windows x64 с базой и файлами на одном компьютере | MVP-06 | Чистая установка, запуск через ярлык, локальный доступ, сохранность, backup/restore, обновление и удаление без потери данных | R2 | PASS C1 + G01/G02 supplement (2026-10-27); clean Win11, Win10 NOT_RUN |

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


2026-10-26 C2 final settlement: TASK-MVP-05 FAIL, F-01 MAJOR remains (API-invalid positive CRUD quantities and mutable historical mock responses); F02-F04 closed. Full reviews2/2 exhausted for A1; TASK-MVP-06 not started. Cumulative actual28965861 input, calls8 settled, accounting-only authority unchanged. See docs/workflow/reviews/TASK-MVP-05-C2.md and STATE/HISTORY. Stop without further fixes/review/commit/push.

2026-10-26 MVP05_C3_A2_AUTHORIZED_20261026: C3 read-only RCA complete; A2 contract-enforcing immutable-wire evidence approach, same frozen scope. Luna medium then Sol medium review1/2; FAIL stops, no automatic C2/A3. Historical28965861 input/calls8 preserved, accounting-only. See docs/tasks/TASK-MVP-05-A2-C1.md. No push/deploy.

2026-10-26 A2/C1 routed PASS by independent Sol medium: all AC/F closed,46 A2+139 inherited hashes matched. Historical A1 failures preserved; cumulative42659624 input/calls10. MVP-06/stage acceptance not started. Local scoped product commit permitted, no push/deploy.
MVP-05 local delivery commit: 06f58065022db9c58524909027ddc2d454f7071f (eight reviewed frontend files); no push/deploy.

MVP-06 Stage execution under existing v1.2 approval: frozen docs/tasks/TASK-MVP-06.md; baseline06f58065022db9c58524909027ddc2d454f7071f unpushed. Luna medium checks-only, separate Codex acceptance after evidence, FINAL-REPORT only after PASS. No new scope/approval/product edits/commit/push/deploy.


MVP-06 checks completed19:05Z: pytest3771passed/1warning; Node24.22.0 typecheck/build0; Alembic e4b8c2d16a70(head),13 migrations. Source190 unchanged at06f58065022db9c58524909027ddc2d454f7071f. ST006 separate acceptance pending; no stage PASS/FINAL-REPORT. Stage actual2625483, retained ledger45285107input/calls11.



2026-10-27 Stage Astra high PASS ST001..006; FINAL-REPORT closes ST007. Approved local MVP+Batch COMPLETE at06f58065022db9c58524909027ddc2d454f7071f; MINOR MVP06-ST-001 documentation drift retained, MOCK limitation explicit. See docs/workflow/FINAL-REPORT.md. Retained ledger48229838input/12calls, historical failures preserved. No new commit/push/merge/deploy.
