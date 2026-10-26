# Текущая сводка workflow

- 2026-10-26: MVP-00…04 имеют routed PASS (5/7). MVP-04 AC-001…010 PASS;
  полный backend: 3771 passed, 1 warning. Независимое R2 evidence review
  закрыто; см. [финальный отчёт](reviews/TASK-MVP-04-evidence-final.md).
- Product commit: `0db1f9e` (`Add Batch schemas, service and API`), 17 файлов.
  Он включает Batch schemas/service/API/tests и обновление `PROJECT_STATUS.md`.
- Workflow/docs/evidence commit: `96e81dc` (`docs: retire Nemotron workflow and
  record MVP-04`), 63 файла. Он содержит актуальные правила Codex, историю и
  evidence MVP-04, а также снятие TASK-WF-01.
- Пользователь отозвал Nemotron: ADR-011 withdrawn, TASK-WF-01 withdrawn from
  future execution (historical result BLOCKED/NOT_ACCEPTED сохраняется).
  Активный координатор проекта — Codex; маршрутизация: [MODEL-ROUTING.md](MODEL-ROUTING.md).
- Текущий roadmap v1.2: следующий этап MVP-05 (Batch frontend), затем MVP-06
  (полная приёмка и FINAL-REPORT). MVP-05 ещё не запущен.
- Codex usage по завершении MVP-04: 12,285,453 / 12,400,000 input; 5/5 calls,
  review2/2. Все попытки и перерасходы отражены в [HISTORY.md](HISTORY.md).
- Ветка `main` синхронизирована с `origin/main` fast-forward push до `96e81dc`.
  Force-push, merge и deployment не выполнялись.
- Рабочих writers/reviewers нет. Не запускать Nemotron и не возобновлять
  TASK-WF-01. Не менять продуктовые требования и границы MVP.

Источники: [APPROVALS.md](APPROVALS.md), [ROADMAP.md](../../ROADMAP.md),
[PROJECT_STATUS.md](../PROJECT_STATUS.md), [MVP-04 evidence](evidence/TASK-MVP-04-ALL-final.txt).
