# История workflow — только дополнение

Фактические события проекта Equipment Documentation Registry. STATE.md содержит
только текущую сводку; эту историю не удалять и не переписывать после PASS.

## Прогресс ROADMAP

| Время | TASK | Статус/автор вердикта | Предшественники | Подход/циклы/ревью/RCA | Ревизия | Следующее действие |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-22 | TASK-MVP-00 | PASS / независимый OpenCode (R1) | нет | A1/C1; 1 полное ревью; FAIL 0 | baseline `3529aa1`; принято `ee4e699` | TASK-MVP-01 |
| 2026-10-22 | TASK-MVP-01 | PASS / независимый OpenCode (R1) | TASK-MVP-00 PASS | A1/C1; 1 полное ревью; FAIL 0 | baseline `5e9e626`; принято `5b9d916` | TASK-MVP-02 |
| 2026-10-22 | TASK-MVP-02 | IN_PROGRESS / C1 реализован, вердикта нет | TASK-MVP-01 PASS | R2; Codex design завершён; A1/C1 реализован; Codex 1/4 | baseline `7b785f4`; C1 `a2b52a8` | R2-ревью Codex |

## Подходы и первопричины

| TASK/подход | Метод и отличие | Первопричина и почему исправления не помогли | Варианты/выбор | Сохранённые инварианты | План проверки |
| --- | --- | --- | --- | --- | --- |
| TASK-MVP-00/A1 | Зафиксировать существующий frontend и baseline без изменения backend | Не применимо (первый подход) | Единственный согласованный baseline-подход | ADR-005…010; backend не меняется | typecheck, build, pytest, alembic, состав коммита |
| TASK-MVP-01/A1 | JSONL-журнал через `logging` с обработчиком на logger `app`, настройка в lifespan, без изменения источников аудита | Не применимо (первый подход) | Файл append + JSONL; альтернативы (БД, syslog) не нужны для MVP | ADR-009; секреты и `str(error)` не пишутся; API/БД не меняются | новые тесты, полный pytest, git-состав, alembic |

## Замечания и исправления

| ID | TASK/подход/цикл | Критерий/место | Факт/воспроизведение | Ожидание/severity | Задание | Исправление/ревизия | Доказательство закрытия/статус |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | — | Замечаний нет | — | — | — | — |

## Фактически выполненные проверки

| Время | TASK/подход/цикл | Кто выполнил | Ревизия/diff | Команда/CWD | Exit/result | Существенный вывод | Лог/артефакт |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-22 | baseline | OpenCode-координатор | `ba6c06e` + untracked `frontend/` | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | 0 / `3377 passed, 1 warning in 409.01s` | Backend-контрольная точка подтверждена | вывод в сессии; будет перенесён в evidence TASK-MVP-00 |
| 2026-10-22 | baseline | OpenCode-координатор | `ba6c06e` | `source /home/djeka/.nvm/nvm.sh; cd frontend && npm run typecheck` | 0 / без ошибок | Typecheck зелёный | вывод в сессии |
| 2026-10-22 | baseline | OpenCode-координатор | `ba6c06e` | `source /home/djeka/.nvm/nvm.sh; cd frontend && npm run build` | 0 / 60 modules, dist создан | Production build зелёный | вывод в сессии |
| 2026-10-22 | baseline | OpenCode-координатор | `ba6c06e` | `.venv/bin/alembic current` | 0 / `a3f1c72d5b90 (head)` | Alembic head подтверждён | вывод в сессии |
| 2026-10-22 | baseline | OpenCode-координатор | `ba6c06e` | `ls alembic/versions/*.py \| wc -l` | 0 / `12` | Число миграций подтверждено | вывод в сессии |
| 2026-10-22 | TASK-MVP-02/A1/C1 | OpenCode-исполнитель | `a2b52a8` | focused-набор: storage/reconciliation/CLI + file_service/concurrency, WSL, корень | 0 / `377 passed` | focused-набор зелёный | `evidence/TASK-MVP-02-C1.md` |
| 2026-10-22 | TASK-MVP-02/A1/C1 | OpenCode-исполнитель | `a2b52a8` | полный `pytest -q`; реальный CLI `python -m app.reconcile_storage`, WSL, корень | 0 / `3474 passed, 1 warning`; CLI 3/3/0 | полный backend и запуск зелёные | `evidence/TASK-MVP-02-C1.md` |

## Критерии приёмки и бэклог

| Время | TASK | Критерий/находка | Severity/статус | Доказательство | Решение/владелец |
| --- | --- | --- | --- | --- | --- |
| 2026-10-22 | TASK-MVP-00 | AC-001…AC-008 | Проверены, PASS; находок 0 | docs/workflow/reviews/TASK-MVP-00.md | Координатор/ревьюер |
| 2026-10-22 | TASK-MVP-01 | AC-001…AC-012 | Проверены, PASS; находок 0 | docs/workflow/reviews/TASK-MVP-01.md | Координатор/ревьюер |

