# Инструкции проекта Equipment Documentation Registry

Применяй `autonomous-development` совместно с `orchestration`.
Skill: `C:/Users/user/.agents/skills/autonomous-development/SKILL.md`.

Codex проектирует, проводит рискованное ревью и итоговую приёмку этапа.
OpenCode-координатор ведёт очередь, TASK, чек-листы, ожидание и документы;
отдельный исполнитель OpenCode реализует код и исправления через Orca.
Утверждение архитектуры и ROADMAP разрешает последовательное выполнение всех
согласованных TASK без дополнительных подтверждений. Подтверждённый объём:
`docs/workflow/APPROVALS.md`.

## Рабочая среда и границы

- Корень репозитория: `D:\Antigravity\EquipmentDocumentationRegistry`
  (в WSL: `/mnt/d/Antigravity/EquipmentDocumentationRegistry`).
- Ветка: `main`; локальные коммиты разрешены по политике APPROVALS.
- Push, merge, deployment и удаление важных данных не разрешены без отдельного
  решения.
- Backend и тесты запускаются в WSL Ubuntu с `.venv/bin/python`; PostgreSQL 18
  должен быть онлайн. Windows-native Python зависимостей проекта не содержит.
- Frontend запускается в WSL через nvm Node.js
  (`/home/djeka/.nvm/versions/node/v24.22.0/bin`), не через Windows `npm`.
- `.env`, `.venv/`, `storage/`, `node_modules/`, `dist/` не коммитить и не
  изменять без задания.
- Продуктовый код пишет только отдельный OpenCode-исполнитель; координатор
  обновляет только документы workflow.

## Проверки

| Проверка | Команда | CWD | Когда обязательна |
| --- | --- | --- | --- |
| Backend, полный набор | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | перед финальной приёмкой; после изменений backend |
| Backend, точечно | та же команда с путями тестов | корень | для текущего TASK |
| Frontend typecheck | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'` | `frontend/` | после изменений frontend |
| Frontend build | та же команда с `npm run build` | `frontend/` | перед приёмкой frontend |
| Alembic current | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic current'` | корень | при изменении миграций |
| Миграции, количество | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | при изменении миграций |

Контрольная точка на 2026-10-22: `3377 passed, 1 warning`; Alembic head
`a3f1c72d5b90`; 12 миграций; frontend `typecheck` и `build` зелёные.

## Исполнение

Источники требований: [VISION.md](VISION.md), [ARCHITECTURE.md](ARCHITECTURE.md),
[ROADMAP.md](ROADMAP.md), [docs/adr/](docs/adr/README.md).
Текущий TASK, подходы, счётчики, замечания и проверки:
[docs/workflow/STATE.md](docs/workflow/STATE.md).
Перед диспатчем и ревью читай `references/routing-and-budget.md`, перед
приёмкой/исправлениями/сменой подхода — `references/review-policy.md` skill
`autonomous-development`.

Координатор переходит к следующему TASK только после PASS по его классу риска;
`worker_done` не является приёмкой. BLOCKED останавливает зависимую цепочку.
Исполнитель OpenCode выполняет только текущее задание, соблюдает живой preamble
Orca, задаёт вопросы координатору и сообщает фактический результат. Он не
присваивает проектный PASS и не запускает следующий TASK.
