# TASK-MVP-00 / C1 — пакет доказательств

## Идентификация

- TASK: TASK-MVP-00 — Baseline: frontend, проверки, документация.
- Подход / цикл: A1 / C1.
- Класс риска: R1.
- Ревизия: базовый HEAD `3529aa1`; результат — коммит `ee4e69907d46116b1eab403d279a06a81b84d1d2`.
- Run / Task / Dispatch Orca: `run_68046cea3eb4` / `task_4d33d01ce1fa` /
  `ctx_85adc7c6460b`.
- Рабочая область: `D:\Antigravity\EquipmentDocumentationRegistry`
  (`/mnt/d/Antigravity/EquipmentDocumentationRegistry`), ветка `main`.
- Исполнитель: отдельный OpenCode-исполнитель (Orca worker,
  `term_63602cf0-9557-4652-a116-a2bcd463b475`).
- Дата: 2026-10-22.

## Что изменено

Закоммичен существующий frontend без изменения кода; `.gitignore` дополнен
исключением `node_modules/`; `docs/PROJECT_STATUS.md` приведён к фактическому
baseline (frontend, контрольные точки, окружение, следующий этап). Продуктовый
код backend, миграции и тесты не изменялись.

| Файл | Назначение изменения |
| --- | --- |
| `frontend/**` (46 файлов) | фиксация существующего React 19 + Vite + TypeScript интерфейса |
| `.gitignore` | исключение `node_modules/` (каталог `dist/` уже исключён) |
| `docs/PROJECT_STATUS.md` | дата фиксации, frontend typecheck/build, окружение, фронтенд и карта проекта, актуальный следующий этап |

Коммит: `ee4e699` — `chore(baseline): add frontend and actualize project status`,
48 файлов, `8832 insertions(+), 12 deletions(-)`.

## Выполненные проверки

Все WSL-команды запускались из PowerShell с CWD
`D:\Antigravity\EquipmentDocumentationRegistry` (корень репозитория).

| # | Команда | CWD | Код выхода | Существенный результат | Лог / артефакт |
| --- | --- | --- | --- | --- | --- |
| 1 | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && node --version && npm --version && npm run typecheck'` | корень (команда выполняется в `frontend/`) | 0 | `v24.22.0`; `11.19.1`; `tsc --noEmit` без вывода и ошибок | вывод команды в сессии исполнителя |
| 2 | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'` | корень (команда выполняется в `frontend/`) | 0 | `vite v8.3.4`, 60 модулей; `dist/index.html` 0.50 kB, CSS 11.32 kB, JS 345.08 kB; `✓ built in 527ms`; `frontend/dist/index.html` существует | вывод команды в сессии исполнителя |
| 3 | Полный `pytest -q` | корень | не перезапускался (reuse) | Переиспользовано подтверждённое значение `3377 passed, 1 warning` на `ba6c06e`; backend-файлы с тех пор не изменялись — см. проверки 4–6 | `docs/workflow/STATE.md`, контрольная точка `ba6c06e` |
| 4 | `git diff --name-only ba6c06e..HEAD -- app alembic tests` | корень | 0 | пустой вывод — backend не изменён между `ba6c06e` и `3529aa1` | вывод команды в сессии исполнителя |
| 5 | `git diff --name-only HEAD -- app alembic tests` и `git status --porcelain --untracked-files=all -- app alembic tests` | корень | 0 | пустой вывод — в рабочем дереве backend-файлы не изменены | вывод команды в сессии исполнителя |
| 6 | `git show --stat --oneline HEAD` | корень | 0 | `ee4e699 chore(baseline): add frontend and actualize project status`; 48 файлов: `frontend/**`, `.gitignore`, `docs/PROJECT_STATUS.md` | вывод команды в сессии исполнителя |
| 7 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic current'` | корень | 0 | `a3f1c72d5b90 (head)` | вывод команды в сессии исполнителя |
| 8 | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | корень | 0 | `12` | вывод команды в сессии исполнителя |
| 9 | `git check-ignore -v frontend/node_modules frontend/dist .env .venv storage` | корень | 0 | все пять путей игнорируются: `.gitignore:22 node_modules/`; `.gitignore:19 dist/`; `.gitignore:2 .env`; `.gitignore:8 .venv/`; `.gitignore:36 storage/` | вывод команды в сессии исполнителя |
| 10 | `git ls-files frontend` | корень | 0 | 46 файлов; совпадений `node_modules` и `/dist/` нет | вывод команды в сессии исполнителя |
| 11 | `git status --porcelain=v1 --untracked-files=all` (после коммита) | корень | 0 | только `M docs/workflow/HISTORY.md` и `M docs/workflow/STATE.md` — рабочие правки координатора, не входят в коммит; frontend, `.gitignore`, `PROJECT_STATUS.md` закоммичены | вывод команды в сессии исполнителя |

## Покрытие критериев приёмки

Исполнитель не присваивает проектный PASS; статусы ниже — фактические
результаты проверок, решение принимает ревьюер.

| Критерий | Статус | Чем подтверждено |
| --- | --- | --- |
| AC-001 | done | проверка 1: `npm run typecheck`, exit 0, ошибок нет |
| AC-002 | done | проверка 2: `npm run build`, exit 0; `frontend/dist/index.html` создан; `dist/` игнорируется (проверка 9) и не входит в `git ls-files` (проверка 10) |
| AC-003 | done (reuse) | проверки 4–6: backend-файлы не изменялись; переиспользовано `3377 passed, 1 warning` на `ba6c06e` |
| AC-004 | done | проверки 9–10: `frontend/node_modules`, `frontend/dist`, `.env`, `.venv`, `storage` игнорируются; в индексе только 46 файлов frontend без `node_modules`/`dist` |
| AC-005 | done | проверки 6, 11: один коммит `ee4e69907d46116b1eab403d279a06a81b84d1d2` в `main` с `frontend/**`, `.gitignore`, `docs/PROJECT_STATUS.md` |
| AC-006 | done | `docs/PROJECT_STATUS.md`: дата 2026-10-22, `3377 passed`, Alembic head `a3f1c72d5b90`, 12 миграций, frontend typecheck/build; утверждений о невыполненных проверках нет |
| AC-007 | done | проверки 4–5: diff по `app`, `alembic`, `tests` пуст |
| AC-008 | done | этот файл: команды, CWD, exit codes, результаты и commit hash |

## Известные ограничения и остаточные риски

- Runtime-frontend (dev-сервер и взаимодействие с запущенным backend) не
  проверялся: TASK требует только `typecheck` и production build.
- Коммит локальный; push/merge/deploy не выполнялись.
- Повторный полный `pytest` не запускался: по условию TASK при неизменном
  backend допускается переиспользование доказательства `3377 passed, 1 warning`
  на `ba6c06e`; неизменность подтверждена diff-проверками 4–5.
- `docs/workflow/HISTORY.md` и `docs/workflow/STATE.md` были изменены
  координатором параллельно; исполнитель их не изменял и не коммитил.

## Ограничения доступа

Нет. Все необходимые проверки выполнены; отказов разрешений, недоступных
ресурсов и ошибок окружения не было.
