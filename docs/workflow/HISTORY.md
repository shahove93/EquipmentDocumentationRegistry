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

## Критерии приёмки и бэклог

| Время | TASK | Критерий/находка | Severity/статус | Доказательство | Решение/владелец |
| --- | --- | --- | --- | --- | --- |
| 2026-10-22 | TASK-MVP-00 | AC-001…AC-008 | Проверены, PASS; находок 0 | docs/workflow/reviews/TASK-MVP-00.md | Координатор/ревьюер |
| 2026-10-22 | TASK-MVP-01 | AC-001…AC-012 | Проверены, PASS; находок 0 | docs/workflow/reviews/TASK-MVP-01.md | Координатор/ревьюер |
| 2026-10-23 | TASK-MVP-02 | AC-001…AC-010 | Проверены, PASS; 6 C1 findings закрыты; новых находок 0 | docs/workflow/reviews/TASK-MVP-02-C2.md | Координатор/Codex R2 |

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

## Восстановление и лимиты

2026-10-22: APPROVALS/ROADMAP отсутствовали; пользователь утвердил объём в
сессии. Git: `main`, HEAD `ba6c06e`, `.gitignore` изменён, `frontend/` не
отслеживается — сохранено. Orca: активных Run/Task по этому репозиторию нет;
завершённые Run относятся к другому проекту (SOBER). Счётчики и бюджеты ранее не
велись; начаты с нуля по факту утверждения. Baseline-проверки выполнены
координатором и сохранены для переиспользования review-policy.
