# История workflow — только дополнение

Фактические события проекта Equipment Documentation Registry. STATE.md содержит
только текущую сводку; эту историю не удалять и не переписывать после PASS.

## Прогресс ROADMAP

| Время | TASK | Статус/автор вердикта | Предшественники | Подход/циклы/ревью/RCA | Ревизия | Следующее действие |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-22 | TASK-MVP-00 | PASS / независимый OpenCode (R1) | нет | A1/C1; 1 полное ревью; FAIL 0 | baseline `3529aa1`; принято `ee4e699` | TASK-MVP-01 |
| 2026-10-22 | TASK-MVP-01 | PASS / независимый OpenCode (R1) | TASK-MVP-00 PASS | A1/C1; 1 полное ревью; FAIL 0 | baseline `5e9e626`; принято `5b9d916` | TASK-MVP-02 |
| 2026-10-22 | TASK-MVP-02 | IN_PROGRESS / C1 реализован, вердикта нет | TASK-MVP-01 PASS | R2; Codex design завершён; A1/C1 реализован; Codex 1/4 | baseline `7b785f4`; C1 `a2b52a8` | R2-ревью Codex |
| 2026-10-23 | TASK-MVP-02 | IN_PROGRESS / C2 NOT_REVIEWED; replacement R2 2/2 зарезервировано | TASK-MVP-01 PASS | R2; A1/C2; C1 FAIL 6 MAJOR; C2 `fde5406`; Codex calls 2/4 | C2 `fde5406`; HEAD `3c0c4be` | Диспатч `task_f5a7cda011c4` |
| 2026-10-23 | TASK-MVP-02 | PASS / Codex-ревьюер (R2) | TASK-MVP-01 PASS | R2; A1/C2; полное ревью 2/2; C1 findings 6 → 0; новые findings 0; Codex calls 3/4 | C2 `fde5406`; review `docs/workflow/reviews/TASK-MVP-02-C2.md` | TASK-MVP-03 |
| 2026-10-23 | TASK-MVP-03 | DESIGN complete / Codex (R2) | TASK-MVP-02 PASS | R2; A1/C1; design 1/4; TASK/AC заморожены; review 0/2 | design `task_6f36396f2464` / `ctx_9b0738b3df2d`; baseline `f0727e6` | Реализация OpenCode |
| 2026-10-24 | TASK-MVP-03 | IMPLEMENTATION_COMPLETE / NOT_REVIEWED | TASK-MVP-02 PASS | R2; A1/C1; design 1/4; реализация `40c6343`; full review 0/2; evidence untracked | baseline `db96b7a`; product `fde5406`; implementation `40c6343` | Codex R2 review |
| 2026-10-25 | TASK-MVP-03 | C1 FAIL / C2_IN_PROGRESS | TASK-MVP-02 PASS | R2; A1/C1; полное ревью 1/2 — FAIL, 2 MAJOR; Codex calls 2/4 | review `task_93712a9c9442` / `ctx_3f22c5d23a39`; `40c6343` | C2 correction OpenCode |
| 2026-10-25 | TASK-MVP-03 | C2_REVIEW_PENDING / NOT_REVIEWED | TASK-MVP-02 PASS | R2; A1/C2; оба MAJOR исправлены только тестами; focused 372, full 3530; C2 review 2/2 reserved; Codex calls 3/4 | C2 `6827ed3` (`task_a39b81e726c5` / `ctx_6e41326def5e`); review `task_b03f28ce101c` / `ctx_894373b5df1a`; evidence C2 untracked | Codex R2 review 2/2 |
| 2026-10-25 | TASK-MVP-03 | PASS / Codex-ревьюер (R2) | TASK-MVP-02 PASS | R2; A1/C2; findings `MVP03-R2-001…002` закрыты; новых 0; полное ревью 2/2; Codex calls 3/4 | C2 `6827ed3`; review `docs/workflow/reviews/TASK-MVP-03-C2.md` | TASK-WF-01 (Nemotron-координатор), затем TASK-MVP-04 |
| 2026-10-26 | TASK-WF-01 | IN_PROGRESS / A1/C1, вердикта нет | TASK-MVP-03 PASS | R1; A1/C1; baseline `a405968`; ревьюер `minimax-m3.1-flash-free`; Codex 0/2; launch receipt не подтверждён | docs WF-01; сервер — evidence C1 | Повторный launch, привязка Run, R1 |
| 2026-10-26 | TASK-WF-01 | **BLOCKED** / AC-002 | TASK-MVP-03 PASS | R1; A1/C1; повторный `orca agent launch` при здоровом сервере — exit 1, `capability_unsupported`; receipt модели нет | `TASK-WF-01-launch.json`; `TASK-WF-01-C1.md` | Нужно решение пользователя; MVP-04 не начинать |
| 2026-10-26 | TASK-WF-01 | IN_PROGRESS / альтернативный запуск | TASK-MVP-03 PASS | R1; A1/C1; пользователь разрешил `terminal create` + `OpenCode-Bolt.ps1`; ADR-011/ROADMAP поправки; R1 0/1 | ADR `034AE9EC…45A4`; ROADMAP `B5C1E943…2E4E` | Попытка 2: terminal create, привязка, R1 |
| 2026-10-26 | TASK-WF-01 | **BLOCKED** / сбой локальной координации | TASK-MVP-03 PASS | R1; A1/C1; terminal create + OpenCode-Bolt.ps1: модель подтверждена (`local-nemotron/nemotron-bolt`, cost 0), generation 5; локальная сессия сфабриковала worker/session ID; терминал закрыт; возврат облачного координатора generation 6 по решению пользователя | `TASK-WF-01-terminal.json`; `TASK-WF-01-local-failure.md`; `TASK-WF-01-C1.md` | TASK-MVP-04 по отдельному решению; WF-01 не PASS |
| 2026-10-26 | TASK-MVP-04 | DESIGN complete / Codex (R2) | TASK-MVP-03 PASS | R2; design 1/4; AC-001…010 и allowlist заморожены; implementation 0 | design `task_89004862c3a1` / `ctx_79b98b623026`; memo `msg_b797e4633a0b`, `msg_53201f873a18`; baseline `a405968` | Реализация OpenCode |
| 2026-10-26 | TASK-MVP-04 | IMPLEMENTATION_IN_PROGRESS / NOT_REVIEWED | TASK-MVP-03 PASS | R2; design 1/4; impl `task_efc8f84abfbc` / `ctx_c254370b2df1`, `deepseek-v4.1-flash-free`; allowlist 10 | baseline `a405968`; product `6827ed3` / `40c6343` | C1 evidence, затем Codex R2 review |

## Подходы и первопричины

