# TASK-MVP-00 — Baseline: frontend, проверки, документация

Статус: PASS. Требования: VISION.md, ARCHITECTURE.md, ROADMAP.md,
ADR-005…010. Этап ROADMAP: 1.
Предшественники с обязательным PASS: нет.
Класс риска: R1 (обоснование: механическая фиксация существующего frontend,
проверки сборки и актуализация документации; backend не меняется).
Маршрут приёмки: независимый OpenCode-ревьюер. Ревьюер: отдельный worker Orca.

## Цель и область

Зафиксировать фактический baseline проекта: существующий frontend должен быть
закоммичен, проверки frontend и backend подтверждены, `PROJECT_STATUS.md`
приведён в соответствие с фактическим состоянием. Продуктовое поведение не
меняется.

Целевые компоненты/файлы: `frontend/**` (только если проверка выявит ошибку),
`.gitignore`, `docs/PROJECT_STATUS.md`, `docs/workflow/evidence/TASK-MVP-00-C1.md`.
Разрешено изменять: перечисленные файлы; commit в `main`.
Не затрагивать: `app/**`, `alembic/**`, `tests/**`, `docs/adr/**`, `VISION.md`,
`ARCHITECTURE.md`, `ROADMAP.md`, `AGENTS.md`, `docs/workflow/APPROVALS.md`,
`docs/workflow/STATE.md`, `docs/workflow/HISTORY.md`.
Инварианты: ADR-005…010; локальный API; никаких push/merge/deploy.

## Критерии приёмки

Чек-лист заморожен координатором до диспатча и передан исполнителю и ревьюеру
отдельно. Ревьюер проверяет строго по этому списку.

| ID | Критерий | Способ независимой проверки | Severity |
| --- | --- | --- | --- |
| AC-001 | Frontend `typecheck` проходит в WSL | `npm run typecheck`; exit 0, вывод без ошибок | BLOCKER |
| AC-002 | Frontend production build проходит | `npm run build`; exit 0, `frontend/dist/index.html` создан, dist не коммитится | BLOCKER |
| AC-003 | Backend-контрольная точка подтверждена | Полный `pytest -q`: `3377 passed, 1 warning` на ревизии без изменений backend; либо повторный прогон, если backend изменён | BLOCKER |
| AC-004 | Секреты и артефакты не попали в Git | `git ls-files` не содержит `frontend/node_modules`, `frontend/dist`, `.env`, `.venv`, `storage`; `git check-ignore` подтверждает | BLOCKER |
| AC-005 | Baseline закоммичен в `main` | Один коммит с frontend, `.gitignore`, `PROJECT_STATUS.md`; hash сообщён; `git show --stat` подтверждает состав | BLOCKER |
| AC-006 | `PROJECT_STATUS.md` соответствует фактам | Дата 2026-10-22, `3377 passed`, Alembic head `a3f1c72d5b90`, 12 миграций, frontend typecheck/build; нет утверждений о невыполненных проверках | MAJOR |
| AC-007 | Backend не изменён | `git diff --name-only <baseline>..HEAD -- app alembic tests` пуст | BLOCKER |
| AC-008 | Evidence-пакет заполнен | `docs/workflow/evidence/TASK-MVP-00-C1.md` содержит команды, CWD, exit code, результаты, commit hash | MAJOR |

## Команды проверок

| Команда | CWD | Ожидаемый результат |
| --- | --- | --- |
| `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'` | корень | exit 0 |
| `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'` | корень | exit 0; dist создан |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | корень | `3377 passed, 1 warning` (или больше при неизменном backend) |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic current'` | корень | `a3f1c72d5b90 (head)` |
| `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | `12` |
| `git status --porcelain`; `git show --stat --oneline HEAD`; `git ls-files frontend` | корень | ожидаемый состав коммита |

## Текущее задание OpenCode

- Рабочая ветка/worktree: `main`, текущий workspace.
- Базовая ревизия: HEAD после коммита координатора с workflow-документами
  (зафиксирован в STATE); исходные изменения — `.gitignore` и untracked
  `frontend/`, сохранены.
- Подход / цикл: A1 / C1.
- Метод: не менять backend; проверить frontend; актуализировать
  `PROJECT_STATUS.md`; закоммитить `frontend/`, `.gitignore`,
  `PROJECT_STATUS.md` в `main`; evidence-файл не коммитить — координатор
  закоммитит его после приёмки.
- Замечания для исправления: нет.
- Формат результата: изменения, выполненные проверки, commit hash, ограничения
  и реальный `worker_done` по текущему preamble Orca; не присваивать PASS.

## Приёмка

Решение: **PASS**. Автор решения: независимый OpenCode-ревьюер
(`task_67d2d98ace9c` / `ctx_b4d619f7a180`). Проверенная ревизия: `ee4e699`
(diff `3529aa1..ee4e699`). Сводка/счётчики: ../workflow/STATE.md.
История: ../workflow/HISTORY.md. Подробный отчёт:
../workflow/reviews/TASK-MVP-00.md. Пакет доказательств:
../workflow/evidence/TASK-MVP-00-C1.md. Следующий TASK: TASK-MVP-01.