## Резервы, расход и события

| Время | TASK/подход/цикл/вид | Run/Task/Dispatch | Событие/ревизия | Резерв и факт ревью/RCA/Codex/input | Вердикт/основание | Следующее действие/владелец |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-22 | approval | — | Пользователь утвердил архитектуру ADR-005…010 и ROADMAP v1.0; Git — локальные коммиты в `main` | — | APPROVED | Записать в APPROVALS |
| 2026-10-22 | TASK-MVP-00/A1/C1 | `run_68046cea3eb4` / `task_4d33d01ce1fa` / `ctx_85adc7c6460b` | R1; резерв полного ревью 1/2 | Codex: 0/2 вызовов, 0/1M input; ревью — независимый OpenCode | worker_done succeeded; проект NOT_REVIEWED | R1-ревью независимым OpenCode |
| 2026-10-22 | TASK-MVP-00/A1/C1 | `run_68046cea3eb4` / `task_4d33d01ce1fa` / `ctx_85adc7c6460b` | Реализация: коммит `ee4e699`, evidence `docs/workflow/evidence/TASK-MVP-00-C1.md`; release — retained/user_takeover | Ревью зарезервировано 1/2 | Ожидает вердикта | Диспатч ревьюера |
| 2026-10-22 | TASK-MVP-00/A1/C1 review | `run_68046cea3eb4` / `task_67d2d98ace9c` / `ctx_b4d619f7a180` | Ревью `3529aa1..ee4e699`; release — released | Полное ревью 1/2; Codex 0/2, 0/1M | **PASS**, находок нет | TASK-MVP-01 |
| 2026-10-22 | TASK-MVP-01/A1/C1 | `run_68046cea3eb4` / `task_b3bcd28acaf7` / `ctx_e67979c66846` | Реализация: коммит `5b9d916`, evidence `docs/workflow/evidence/TASK-MVP-01-C1.md`; release — released | Полное ревью зарезервировано 1/2; Codex 0/2, 0/1M | worker_done succeeded; проект NOT_REVIEWED | R1-ревью |
| 2026-10-22 | TASK-MVP-01/A1/C1 review | `run_68046cea3eb4` / `task_1d61cb577817` / `ctx_7ef3ef86a791` | Ревью `5e9e626..5b9d916`; evidence переиспользовано; release — released | Полное ревью 1/2; Codex 0/2, 0/1M | **PASS**, находок нет | TASK-MVP-02 |
| 2026-10-22 | TASK-MVP-02 design | `run_68046cea3eb4` / `task_2d70042ef4d9` / `ctx_acbb6b3c25e6` | R2 design по ADR-009; baseline `7b785f4`; design memo `msg_2a59e2195e94`; release — released | Codex calls 1/4; input design не раскрыт worker / 3M; reserve 0 | worker_done succeeded; проект NOT_REVIEWED | Реализация |
| 2026-10-22 | TASK-MVP-02/A1/C1 | `run_68046cea3eb4` / `task_508a5a075dd1` / `ctx_f615074805a8` | Реализация: коммит `a2b52a8`, evidence `docs/workflow/evidence/TASK-MVP-02-C1.md` (untracked); release — released | Codex calls 1/4; input design не раскрыт / 3M; полное ревью зарезервировано 1/2 | worker_done succeeded; проект NOT_REVIEWED | R2-ревью Codex |
| 2026-10-22 | TASK-MVP-02/A1/C1 review | `run_68046cea3eb4` / `task_4ac8b4f9eb5e` / `ctx_51b60231d76c` | Ревью `a2b52a8`; startup-сбои `ctx_f4757f0bcbf3`, `ctx_8cfb23da9905` — agent_readiness (Codex MCP warnings), не ревью; отчёт `docs/workflow/reviews/TASK-MVP-02.md`; release — terminal stale/closed | Полное ревью 1/2; Codex calls 2/4; input C1 review не раскрыт | **FAIL**, 6 MAJOR (`MVP02-R2-001…006`) | C2 correction + повторное ревью 2/2 |

## Восстановление и лимиты

2026-10-22: APPROVALS/ROADMAP отсутствовали; пользователь утвердил объём в
сессии. Git: `main`, HEAD `ba6c06e`, `.gitignore` изменён, `frontend/` не
отслеживается — сохранено. Orca: активных Run/Task по этому репозиторию нет;
завершённые Run относятся к другому проекту (SOBER). Счётчики и бюджеты ранее не
велись; начаты с нуля по факту утверждения. Baseline-проверки выполнены
координатором и сохранены для переиспользования review-policy.