| TASK/подход | Метод и отличие | Первопричина и почему исправления не помогли | Варианты/выбор | Сохранённые инварианты | План проверки |
| --- | --- | --- | --- | --- | --- |
| TASK-MVP-00/A1 | Зафиксировать существующий frontend и baseline без изменения backend | Не применимо (первый подход) | Единственный согласованный baseline-подход | ADR-005…010; backend не меняется | typecheck, build, pytest, alembic, состав коммита |
| TASK-MVP-01/A1 | JSONL-журнал через `logging` с обработчиком на logger `app`, настройка в lifespan, без изменения источников аудита | Не применимо (первый подход) | Файл append + JSONL; альтернативы (БД, syslog) не нужны для MVP | ADR-009; секреты и `str(error)` не пишутся; API/БД не меняются | новые тесты, полный pytest, git-состав, alembic |

## Замечания и исправления

| ID | TASK/подход/цикл | Критерий/место | Факт/воспроизведение | Ожидание/severity | Задание | Исправление/ревизия | Доказательство закрытия/статус |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MVP02-R2-001…006` | TASK-MVP-02/A1/C1 | AC-003, AC-004, AC-005, AC-007, AC-008 | 6 MAJOR: `status=complete`; учёт `LOG_FILE`; `root_missing`; детерминированный swap-тест; межсоединительный Event/barrier-тест; fault matrix root/stat | Требовалось bounded-исправление и повторное полное ревью 2/2 | C2 correction | `fde5406`; C2 evidence | **CLOSED**; C2 review PASS, новых findings 0 |
| `MVP03-R2-001` | TASK-MVP-03/A1/C1 | AC-003 | `VanishingStorage.open()` удаляет blob до `is_file`, поэтому граница `is_file`/`open` реального `LocalStorageBackend` не достигается; MAJOR | Нужна инъекция после успешного `is_file` и до `Path.open`, безопасный 500 и ровно одна `content_open_failed` запись | C2 correction | ожидается | **OPEN** |
| `MVP03-R2-002` | TASK-MVP-03/A1/C1 | AC-006, AC-007 | Disk snapshot не проверяется для EOF/read failure/ASGI 2.0/cancellation; send-наблюдатель накапливает body; MAJOR | Нужны disk-backed ASGI closure assertions для всех выходов и потоковый send-наблюдатель без накопления | C2 correction | ожидается | **OPEN** |
| `MVP03-R2-001…002` | TASK-MVP-03/A1/C2 | AC-003, AC-006, AC-007 | Оба MAJOR исправлены в C2 `6827ed3`; focused 372, full 3530; новых findings 0 | Требовалось повторное полное R2-ревью 2/2 | C2 correction | `6827ed3`; `docs/workflow/reviews/TASK-MVP-03-C2.md` | **CLOSED**; C2 review PASS |

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
| 2026-10-23 | TASK-MVP-02/A1/C2 | OpenCode-исполнитель | `fde5406` | focused: storage/reconciliation/CLI + file_service/concurrency, WSL, корень | 0 / `386 passed` | focused-набор с новыми C2-тестами зелёный | `evidence/TASK-MVP-02-C2.md` |
| 2026-10-23 | TASK-MVP-02/A1/C2 | OpenCode-исполнитель | `fde5406` | полный `pytest -q`; реальный CLI; миграции, WSL, корень | 0 / `3483 passed, 1 warning`; CLI complete; 12 миграций | полный backend и запуск зелёные | `evidence/TASK-MVP-02-C2.md` |
| 2026-10-23 | TASK-MVP-03 design | Codex | `f0727e6` | read-only `wsl.exe ... .venv/bin/python -B -m alembic heads` | 0 / `a3f1c72d5b90 (head)`; 12 revisions | baseline миграций подтверждён | design memo / HISTORY |
| 2026-10-24 | TASK-MVP-03/A1/C1 | OpenCode-исполнитель | `40c6343` | focused: download/integration/file/index-migration/storage/events/variants, WSL, корень | 0 / `365 passed, 1 warning in 62.25s` | focused-набор с integrity/index-тестами зелёный | `evidence/TASK-MVP-03-C1.md` |
| 2026-10-24 | TASK-MVP-03/A1/C1 | OpenCode-исполнитель | `40c6343` | полный `pytest -q`, WSL, корень | 0 / `3523 passed, 1 warning in 518.03s`; 0 failed | полный backend зелёный | `evidence/TASK-MVP-03-C1.md` |
| 2026-10-24 | TASK-MVP-03/A1/C1 | OpenCode-исполнитель | `40c6343` | `alembic heads/current`; `ls alembic/versions/*.py \| wc -l`; targeted 19 tests | 0 / `e4b8c2d16a70 (head)`; 13 миграций; `19 passed` | миграция и targeted-доказательства зелёные | `evidence/TASK-MVP-03-C1.md` |
| 2026-10-25 | TASK-MVP-03/A1/C2 | OpenCode-исполнитель | `6827ed3` | focused 372, full `pytest -q`, WSL, корень | 0 / `3530 passed, 1 warning`; 117 file tests | C2-исправления и полный backend зелёные | `docs/workflow/evidence/TASK-MVP-03-C2.md` |
| 2026-10-25 | TASK-WF-01 preflight | OpenCode-координатор | docs baseline `a405968` | `orca agent launch --agent opencode --model local-nemotron/nemotron-bolt` | FAIL / `capability_unsupported`: execution host cannot verify OpenCode model launch | локальный сервер был остановлен; cloud fallback не запускался | `D:\AI\NemotronBoltE4B\logs\orca-edr-launch-20261025-130043-537.json` |
| 2026-10-26 | TASK-WF-01 preflight | OpenCode-координатор | HEAD `a405968` | WMI `Start-Bolt.ps1`; `/health`, `/v1/models`, `server-state.json` | 0 / `ok`; `nemotron-bolt`, ctx 32768; PID 8304 | сервер поднят вне job терминала | `D:\AI\NemotronBoltE4B\server-state.json`, `logs\wmi-start.log` |
| 2026-10-26 | TASK-WF-01/A1/C1 | OpenCode-координатор | docs WF-01 | `orca agent launch --agent opencode --model local-nemotron/nemotron-bolt` при `/health` ok | 1 / `capability_unsupported`: execution host cannot verify OpenCode model launch | launch receipt модели нет; BLOCKED, fallback не запускался | `docs/workflow/evidence/TASK-WF-01-launch.json` |
| 2026-10-26 | TASK-WF-01 resumption | OpenCode-координатор | HEAD `a405968` | `orca orchestration run-use --id run_68046cea3eb4 --json` | 0 / handle `term_5ee91075…`, generation 4 | stale binding term_d5da заменена | Orca `run_68046cea3eb4` |
| 2026-10-26 | TASK-WF-01 attempt 2 | OpenCode-координатор | docs WF-01 | `orca terminal create`; `opencode export ses_e897…`; `run-show`; `terminal close` | 0 / generation 5; provider `local-nemotron`, model `nemotron-bolt`, cost 0; close `ptyKilled=true`; generation 6 | локальная модель подтверждена, но output сфабрикован | `TASK-WF-01-local-failure.md`; `%TEMP%\opencode\wf01-local-fake-output.txt` |

## Критерии приёмки и бэклог

| Время | TASK | Критерий/находка | Severity/статус | Доказательство | Решение/владелец |
| --- | --- | --- | --- | --- | --- |
| 2026-10-22 | TASK-MVP-00 | AC-001…AC-008 | Проверены, PASS; находок 0 | docs/workflow/reviews/TASK-MVP-00.md | Координатор/ревьюер |
| 2026-10-22 | TASK-MVP-01 | AC-001…AC-012 | Проверены, PASS; находок 0 | docs/workflow/reviews/TASK-MVP-01.md | Координатор/ревьюер |
| 2026-10-23 | TASK-MVP-02 | AC-001…AC-010 | Проверены, PASS; 6 C1 findings закрыты; новых находок 0 | docs/workflow/reviews/TASK-MVP-02-C2.md | Координатор/Codex R2 |
| 2026-10-26 | TASK-WF-01 | AC-004/AC-008: фабрикация worker/session ID | FAIL/BLOCKER | `TASK-WF-01-local-failure.md` | Координатор: терминал закрыт; WF-01 BLOCKED |

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
| 2026-10-23 | TASK-MVP-02/A1/C2 | `run_68046cea3eb4` / `task_b456188d963d` / `ctx_43c38bcb89c3` | Реализация C2: коммит `fde5406`, 4 файла; evidence `docs/workflow/evidence/TASK-MVP-02-C2.md`; focused 386 passed, full 3483 passed / 1 warning / 0 failed; release — released | Повторное полное ревью 2/2 зарезервировано; Codex calls 2/4, review не потреблён | worker_done succeeded; C2 не PASS | Повторное R2-ревью Codex |
| 2026-10-23 | TASK-MVP-02/A1/C2 review | `run_68046cea3eb4` / `task_947e474bc156`, `task_350c1332b0c3`, `task_af3f1c99b21e` / dispatches `ctx_f4481cb5eb4d`, `ctx_9daa30ee732e`, `ctx_5e49a3ea18bd`, `ctx_d219aae5e636`, `ctx_b5432406ad6d`, `ctx_adf362014e31` | Повторное ревью не начато: Codex `worker-start` — 6 failed на `agent_readiness`; warning `codex_worktrees` MCP HTTP 502; `task_af3f1c99b21e` circuit-broken; все терминалы released; C1/C2 evidence сохранены | Полное ревью 2/2 не проведено; Codex calls 2/4; input не раскрыт | **BLOCKED**; C2 не PASS | Решение пользователя: Codex/Orca startup + replacement review Task |
| 2026-10-23 | TASK-MVP-02/A1/C2 review | `run_68046cea3eb4` / `task_f5a7cda011c4` / dispatch pending | Codex startup fix: Hiddify system proxy `127.0.0.1:12334` возвращал HTTP 502 для localhost; добавлен `ProxyOverride=localhost;127.0.0.1;::1;<local>`; Codex TUI smoke без warning; ревью не потреблено | Полное ревью 2/2 reserved; Codex call 3/4 reserved; input 0/3M | NOT_REVIEWED | Диспатч Codex-ревьюера и ожидание `worker_done` |
| 2026-10-23 | TASK-MVP-02/A1/C2 review | `run_68046cea3eb4` / `task_f5a7cda011c4` / `ctx_f8b4e389182a` | Повторное полное R2 2/2: PASS; AC-001…AC-010 PASS; `MVP02-R2-001…006` закрыты; новых findings 0; отчёт `docs/workflow/reviews/TASK-MVP-02-C2.md`; evidence переиспользовано, rerun 0. Supervised `worker-start` вновь не прошёл `agent_readiness` (Orca ждёт `›`, Codex TUI рисует `»`); ревью выполнено через `dispatch --inject` в `term_27b46876-e608-426e-bd29-128220d4981e`, затем Task completed, терминал закрыт | Полное ревью 2/2; Codex calls 3/4; input 0/3M | **PASS**; TASK-MVP-02 PASS; проектный PASS не присвоен | TASK-MVP-03 |
| 2026-10-23 | TASK-MVP-03 design | `run_68046cea3eb4` / `task_6f36396f2464` / dispatch pending | R2 design: SHA-256 при скачивании + миграция `ix_files_document_id_id`; README/TASK-MVP-02 PASS; design Task создан | Codex calls 1/4 reserved; полное ревью 0/2 | NOT_REVIEWED | Диспатч Codex design |
| 2026-10-23 | TASK-MVP-03 design | `run_68046cea3eb4` / `task_6f36396f2464` / `ctx_9b0738b3df2d` | Design memo `msg_026fcb9a8ffb`: TemporaryFile-снимок с SHA-256 до 200, safe 500, `DownloadIntegrityError`, миграция `e4b8c2d16a70` от `a3f1c72d5b90`, AC-001…AC-010; найдены 3 устаревших baseline 12-миграционных теста; TASK `docs/tasks/TASK-MVP-03.md` создан; файлы/Git не менялись | Codex calls 1/4; полное ревью 0/2; input 0/3M | DESIGN complete; не TASK PASS | Реализация OpenCode |
| 2026-10-23 | TASK-MVP-03/A1/C1 | `run_68046cea3eb4` / `task_164ca46a0ba5` / dispatch pending | Implementation Task создан по TASK; baseline `0f57362`, продукт `fde5406`; старт A1/C1 | Codex calls 1/4; полное ревью 0/2 | NOT_REVIEWED | Запуск OpenCode-исполнителя |
| 2026-10-24 | TASK-MVP-03/A1/C1 | `run_68046cea3eb4` / `task_164ca46a0ba5` / `ctx_6fbe343526ae` | Supervised worker сделал коммит `40c6343`, но был abandoned до evidence и `worker_done`; Task помечен failed, работа продолжена отдельным Task | Codex calls 1/4; полное ревью 0/2 | worker outcome unknown; проектный PASS не присвоен | Recovery: новый Task верификации и evidence |
| 2026-10-24 | TASK-MVP-03/A1/C1 | `run_68046cea3eb4` / `task_f53910e0735d` / `ctx_331ce3d2a440` | Независимая проверка `40c6343`: focused 365 passed, full 3523 passed / 1 warning, 19 targeted, alembic `e4b8c2d16a70` / 13, diff только 12 allowlist-файлов; evidence `docs/workflow/evidence/TASK-MVP-03-C1.md` (untracked); Task completed | Codex calls 1/4; полное ревью 1/2 reserved | worker_done succeeded; проект NOT_REVIEWED | Codex R2 review |
| 2026-10-25 | approval | — | Пользователь подтвердил ADR-011 и ROADMAP v1.1: локальный Nemotron только координатор после PASS TASK-MVP-03; TASK-WF-01 до TASK-MVP-04; остальные роли без изменений | — | APPROVED; хеши `6F07E935…5716` / `EF04E4D4…1B10` | Записано в APPROVALS; TASK-WF-01 после PASS TASK-MVP-03 |
| 2026-10-25 | TASK-MVP-03/A1/C1 review | `run_68046cea3eb4` / `task_93712a9c9442` / `ctx_3f22c5d23a39` | Полное R2-ревью `40c6343`: FAIL, 2 MAJOR (`MVP03-R2-001` AC-003; `MVP03-R2-002` AC-006/AC-007); evidence переиспользовано, rerun 0; отчёт `docs/workflow/reviews/TASK-MVP-03.md`; Codex TUI `»` — `dispatch --inject` в `term_5de79d4e-cbc7-4fd8-a73e-782a9b95fc51`, терминал retained для C2 | Полное ревью 1/2; Codex calls 2/4; C2 review reserved 3/4 и 2/2; input не раскрыт | **FAIL**; C2 correction | C2 correction OpenCode, затем повторное ревью 2/2 |
| 2026-10-25 | TASK-MVP-03/A1/C2 | `run_68046cea3eb4` / `task_a39b81e726c5` / `ctx_6e41326def5e` | C2: коммит `6827ed3`, оба MAJOR закрыты тестами; focused 372, full 3530; evidence `TASK-MVP-03-C2.md`; release — released | C2 review 3/4 reserved; полное ревью 2/2 | worker_done succeeded; C2 не PASS | Codex R2 review 2/2 |
| 2026-10-25 | TASK-MVP-03/A1/C2 review | `run_68046cea3eb4` / `task_b03f28ce101c` / `ctx_894373b5df1a` | Полное R2 2/2: PASS; AC-001…AC-010; findings закрыты; новых 0; отчёт `TASK-MVP-03-C2.md`; review Task completed | Полное ревью 2/2; Codex calls 3/4; input 0/3M | **PASS**; TASK-MVP-03 PASS; проектный PASS не присвоен | TASK-WF-01, затем TASK-MVP-04 |
| 2026-10-26 | TASK-WF-01/A1/C1 | `run_68046cea3eb4` / launch pending / dispatch pending | R1; baseline `a405968`; TASK/AC заморожены; preflight launch 2026-10-25 13:00 — `capability_unsupported` при остановленном сервере; 2026-10-26 сервер поднят, повторный launch | Ревьюер `minimax-m3.1-flash-free`; Codex 0/2; input 0/1M; полное ревью 0/1 | IN_PROGRESS; при неподтверждённой модели — BLOCKED | Повторный `orca agent launch`, привязка, R1 |
| 2026-10-26 | TASK-WF-01/A1/C1 | `run_68046cea3eb4` / launch failed / dispatch none | Повторный launch при `/health` ok и PID 8304: exit 1, `capability_unsupported`; сессия не создана; R1 не запускался; продуктовые файлы не менялись | Ревью не начато (0/1); Codex 0/2; input 0/1M | **BLOCKED** по AC-002 / ADR-011; cloud fallback нет | Решение пользователя: изменить способ подтверждения или отложить WF-01 |
| 2026-10-26 | approval | — | Пользователь ответил «Разрешить альтернативный запуск (Recommended)»: terminal create + OpenCode-Bolt.ps1, подтверждение модели по receipt/metadata/логу; ADR-011 и ROADMAP дополнены | ADR `034AE9EC…45A4`; ROADMAP `B5C1E943…2E4E` | **APPROVED** | Попытка 2 TASK-WF-01, затем R1 |
| 2026-10-26 | TASK-WF-01/A1/C1 attempt 2 | `run_68046cea3eb4` / `term_356c9014…` / generation 5→6 | Альтернативный запуск: модель подтверждена; локальная сессия сфабриковала output; терминал закрыт; пользователь вернул облачного координатора | Ревью 0/1; Codex 0/2; input 0/1M | **BLOCKED**; TASK-MVP-04 разрешён отдельным решением | TASK-MVP-04 |
| 2026-10-26 | approval | — | Пользователь ответил «Вернуть облачного координатора (Recommended)»: исключение из запрета cloud fallback, WF-01 BLOCKED, MVP-04 разрешён | ADR-011 + поправка (2) `0C9A647D…3773`; ROADMAP + поправка (2) `22597055…E609` | **APPROVED** | Возврат generation 6; TASK-MVP-04 |

## Восстановление и лимиты

2026-10-22: APPROVALS/ROADMAP отсутствовали; пользователь утвердил объём в
сессии. Git: `main`, HEAD `ba6c06e`, `.gitignore` изменён, `frontend/` не
отслеживается — сохранено. Orca: активных Run/Task по этому репозиторию нет;
завершённые Run относятся к другому проекту (SOBER). Счётчики и бюджеты ранее не
велись; начаты с нуля по факту утверждения. Baseline-проверки выполнены
координатором и сохранены для переиспользования review-policy.

2026-10-26: после простоя обнаружена устаревшая привязка координатора
(`term_d5da…`, generation 3 не существует); `run-use` привязал текущую вкладку
`term_5ee91075…` как generation 4. Локальный Nemotron был остановлен вместе с
закрытой вкладкой 2026-10-25; новый запуск выполнен через WMI-процесс вне job
терминала, health/models подтверждены. Попытка `orca agent launch` с локальной
моделью 2026-10-25 13:00 вернула `capability_unsupported`; повторная попытка
после подъёма сервера является решающей для TASK-WF-01. Повторная попытка
2026-10-26 при `/health` ok вновь вернула `capability_unsupported`; TASK-WF-01
был остановлен как BLOCKED по AC-002. Пользователь разрешил альтернативный
запуск (terminal create + OpenCode-Bolt.ps1), ADR-011/ROADMAP дополнены;
TASK-WF-01 возобновлён, R1 и TASK-MVP-04 ещё не начаты. Облачный fallback не
запускался.

2026-10-26 (попытка 2): альтернативный `terminal create` +
`OpenCode-Bolt.ps1` поднял локальную сессию (`ses_e89726004ffeafCU74n5N64Qki`,
provider `local-nemotron`, model `nemotron-bolt`, cost 0), Run привязан с
generation 5. Локальная сессия сфабриковала `worker-list`/session ID вместо
фактического чтения Orca и не изменила PENDING-разделы C1; терминал закрыт,
ложные evidence не записаны, сервер PID 8304 остался жив. Пользователь
разрешил вернуть облачного координатора; `run-use` дал generation 6.
TASK-WF-01 — BLOCKED; TASK-MVP-04 разрешён отдельным решением пользователя.

2026-10-26 (CODEX_NEMOTRON_20261026; bounded setup): пользователь разрешил на
сегодня local-Nemotron coordination, отдельных Codex implementation/review и
выбор модели по задаче. Старый approval marker был ошибочно поставлен в первую
ячейку строки об альтернативном запуске; дата/источник восстановлены как
2026-10-26 / OpenCode user reply «Разрешить альтернативный запуск (Recommended)».
Фактическое новое решение добавлено отдельной строкой APPROVALS.

Утверждённый Run `run_68046cea3eb4` сейчас привязан к
`term_f2e42ac1-07ef-40bf-8517-f2ae394998f4`, generation 7 (live `run-show`).
Worker setup: Task `task_d93200c5b6b2`, Dispatch `ctx_eba8fecff71e`, terminal
`term_f2e42ac1-07ef-40bf-8517-f2ae394998f4`. Новая local session из bounded
metadata helper: `ses_e88db33d9ffe7MQijTub3mPnb6`, local-nemotron/nemotron-bolt,
47 messages, cost 0, cloud providers 0. `/health=ok`, единственная модель
nemotron-bolt, ctx 32768, PID 8304; профильный launcher `-CheckOnly` дал
CONFIG_VALIDATED, launched=false, run_mutated=false. Глобальный OpenCode config
hash не изменился: `31032AD46AB3230E75B9A9B0EE9CB255630D188C25949438C76AD9940A5CAE81`.

WF-01 документы обновлены, C1/failure evidence сохранены; AC IDs unchanged,
AC-005/009 reflect approved route substitution. Workflow setup call consumes
one WF-01 Codex call (1/2); one independent Sol-medium review call reserved,
not started here. WF-01 stays NOT_REVIEWED. No product code/data, tests,
migrations, frontend, environment, storage or dependency changes; no commit.
The initial rejected reviewer-start request did not start a reviewer; its
mutation ID is not a Dispatch. Malformed dotted-property PowerShell projection
returned null fields and is not evidence that workers were absent. Old DeepSeek
MVP-04 attempt `task_efc8f84abfbc` / `ctx_c254370b2df1` positively exited/failed
per execution-host worker-show at 10:37:39 Moscow; no code was written and no
worker_done was fabricated. Baseline 3530 tests is from 2026-10-25, not rerun.

Quota snapshots: 15% at 10:28:06, 18% at 10:29:49, and bounded helper 26% at
10:55 Moscow, all primary 300-minute reset `1793013647` (14:20:47 Moscow).
Weekly 4% is a separate 10080-minute window with reset `1793600447`. Setup
consumed user-session quota; local session cost 0 is not a free Codex call.
Per-task input attribution unavailable; preserve aggregate helper metadata,
never convert API dollar rates into subscription quota. Full failure, diagnostic,
hash, and current-state detail: `evidence/TASK-WF-01-C2.md`.

2026-10-26: независимый отчёт `docs/workflow/reviews/TASK-WF-01.md` обнаружен
после первого состояния NOT_REVIEWED. Его вердикт — **FAIL**, finding
`WF01-AC004-001` (BLOCKER): живой Orca сообщает старый MVP-04 dispatch
`ctx_c254370b2df1` failed/exited, а экран Nemotron показывал heartbeating /
investigating; AC-008 также FAIL из-за этой же фактической обработки.
Проверки AC-001/002/003/005/006/007 в отчёте PASS, AC-009/010 fully not
verified. Отчёт фактически указывает reviewer model `gpt-6-luna`, хотя для
review пользователя выбран `gpt-6.1-sol` / medium. Не считать этот разрыв PASS;
не переотправлять работу: setup + этот Codex review занимают WF-01 budget 2/2,
координатор сверяет остаток/следующий шаг и запрашивает новое решение при
нехватке бюджета. Отчёт не содержит подтверждённых Task/Dispatch ID ревьюера;
никакие lifecycle ID не выводятся из файла.

В ответ на follow-up координатора подготовлены внешние bounded guards:
`D:/AI/NemotronBoltE4B/Get-EDRWorkerStatus.ps1` (live `worker-show`, exact Task
и Dispatch match, ready/input_accepted= in_progress, completion требует explicit
outcome и nonempty report; никакой ack/successor) и обновлённый
`Start-WF01CodexReview.ps1` (actual full spec text, explicit codex / Sol medium,
сохранение exit code и `ok` в результате). В experiment profile разрешён только
status helper. Текущая Nemotron session использует inline
`OPENCODE_CONFIG_CONTENT`; изменения file-backed profile не меняют текущие
permissions. Контролируемый restart оставлен владельцу Run после завершения
текущей работы; denial не обходился. Настройка/helper syntax и profile JSON
проверены read-only, helper не запускает работников и не ack-ает почту.
2026-10-26: follow-up от координатора получен как status
`msg_ca5fe92cc3f1` / delivery `delivery_7460ae111b6a`; он указал на проверенную
несогласованность ready/input_accepted с worker_done и ошибочное принятие
rejected worker-start за успех. Командный `worker-start --help` прочитан перед
правкой. Добавлен внешний read-only status helper, проверяющий оба expected ID,
и подготовлен future profile permission; сценарий старта ревьюера передаёт
полный текст spec и явные Codex model/effort. Сырой native exit/JSON `ok:false`
сохраняется как явный failed result. Helper read-only проверен на том же старом
Dispatch и вернул failed/exited. PowerShell AST: 3 скрипта parse ok; profile
JSON valid; launcher `-CheckOnly`: CONFIG_VALIDATED, launched=false,
run_mutated=false. Первая AST-проверка выявила апостроф в строке ошибки — он
исправлен, после исправления повторная проверка успешна.

Профильная permission edit не изменила уже работающий coordinator: он был
запущен с inline `OPENCODE_CONFIG_CONTENT`. Не обходить denial; контролируемый
restart после settlement относится владельцу Run. Проверен ещё один quota
snapshot: 31% в 11:09 Moscow, primary 300 минут/reset `1793013647`, separate
secondary 5%/10080 минут/reset `1793600447`; aggregate tokens 11580573, per-task
attribution неизвестна.


### 2026-10-26T11:28:40.5537512+03:00 — защитный режим Nemotron

Фактическая привязка Run: `term_6f7a2a3e-51b1-4c5b-9056-734a90cd49e7`, generation 8. Прежняя generation 7 закрыта в 11:00:26 MSK после неверной интерпретации `ready/input_accepted` как завершения и преждевременного запуска review.
Контрольный guard берёт статусы непосредственно из Orca и сверяет оба lifecycle ID: setup `ctx_eba8fecff71e` = succeeded, review `ctx_1fed9cb1a43e` = succeeded. Новые dispatch и произвольные файловые правки текущему агенту недоступны. Приёмка текущего профиля NOT_REVIEWED, продуктовая цепочка BLOCKED. Calls 2/2 и review slot 1/1 не сбрасывались; дополнительный бюджет запрошен отдельно и не считается выданным без ответа.
Источник: `D:/AI/NemotronBoltE4B/Read-EDRQueue.ps1`, фактические `run-show`/`worker-show`, текущий snapshot STATE. Это операционная запись координатора, не новый вердикт ревью и не новая проверка backend.


### 2026-10-26T11:46:12.3378721+03:00 — защитный режим Nemotron

Фактическая привязка Run: `term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`, generation 9. Прежняя generation 7 закрыта в 11:00:26 MSK после неверной интерпретации `ready/input_accepted` как завершения и преждевременного запуска review.
Контрольный guard берёт статусы непосредственно из Orca и сверяет оба lifecycle ID: setup `ctx_eba8fecff71e` = succeeded, review `ctx_1fed9cb1a43e` = succeeded. Произвольные dispatch/правки недоступны; разрешённые дополнительные стадии проверяются отдельно. Приёмка текущего профиля NOT_REVIEWED, продуктовая цепочка BLOCKED. Calls used/reserved 3/4, review slots 1/2; исходные 2 calls/1 review не сбрасывались. Расширение действует только по фактически сохранённому решению WF01_EXTRA_2_20261026.
Источник: `D:/AI/NemotronBoltE4B/Read-EDRQueue.ps1`, фактические `run-show`/`worker-show`, текущий snapshot STATE. Это операционная запись координатора, не новый вердикт ревью и не новая проверка backend.


### 2026-10-26 — call3/4, единственная исправленная подача

Разрешение WF01_EXTRA_2_20261026 увеличивает потолок до 4 calls/2 full-review,
не сбрасывая исходные 2 calls/1 review. Реконструкция A1: C1 включает старые
неуспешные launch/handover и setup; независимый Luna Dispatch
`task_ffa88d993b98` / `ctx_1fed9cb1a43e` — один потреблённый полный review.
Ранний текст про AC-004/008 и итоговый текст того же отчёта про AC-009/010 —
версии одного review, не два подтверждённых независимых Dispatch.
Название старого файла C2 не доказывает, что второй full-review уже состоялся.
Текущий Sol `task_efe531f9842f` / `ctx_62c8a01dda32` — единственная исправленная
подача C2, call3/4. Astra high — зарезервированный call4/4 и повторный слот2/2,
не запущен. При обнаружении дополнительного ранее потреблённого full-review
цепочка BLOCKED без переименования/возврата. Нового подхода не объявляли.

Run generation9, `term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`; generation8 и её
receipt сохранены. Gen7 закрыт в11:00:26 MSK. Реальный worker terminal call3 —
`term_8bb93ef6-f806-4154-8f6a-158ebe096521`, не наследуемый coordinator handle.
Запуск call3 initially stopped на пустой post-start provider metadata;
это started_unverified, не доказанный wrong-model. Owner follow-up
`msg_c6d095c16473` и живое worker-show подтвердили Sol medium, без retry.
Повтор receipt теперь completion_not_inferred, а не ложный completed=false.

BLOCKED: live inline permission `*Read-EDRQueue.ps1*` слишком широко.
Подготовлен exact allowlist, но текущая сессия не перезапущена; старты
fail-closed отключены. RecordControl заморожен; чужая почта не ack-нута.
Новый пакет C2-correction содержит актуальные проверки, хеши и точные
действия владельца. Ни workflow, ни продуктовый PASS не присваивались.
Backend3530 — только история2026-10-25; новых backend/frontend прогонов нет.

### 2026-10-26T12:38:02.6004645+03:00 — снимок до CODEX_COORD_20261026

# Текущая сводка workflow

- 2026-10-26, main HEAD a405968; WF-01 **BLOCKED**, A1/C2: единственная исправленная подача; прежний FAIL сохранён.
- Run `run_68046cea3eb4`, coordinator `term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`, generation9. Generation8 — история; gen7 закрыт11:00:26 MSK.
- Call3: `task_efe531f9842f` / `ctx_62c8a01dda32`, worker `term_8bb93ef6-f806-4154-8f6a-158ebe096521`, фактический Sol medium; подача не означает PASS.
- WF01_EXTRA_2_20261026: использованы3/4 calls, резерв1/4 для отдельной Astra high; full-review использован1/2, повторный слот2 зарезервирован, не запущен. Старые2 calls и Luna FAIL не возвращены. Input TASK недоступен; агрегат rollout не равен расходу TASK.
- Текущая inline shell permission шире нужного; новый exact профиль только подготовлен. Платные старты и продуктовый dispatch выключены; нужен контролируемый restart/сверка владельцем. RecordControl не переписывает замороженный снимок. Нет новых агентов, commits/push/merge/deploy.
- MVP-00…03 PASS(4/7); проектный PASS нет. MVP-02 calls3/4,A1 2/3,всего2/9; MVP-03 calls3/4,review2/2. MVP-04 design1/4, реализация BLOCKED; старый DeepSeek failed/exited, нового writer нет.
- Quota11:51:18 MSK: primary51%,300min/reset14:20:47 MSK; secondary8%,10080min/reset1793600447 — отдельное окно. При исчерпании BLOCKED до нового решения, без reset/credit/account обходов. Исключение истекает27.10 00:00 MSK.
- Backend3530 — история25.10; новых backend/frontend прогонов нет; продукт не менялся.

[История](HISTORY.md), [основание](APPROVALS.md), [новый пакет](evidence/TASK-WF-01-C2-correction.md), [сохранённый FAIL](reviews/TASK-WF-01.md). Повторный отчёт `reviews/TASK-WF-01-repeat.md` ещё отсутствует.


### CODEX_COORD_20261026 — takeover и резерв MVP-04 A1/C1

run-use из собственного terminal term_d727cc23-31e8-42eb-a295-c42268e0c645
вернул generation10; receipt и ORCA_PANE_KEY совпали. Новый Run не создавался.
Live worker-list: старый MVP-04 task_efc8f84abfbc/ctx_c254370b2df1 failed,
exited, terminal retained (не released, как неточно сказано в handoff).
Design ctx_79b98b623026 settled succeeded/reclaimable: выполнен worker-release,
ответ released/closed_exited_terminal. Остальные user/retained terminals сохранены.
Полная delivery_97dc7d21db17 сохранена в evidence/CODEX-COORD-20261026-inbox.json:
design memos/worker_done подтверждают готовый контракт; старые DeepSeek heartbeats
не completion; WF setup/review/correction относятся к settled/released Dispatch.
WF FAIL и BLOCKED не изменены. Старая question msg_ba354aee346e уже потеряла
предмет после delivered review FAIL; нового WF review не будет.
MVP-04: design 1/4 consumed; резерв implementation call2/4 Sol medium,
A1/C1; затем независимый R2 Astra high call3/4, первый full-review slot1/2.
Input cap3M; точный исторический input TASK недоступен, aggregate не подменяет его.
AC-001..010 и allowlist TASK заморожены без функциональных изменений.
Сохранены все существовавшие uncommitted workflow-файлы; продукт baseline чист.
Quota наблюдение09:36:23Z: primary67%/300min/reset1793013647,
secondary10%/10080min/reset1793600447; источник собственный rollout
rollout-2026-10-26T12-35-15-01a17790-6877-7a71-a922-5fed6e550d7d.jsonl.
Это общее окно, не расход MVP-04. Backend3530 — только история25.10.

Orca preflight retry отказал task_not_startable: Task ready при latest Dispatch failed (failure_count1, operator_close), circuit breaker не достигнут. dispatch-show/worker-show подтвердили exited/external retained. Привожу статус Task к фактическому failed, затем supported --retry-of; новый Task/Run не создаётся. Отказ preflight не запустил модель, резерв call2 сохранён. Старая question уже имеет ответ (answer_conflict), прежний ответ не переписан; delivery обработана и ack.


Реальный Sol start succeeded/ready input_accepted, task_efc8f84abfbc / ctx_25189cfb43ce, worker term_c7507fad-6b56-46c9-86be-45f8398bc281. Requested/effective gpt-6.1-sol medium. Call2/4 consumed, не PASS. Receipt evidence/TASK-MVP-04-implementation-launch-2.json; отдельное актуальное руководство отправлено worker. Первый preflight refusal сохранён отдельно. Ожидание реального worker_done.


Вопрос исполнителя msg_c0b7ab216ae2 разрешён msg_52914a94cc85: leave uncommitted, commit после R2 PASS. Provider metadata сохранены отдельно. Coordinator ждёт exact worker_done ctx_25189cfb43ce.


Checkpoint msg_541e2abcbe10 от writer: S114, V55, H88/1warning, O10 passed; F выполняется, затем ALL/evidence. Это предварительное сообщение, не приёмка; два test-authoring сбоя исправлены внутри подачи, full review ещё не было.

### MVP-04 — ALL выявил границу allowlist, решение пользователя ожидается

msg_1753a6e7f565: ALL exit1, 7 failed/3764 passed/1 warning, 463.24s.
Причина подтверждена rg: глобальные OpenAPI assertions19 paths/34 operations
в семи старых модулях не учитывают два новых Batch path/четыре операции.
F1094 passed. Product AC/реализация не менялись; full-review ещё0/2.
Предложена точная поправка allowlist: tests/test_document_variants_api.py:698,
test_documents_integration_api.py:520, test_documents_search_api.py:527,
test_files_api.py:498, test_files_delete_api.py:691,
test_files_download_api.py:2244, test_files_upload_api.py:923.
Только totals19→21/34→38 и два содержащих числа test names.
Async вопрос пользователю отправлен; разрешение ещё НЕ получено.
Исполнителю через reply msg_9b1e26195c3c запрещены эти правки/повтор тестов
до явного решения; разрешено сохранить реальные failed ALL/G/C1 и metadata.
Тот же writer Dispatch ctx_25189cfb43ce остаётся владельцем, новый не запущен.
Quota10:00:17Z primary91%/300min/reset1793013647, secondary14%;
это общее окно. Фактического provider exhaustion пока не наблюдалось.

### MVP04_OPENAPI_COUNTERS_20261026 — явное решение после settlement

msg_ad8d127255c9 соответствует task_efc8f84abfbc/ctx_25189cfb43ce,
outcome failed, scope BLOCKED. После этого пользователь ответил «Разрешаю»
на точечный запрос семи totals и двух имён; точная формулировка в APPROVALS.
Прошлый writer released до ack. Резерв Sol continuation call3/4 и отдельный
Astra high call4/4; consumed design+implementation2/4 сохранены.
Это продолжение A1/C1, full-review0/2, не отмена failed ALL и не новый подход.

10:06:45Z audit actual implementation rollout input7686005/cached7566336/output31065, >input cap3M. Coordinator detected late after call3 start, no silent reset. New async request cap12M pending, maxcalls4 unchanged; Astra blocked until decision. Worker instructed pause new work at checkpoint, preserve already running ALL. Evidence implementation-quota-final.json observed10:04:45Z primary95%.


MVP04_INPUT_12M_20261026: явное user approval12M записано; actual7686005 сохранён, calls3/4, reserve Astra4/4. Пользователь сообщил primary2% после reset и явно разрешил продолжение текущего ctx_7ff92b6ea59a. Автосброс сам разрешением не считался; новых Run/Task/session для continuation нет.


### MVP-04 — continuation settled, ALL PASS, independent review pending

msg_9ff38caf3ce5 соответствует task_efc8f84abfbc/ctx_7ff92b6ea59a:
succeeded, ALL-final3771passed/1warning/exit0, без повторного запуска.
worker-release вернул released/closed_agent_terminal до delivery ack.
Actual input из отдельных подтверждённых rollout:
design2242445 + implementation7686005 + continuation1606202 =
11534652 из12000000, осталось465348. Cached input входит в input, не суммируется
повторно. Итоговые metadata snapshots лежат в evidence/*quota-final.json.
Design rollout связан с task_89004862c3a1/ctx_79b98b623026 его live preamble.
Актуальный provider snapshot11:56:37Z primary6%/reset1793032523, отдельное новое
окно; прежние95/100% не складываются с6%. Нового exhaustion не обнаружено.
Astra high call4/4, full-review1/2 ещё не запущен: pending уточнение literal
запрета пользователя создавать Task/session против независимого reviewer.
Запрошено только исключение для одного reviewer, лимит review400000 input,
не новый логический TASK/Run и не новый бюджет.

MVP04_ASTRA_CALL4_ONLY_20261026: получено точное «Разрешаю только Astra review call4». До старта reserve call4/4, first full-review1/2 A1/C1, max400000 input; used11534652/12M сохранён. Freeze финальный product/test SHA256 в TASK-MVP-04-SHA256-final.txt, G cleanup exit0 после coordinator EOF cleanup.

Astra review launched task_e54c9b327d43/ctx_666d79cff077, terminal term_1cda0a5c-f4e1-4d86-b844-df01891ca05b. Requested/effective gpt-6-astra high, input_accepted/turnStart observed; НЕ PASS. Call4/4 consumed, first full-review1/2. Maxreview400000/remaining465348, no further model calls authorized.

### MVP-04 — Astra call4 BLOCKED, бюджеты исчерпаны

Получен matching worker_done msg_7a0750ba0c0e:
task_e54c9b327d43/ctx_666d79cff077 outcome failed, report
reviews/TASK-MVP-04-C1.md. Actual provider gpt-6-astra/high подтверждён.
Ревью просмотрело восемь новых файлов, tracked diff, AC и17/17 hashes;
продуктовых BLOCKER/MAJOR не найдено. F/ALL/G просмотрены не полностью:
совмещённый tool output усечён, reviewer остановился по input budget,
вердикт BLOCKED/NOT_ACCEPTED, не PASS.
Worker released/closed_agent_terminal до delivery_ecd0c2f91f76 ack.
Call4/4 использован; full-review1/2 использован, отсутствие FAIL не возвращает
расход. Повтор/исправления/другие TASK без нового решения не запускаются.

Финальный review token_count12:04:40.588Z: input482028 (cached405504 уже входит),
output6482. Он превысил выделенный review reserve400000 на82028; финальное
завершение после последнего безопасного snapshot297176 также израсходовало
input. Реальный расход не скрывается и не обрезается лимитом.
Итого2242445 design +7686005 implementation +1606202 continuation +482028 review
=12016680 input/12000000, превышение16680. Фактические metadata:
evidence/TASK-MVP-04-review-quota-final.json и три предыдущих quota-final.
Provider primary21%/300min/reset1793032523, secondary19%/10080min;
нового provider exhaustion не было. BLOCKED именно TASK budget/неполное review.
ALL-final3771passed/1warning/exit0 сохраняется, повторов тестов не было.
Продуктовый commit не выполнен: routed PASS отсутствует. Все uncommitted
workflow/product изменения сохранены; push/merge/deploy/следующий MVP не было.

MVP04_ASTRA_EVIDENCE_CALL5_20261026: точное user «Разрешаю» принято; ceiling5calls/12400000input, used12016680 без сброса. До dispatch reserve call5/5, review slot2/2, only evidence continuation F/ALL/G, max300000input including finalization (remaining383320). Статический diff/hashes/AC reviewC1 переиспользуются; code submission неизменён.

Call5 ready/turnStart observed: task_f46401946eef/ctx_ab6321c6c683, worker term_cf5c2ff7-a4eb-49ff-bc9e-72b50b2d787c; requested/effective gpt-6-astra/high. Это не verdict. Budget5/5 consumed, review2/2; hard inputreserve300000 including finalization.

### MVP-04 — окончательный routed PASS и локальная поставка

matching msg_218f85040dc9:
task_f46401946eef/ctx_ab6321c6c683 succeeded,
report reviews/TASK-MVP-04-evidence-final.md.
Независимая Astra gpt-6-astra/high подтвердила полный F/ALL/G bounded просмотр,
17/17 неизменённых hashes, наследованную завершённую static AC001..010 проверку.
Вердикт PASS для всех10 AC; MVP04-R2-001 CLOSED. Старый BLOCKED не удалён.
worker-release вернул released/closed_agent_terminal до delivery50664458a1d2 ack.

Финальный token_count call5: 268773input (cached225792 входит), output6597.
Итого12016680+268773=12285453input/12400000; остаток114547.
Calls5/5, full-review2/2 использованы; последний разрешённый вызов завершил PASS.
Call5 reserve300000 соблюдён, расход/превышение предыдущих calls сохранены.
Provider12:22:58Z primary34%/reset1793032523, secondary21%; нового exhaustion нет.
Metadata evidence/TASK-MVP-04-evidence-review-quota-final.json.

До commit coordinator повторно сверил17/17 hashes с принятым манифестом.
После PASS только R0 status update docs/PROJECT_STATUS.md: пять упоминаний
ожидаемой приёмки заменены фактическим R2 PASS; код/тесты не менялись.
Новый commit-manifest evidence/TASK-MVP-04-commit-SHA256.txt отделён от прежнего
reviewed manifest, не перезаписывая исторические hashes. Тесты не повторялись:
последняя правка только фактический документный статус, не исполнение.
Первая служебная staging guard имела ошибку precedence сравнения PowerShell,
отказала до commit; исправлено явным сравнением двух строк списков.
Индекс после проверки содержал ровно17 allowlist files, прежних staged не было.
Локальный commit 0db1f9ede4b4e4b462ded4ce49a2b45967712732
Add Batch schemas, service and API, main; 17files,930insertions,32deletions.
Все прежние workflow изменения и evidence сохранены uncommitted.
No push/merge/deploy. WF-01 остаётся BLOCKED/NOT_ACCEPTED.
Следующие MVP не запускаются: текущее явное разрешение ограничено MVP-04.

### CODEX_NO_NEMOTRON_AND_STAGE_PUBLICATION_20261026

Новое решение пользователя: «Nemotron убираем из связки. Работа с ним не
понравилась вестись не будет. Тогда внеси коррективы какие нужны в проект
перед тем как приступим к следующему MVP и наверно стоит закоммитеть этот этап
проекта на GitHub».

ADR-011 отозван как действующее решение; TASK-WF-01 прекращён по выбору
пользователя. Его попытки и BLOCKED/FAIL результаты оставлены в истории и
evidence, повторные старты запрещены. Активные документы переключаются на
Codex coordination и [MODEL-ROUTING.md](MODEL-ROUTING.md); продуктовая
архитектура/объём не меняются. Roadmap v1.2 синхронизирует MVP-03/04 PASS и
оставляет MVP-05 следующим плановым этапом; этот запрос не запускает MVP-05.

Пользователь также разрешил публикацию текущего проверенного этапа: fast-forward
push текущей `main` в `origin/main` без force/merge/deploy. На момент решения
`main` имела 30 локальных коммитов сверх `origin/main`, включая MVP-00…04;
текущие workflow/task/evidence документы подготовлены к отдельному коммиту.
Ограничения и точная текущая область — в APPROVALS.md.
