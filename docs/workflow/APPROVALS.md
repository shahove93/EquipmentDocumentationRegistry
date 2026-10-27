# Утверждения и разрешения

Записывать только фактические решения пользователя. Установка workflow не
разрешает разработку проекта.

## Журнал решений

| Дата / источник сообщения | Решение пользователя | Утверждённые документы и версия/хеш | TASK и границы | Ограничения |
| --- | --- | --- | --- | --- |
| 2026-10-22 / сессия OpenCode; ответы на вопросы координатора | Утверждён объём «MVP + Batch»; архитектура ADR-005…010; ROADMAP v1.0; frontend включён в поставку; Git — локальные коммиты в `main` | ADR-005 `6B73806E…E0020`; ADR-006 `05704F46…4F2C`; ADR-007 `5407FCD1…6913`; ADR-008 `86352049…A1CE`; ADR-009 `27797475…BF0E`; ADR-010 `FBCB792A…1472`; `ROADMAP.md` `3AAEA040…6EE4`; `VISION.md` `0DD68952…5E43`; `ARCHITECTURE.md` `6CB459E2…30A0`; `AGENTS.md` `51901EA7…DC78`; frontend tree `6ef6b03b…009a` | TASK-MVP-00…TASK-MVP-06; ветка `main`; frontend `frontend/**`; baseline HEAD `ba6c06e` | Без push/merge/deploy; без auth/authz и публичного доступа; без привязки к `Product`/`Batch`, `pg_trgm`, журнала изменений привязок и каскадного удаления; без удаления важных данных; без сброса лимитов провайдера |
| 2026-10-24…25 / сессия OpenCode; «Подтверждаю» (ADR-011) и «принял, продолжай» | Утверждено workflow-дополнение ADR-011 и ROADMAP v1.1: `local-nemotron/nemotron-bolt` только как координатор OpenCode после независимого R2 PASS TASK-MVP-03; TASK-WF-01 до диспатча TASK-MVP-04; исполнитель, R1-ревьюер и Codex-маршруты без изменений | ADR-011 `6F07E935…5716`; `ROADMAP.md` v1.1 `EF04E4D4…1B10` | TASK-WF-01 (операционный, вне семи продуктовых TASK); TASK-MVP-00…06 без изменения объёма | Без изменения глобальной модели OpenCode и других проектов; без тихого fallback на облачную модель; без изменения продуктового кода/данных в TASK-WF-01; TASK-MVP-03 review/счётчики не меняются |
| 2026-10-26 / сессия OpenCode; ответ «Разрешить альтернативный запуск (Recommended)» | Утверждена поправка к ADR-011/ROADMAP: при `capability_unsupported` от `orca agent launch` локальный координатор запускается через Orca `terminal create` с `OpenCode-Bolt.ps1` и явным `--model local-nemotron/nemotron-bolt`; фактическая модель подтверждается terminal receipt, метаданными OpenCode-сессии, локальным логом/процессом и привязкой к Run | ADR-011 + поправка `034AE9EC71013EBEE33137A24D7778B38F11ACC58462250419DCED65696445A4`; `ROADMAP.md` v1.1 + поправка `B5C1E9436F0989AEA9C30317DC0B9DF3B82844EAED26C6CD0FE8DCBB46782E4E` | TASK-WF-01; последовательность и TASK-MVP-00…06 без изменений | Без облачного fallback, без параллельных координаторов, без изменения глобальной модели/других проектов и продуктового кода/данных; остальные роли без изменений |
| 2026-10-26 / сессия OpenCode; ответ «Вернуть облачного координатора (Recommended)» | Утверждено исключение после сбоя локального Nemotron: вернуть облачного координатора, зафиксировать TASK-WF-01 BLOCKED и отдельно разрешить продолжение TASK-MVP-04; локальная модель координатором не признана | ADR-011 + поправка (2) `0C9A647D8338265618F9036A99321C3FE344666E878D0372E8FF9649AA5A3773`; `ROADMAP.md` v1.1 + поправка (2) `22597055AE417F67F0E18E7DC89367AF13FF6648A2E1CCF4D2B7A93F2033E609` | TASK-WF-01 — BLOCKED; TASK-MVP-04 разрешён отдельным решением; TASK-MVP-00…06 без изменения объёма | Без push/merge/deploy; без изменения продуктового кода/данных в WF-01; будущие попытки локальной координации — только по новому решению пользователя |
| CODEX_NEMOTRON_20261026 — сообщение Codex 2026-10-26 и последующее дополнение о моделях | Пользователь: «Давай сегодня попробуем поработать в связке только Codex и Nemotron, в качестве координатора) Проверим насколько хватит 5 часового лимита Codex». Дополнение: «Еще 1 дополнение, надо чтобы Codex менял каждую модел GPT под задачи, надо трудоемкие задачи использовать недорогие модели, там где нужно использовать дорогую». На сегодня локальный Nemotron координирует, отдельные Codex-исполнители реализуют, независимые Codex-ревьюеры проверяют; облачный OpenCode отключён. WF-01 использует Codex-подстановку для AC-005/009; внешние профиль/launcher/diagnostics входят в операционную область. После WF-01 acceptance можно продолжать утверждённые MVP-задачи без повторного подтверждения старта | Baseline `a405968401eefe6bcbbc2ca3302d14072eb63509`; исходные поправки ADR `034AE9EC…45A4`, ADR (2) `0C9A647D…3773`, ROADMAP `B5C1E943…2E4E`, ROADMAP (2) `22597055…E609`. Текущие полные SHA-256 документов AGENTS/ROADMAP/ADR-011/APPROVALS/TASK-WF-01/TASK-MVP-04 и profile/launcher — в `docs/workflow/evidence/TASK-WF-01-C2.md`. | Одна bounded настройка WF-01 и независимое review WF-01; сохраняются AC IDs и продуктовый объём. MVP-04 implementation по существующему design и Astra high R2 review только после WF-01 acceptance | Действует до 2026-10-27 00:00 Europe/Moscow. `gpt-6-luna` medium для текущей рутины, `gpt-6.1-sol` medium для WF-01 review и MVP-04 implementation, `gpt-6-astra` high для MVP-04 R2. Нет глобальных model/account/plan changes, reset/purchase credits, push/merge/deploy или product/data changes. При фактическом исчерпании провайдера — остановить зависимую цепочку и ждать нового решения даже после reset. Не переводить API cost в подписочный лимит. |
| 2026-10-26 / текущая сессия Codex; прямое сообщение пользователя | Пользователь: «Nemotron убираем из связки. Работа с ним не понравилась вестись не будет». Решение ADR-011 отозвано; будущая работа с Nemotron прекращена. TASK-WF-01 снят с исполнения, исторические результаты сохраняются. Координация проекта остаётся за Codex, модели выбираются по роли. Также запрошена синхронизация документов перед следующим MVP и публикация завершённого этапа на GitHub | ROADMAP v1.2, AGENTS.md, ADR-011, TASK-WF-01, MODEL-ROUTING.md и актуальные STATE/HISTORY | Продуктовый объём MVP-00…06 не меняется; MVP-05 остаётся следующим плановым этапом, запуск не входит в эту правку | Разрешён fast-forward push `main` → `origin/main` для всех текущих непубликованных commits и подготовленного документного commit; без force, merge или deployment. Не удалять внешние профили/evidence и не менять продуктовый код в этой корректировке |

Полные хеши (SHA-256) утверждённых документов на момент записи:

- ADR-005: `6B73806E7BC02F75BA1FBC38D2FEE4D37685CAE1F8E6609342CEF8FB190E0020`
- ADR-006: `05704F46E04026322EAE3880018DA297F54D50E5E40DD2EDCEB6F3A9293D4F2C`
- ADR-007: `5407FCD1842BF7AA0783C3E6FDE2933A83DEC8AE150AEBD313578F0863796913`
- ADR-008: `8635204909D3AC35F11F61291FD4F71CB53AE049AC438D29DF85909195A7A1CE`
- ADR-009: `2779747520BB433F2ED8D7E5FEE60F4A1704E87E53D51B567D40C04DD714BF0E`
- ADR-010: `FBCB792A85620D1D69FFC91351FDBBDC779718B776D6D264D0ACE702A25A1472`
- ROADMAP.md: `3AAEA040B650C13633FFFBEE0183D6DFBCCE71C63BB532BFE0C639A2D6F26EE4`
- VISION.md: `0DD68952798D8C3950E352F38B125789E567AE0A17CF4E2FBA25AEFCBD055E43`
- ARCHITECTURE.md: `6CB459E2E9D16A0D0258CDB38A5A39C05A98CCD28524C18F429492986EEF30A0`
- AGENTS.md: `51901EA73E3E061A3FC49BDF0375808C51840FB622B4D1C99767296D1D43DC78`
- frontend tree (без `node_modules/` и `dist/`):
  `6ef6b03b5acf5570cf6d2c5f80f7dbc29516e59d06b4c52950f46f925d87009a`

## Текущая область разрешения

- Архитектура продукта ADR-005…010, VISION v1.0 и ARCHITECTURE v1.0 остаются
  утверждёнными. ROADMAP v1.2 сохраняет продуктовые TASK-MVP-00…06; изменения
  относятся к workflow и не меняют продуктовые требования.
- ADR-011 отозван. TASK-WF-01 прекращён по решению пользователя и не является
  активной задачей или условием для MVP-05. Исторические approvals, BLOCKED/FAIL
  и evidence не удаляются и не дают разрешения на повторный запуск.
- Codex координирует Orca; отдельные Codex workers реализуют TASK и проводят
  независимое ревью по риск-маршруту. Модели и effort — в MODEL-ROUTING.md.
- Ветка/worktree: `main`, текущий workspace. Локальные коммиты разрешены после
  routed PASS.
- Push: разрешён только текущий fast-forward push `main` → `origin/main`,
  включающий ранее согласованные непубликованные commits и документный commit
  этой корректировки. Force-push запрещён.
- Merge и deployment не разрешены. Удаление важных данных не разрешено.
- Frontend включён в поставку. Auth/authz, публичный доступ, связи документа с
  `Product`/`Batch`, `pg_trgm`, журнал изменений привязок и каскадное удаление
  остаются вне объёма до отдельного решения.
- MVP-05 — следующий плановый TASK; эта корректировка документов сама по себе
  не запускает его реализацию.


## WF01_EXTRA_2_20261026 — дополнительные вызовы без сброса истории

2026-10-26, текущая сессия Codex: пользователь ответил **«Разрешаю»** на конкретный запрос: ещё два вызова для WF-01 — Sol medium для исправления пакета и контрольных проверок, затем отдельная Astra high для независимой приёмки. Общий потолок увеличен с 2 до 4 вызовов, полных ревью — с 1 до 2. Прежние setup/Luna-review и их фактический расход сохраняются; ни одного вызова или review slot не возвращено.
Для этого единственного повторного WF-01 ревью явно утверждена `gpt-6-astra / high`; это изменение действует вперёд и не исправляет задним числом ошибочный Luna-review. Область продукта, запреты push/merge/deploy/reset/account changes и срок сегодняшнего эксперимента не изменены. При повторном FAIL/BLOCKED или исчерпании 4/4 цепочка останавливается.
Источник решения: `D:/AI/NemotronBoltE4B/logs/WF01-extra-budget-20261026.json`, baseline `a405968401eefe6bcbbc2ca3302d14072eb63509`; точный вопрос и ответ сохранены в этом артефакте. Координатору разрешены только два последовательно ограждённых запуска, полный spec, фактические model/effort и реальные lifecycle receipts обязательны.


## Уточнение WF01_EXTRA_2_20261026 — исправление call3

Решение «Разрешаю» от 2026-10-26 11:33:55 MSK сохранено в
`D:/AI/NemotronBoltE4B/logs/WF01-extra-budget-20261026.json`:
общий потолок 4 вместо 2, полных ревью 2 вместо 1, без возврата расхода.
Исправление — `gpt-6.1-sol / medium`, единственное повторное ревью —
`gpt-6-astra / high`, только вперёд; прежний Luna FAIL остаётся FAIL.
Срок — до 2026-10-27 00:00 Europe/Moscow. Объём AC и продукта не меняется.
Текущий Run `run_68046cea3eb4`, coordinator
`term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`, generation 9; generation 8
(`term_6f7a2a3e-51b1-4c5b-9056-734a90cd49e7`) — история.
Новый фактический пакет: `docs/workflow/evidence/TASK-WF-01-C2-correction.md`.
Старый C2 содержит неверный worker handle и устаревшие данные; его нельзя
использовать как текущий снимок. Повторный отчёт предназначен для
`docs/workflow/reviews/TASK-WF-01-repeat.md`; он ещё не создан.
Текущий результат исправления — BLOCKED: активное inline shell-разрешение
слишком широко, подготовленный точный профиль ещё не загружен.
Платные старты и продуктовый dispatch отключены. Restart/rebind/закрытие
координатора исполнителем не выполнялись; требуется действие владельца.

## CODEX_COORD_20261026 — передача координации Codex

2026-10-26: точное решение пользователя из native-read
D:/AI/NemotronBoltE4B/EDR-CODEX-COORDINATOR-20261026.md:
«Давай передадим работу у в Codex пока. Посмотрим как пойдет расход лимитов) Главное сделай распределение моделей по ролям».
Текущее прямое сообщение пользователя: "You are the new Codex COORDINATOR of Equipment Documentation Registry. The current user explicitly transferred coordination from Nemotron to Codex, authorized continuing the approved MVP-04 despite BLOCKED WF-01, and requires GPT choice by role/task. This overrides the previous OpenCode-only/Nemotron-coordinator restrictions."

Baseline a405968401eefe6bcbbc2ca3302d14072eb63509, main/current.
Codex временно владеет очередью, документами, ожиданием и приёмкой по маршруту;
отдельный Sol medium реализует MVP-04 по готовому TASK, отдельный Astra high
проверяет R2. Полная таблица: MODEL-ROUTING.md. WF-01 остаётся BLOCKED/
NOT_ACCEPTED, 3/4 calls, 1/2 full-review, последний резерв не используется.
MVP-04 сохраняет design 1/4, потолок 4 calls/3M input; новая сессия не сбрасывает
расход. Продолжение ранее утверждённых MVP разрешено без повторных стартовых
подтверждений. Новое разрешение отменяет только старые ролевые ограничения и
зависимость product dispatch от WF-01 PASS. Функциональные AC/архитектура,
срок до 2026-10-27 00:00 Europe/Moscow, независимость review, запреты
push/merge/deploy/reset/credit/account/plan changes сохраняются.
Локальный commit разрешён после routed PASS; до него исполнитель не коммитит.
При фактическом исчерпании провайдера — BLOCKED до нового решения даже после reset.
Run run_68046cea3eb4 привязан собственным run-use: coordinator
term_d727cc23-31e8-42eb-a295-c42268e0c645, generation 10.
Launch receipt: D:/AI/NemotronBoltE4B/logs/edr-codex-coordinator-20261026-launch.json.

## MVP04_OPENAPI_COUNTERS_20261026 — точечное расширение allowlist

Пользователь 2026-10-26 в текущем чате ответил **«Разрешаю»** на вопрос:
«Разрешить точечно расширить allowlist MVP-04 на семь существующих тестов:
test_document_variants_api.py, test_documents_integration_api.py,
test_documents_search_api.py, test_files_api.py, test_files_delete_api.py,
test_files_download_api.py, test_files_upload_api.py — только обновить общий
OpenAPI-счётчик 19→21 путей и 34→38 операций (и названия двух тестов с этими
числами)? Это необходимо для ALL: строгий allowlist TASK-MVP-04 сейчас запрещает
их менять. Функциональные проверки сохраняются; после правки исполнитель
повторит ALL, затем отдельная Astra high проведёт ревью в прежнем бюджете.»

Baseline a405968401eefe6bcbbc2ca3302d14072eb63509; сохраняется текущий
uncommitted Batch diff, AC-001…010 и архитектура. Дополнительные разрешённые
файлы находятся в tests/. Только перечисленные счётчики/названия, без ослабления
проверок. Отказавший ALL7failed/3764passed остаётся в истории.
Sol continuation call3/4, независимый Astra high call4/4; это прежний бюджет,
не увеличение потолка. Full-review ещё0/2; повтор ALL обоснован новыми тестовыми
изменениями. F1094 успешный переиспользовать: его файлы не меняются.

## MVP04_INPUT_12M_20261026 — увеличение input без сброса

Точное новое указание пользователя 2026-10-26:
«Пользователь явно разрешил для MVP-04 поднять input-потолок до 12 млн токенов.
Сохрани фактический расход 7 686 005 input, существующий лимит 4 вызова, все
прежние попытки и результаты. Не создавай новый Run, Task или сессию.
Продолжай только существующий MVP-04: зафиксируй разрешение в workflow,
проверь текущий статус того же Dispatch ctx_7ff92b6ea59a и уже запущенного ALL,
не дублируй тесты без необходимости. Provider quota snapshot сейчас показывает
primary 2%, reset уже произошёл. Если этот же активный worker доступен —
доставь ему approval через Orca и продолжай; Astra high call4 — только после
подтверждения результата ALL и если остаток 12M позволяет.
Сразу остановись, если provider limit снова exhausted.»

Baseline a405968401eefe6bcbbc2ca3302d14072eb63509, main/current;
Run run_68046cea3eb4, текущий task_efc8f84abfbc/ctx_7ff92b6ea59a.
Input ceiling увеличен3M→12M, использованные7686005 и весь добавочный
фактический расход сохраняются. Максимум4 calls, design1/4,
implementation2/4, continuation3/4, резерв Astra high4/4.
Пользователь явно разрешает текущее продолжение после reset; сам reset
разрешением не считался. Новый provider exhaustion останавливает цепочку.
Новых Run/Task/сессий для продолжения не создавать; использовать текущий worker.

## MVP04_ASTRA_CALL4_ONLY_20261026

Точный ответ пользователя на уточнение запрета новых Task/session:
**«Разрешаю только Astra review call4»**.
Разрешён единственный отдельный независимый reviewer Task/context в существующем
Run run_68046cea3eb4, логический MVP-04. Call4/4, не новый бюджет;
input reserve максимум400000 из остатка465348 при used11534652/12M.
Реализация завершена, ALL3771passed/1warning. Других workers/tasks/сессий
и следующих MVP это решение не разрешает; проверки без необходимости не повторять.

## MVP04_ASTRA_EVIDENCE_CALL5_20261026

Пользователь ответил **«Разрешаю»** в текущем чате на конкретный запрос:
«Разрешить один дополнительный Astra-вызов и потолок 12,4 млн input,
только для завершения проверки доказательств, без изменений кода и повторных тестов?»
Baseline a405968401eefe6bcbbc2ca3302d14072eb63509. Продолжается только
существующий логический MVP-04 / Run run_68046cea3eb4.
Потолок calls4→5, input12M→12.4M; used12016680 сохраняется, осталось383320.
Прежний review BLOCKED, все результаты/превышения сохранены.
Дополнительный gpt-6-astra/high проверяет только недостающие F/ALL/G и закрытие
MVP04-R2-001, переиспользует завершённую статическую проверку и hashes из C1.
Резерв call5/5, второй и последний review slot2/2; code submission не меняется.
Hard reserve300000 input (включая финализацию), 83320 остаётся страховочным
остатком родительского cap. Других вызовов/следующих MVP, code changes,
повторных тестов/reset/account changes/push/merge/deploy не разрешено.

## MVP05_START_20261026

Текущее прямое поручение пользователя: «создай замороженный
docs/tasks/TASK-MVP-05.md и запиши scope, AC и лимиты в STATE+HISTORY; затем
через существующий Run создай и запусти TASK исполнителя по утверждённой
матрице Luna medium».
Scope Batch list/detail/create/edit и Vite/batches; без backend/API/DB,
Document→Batch/Product/auth/migrations. Main baseline318e6336737ee635abf593c2643f26daba273f86.
Один writer, R1, frozen AC001..007. Резерв implementation600000 input,
общий ceiling1000000/calls2, возможный R1 review250000 отдельно после
completion и сверки актуальной policy. Никакого экспертного/приёмочного
вызова это стартовое действие не выполняет. Push запрещён, reviewer до
завершения исполнителя запрещён. Новый Run/Nemotron не используются.

## MVP05_REVIEW_ONLY_9300000_20261026 — исключительное решение пользователя

Точное текущее поручение пользователя:
«Пользователь явно разрешил дополнительный бюджет только на независимое ревью Sol.
Продолжай тот же TASK-MVP-05 без сброса счётчиков: фактические 8,812,350 input
сохраняются; новый потолок всего TASK 9,300,000 input; резерв на единственный
reviewer call2/2 — максимум 250,000 input, остаток 237,650 страховочный».
Ровно один отдельный gpt-6.1-sol/medium reviewer в существующем Run.
Только review frozen AC/ограниченного полного diff+evidence; без нового кода,
исправлений, повторных проверок, дополнительных задач, commit/push и stage acceptance.
Любой verdict и фактический usage записать и остановиться; исправления требуют
нового бюджета. Это явное пользовательское исключение для R1 Codex-review и
input cap, приоритетное над общими ограничениями skills на рутинный R1 Codex.

Baseline318e6336737ee635abf593c2643f26daba273f86, main/current,
Run run_68046cea3eb4, logical TASK-MVP-05, A1/C1.
Расход Luna8812350 сохранён; cap1000000 превышен7812350,
reserve600000 превышен8212350; прежний BLOCKED и snapshot7271010 сохранены.
Новый cap9300000; calls1/2 consumed, reserve call2/2 input250000
(включая финализацию); safety237650 не выдаётся reviewer как доп. бюджет.
Первый full-review slot1/2 резервируется; предыдущих acceptance review нет.
Нет автоматического увеличения потолков при FAIL/MINOR/NIT/BLOCKED.

## MVP05_C2_EXTRA_1500000_20261026 — явное исключительное разрешение C2

Новое прямое поручение пользователя после C1 FAIL:
«Разрешаю C2 до 1,5 млн input-токенов по этому плану».
Точное уточнение: C1 settlement9210419/9300000 сохраняется без сброса;
дополнительно ровно до1500000 input, cumulative ceiling10710419.
Резерв C2 Luna medium implementation до900000 включая проверки/evidence;
checkpoint600000 и остановка implementation ДО900000. Резерв второго/последнего
Sol medium full-review до450000 НЕПРИКОСНОВЕНЕН для writer; safety150000.
Ровно2 новых calls, cumulative4; review slot2/2 A1. Сначала actual writer
worker_done, затем независимый reviewer. Если C2 FAIL — остановиться:
третьего full-review нет. Это не reset расходов и не изменение подхода.

Тот же Run run_68046cea3eb4, main/current baseline318e6336737ee635abf593c2643f26daba273f86.
C2 строго F-01..F-04: полный round-trip bodies/date/Decimal/edit/clear/detail GET;
guard stale POST/PATCH callbacks; browser URL/refresh/HTML headers и ограниченные
404/422/network/pagination evidence; final hashes после всех правок.
Original MVP05 allowlist, mock/browser fixture, backend/API/DB/deps unchanged.
Только targeted browser smoke и frontend typecheck/build; не backend full tests.
One writer, no push; commit только после C2 routed PASS. Не stage acceptance.
Предыдущие overruns и C1 FAIL остаются в append-only history/evidence.

## MVP05_C2_RESUME_CALL4_11535749_20261026 — новое прямое разрешение

Пользователь ответил «Разрешаю» на явный запрос одного дополнительного
Luna implementation call до900000 input, cumulative ceiling11535749,
с сохранением Sol final review450000 и safety150000.
Точное текущее поручение: продолжить C2 в прежнем Run, не сбрасывать input
и stopped call3actual825330; call4/5 Luna medium≤900000,
call5/5 Sol medium≤450000; C2 second/full-review slot2/2.
C1actual9210419 + call3actual825330 = currentactual10035749.
Новый cap11535749, рост против прежнего10710419 ровно825330.
Aggregate remaining1500000 = writer900000 +review450000 +safety150000.
Все исторические cap/overrun/FAIL/stopped receipts остаются append-only.

Code scope и frozen checklist exactly docs/tasks/TASK-MVP-05-C2.md,
без новых требований. Prior partialcode/evidence сохраняются, один writer.
Старый TASK-MVP-05-C2-budget-guard.py/receipts не менять и НЕ запускать:
его worker-stop800k был ошибкой. Новый observer только read-only/alert-only
checkpoint600k. Координатор вручную проверяет progress/spend; writer прекращает
substantive edits до750k, finalization до900k; safety/review не тратит.
После actual worker_done записать settledusage ДО Sol call5.
Scope/budget failure останавливает цепочку. Coordinator не пишет code.
Других workers/Dispatch вне этой пары, reset/account/session обходов нет.
Commit/push до routed C2 PASS запрещены; прежний запрет push сохраняется.

## MVP05_C2_CALL5_12435749_20261026 — новое прямое разрешение

Пользователь прямо ответил «Разрешаю»: один дополнительный Luna implementation
call до900000 input; новый cumulative ceiling12435749, final Sol review≤450000.
Current settledactual10959367 сохраняется: C1 9210419, stoppedcall3 825330,
stoppedcall4 923618 (over own900000 by23618). Никакого reset/refund/переписывания
истории; previous ceiling11535749 увеличен ровно900000.
Totalcalls6: implementation call5/6 Luna medium≤900000,
finalreview call6/6 Sol medium≤450000, A1 full-review slot2/2.
Remaining1476382 =900000writer+450000review+126382safety; writer не тратит safety.

Frozen C2 scope F01..F04 и alloriginalAC carryforward неизменны; partialcode/
evidence uncommitted сохраняются. Same Run/workspace, ровно1 новый writer;
старый guard/terminal не переиспользовать. На owninput450000 writer делает
blocking ask и прекращает substantive work до ответа координатора.
Substantive закончить≤700000, finalize≤850000, headroom до hard900000.
Observer read-only/alert-only, никаких worker-stop/close; coordinator message450k.
Только targeted existing MOCK browser smoke, typecheck/build один раз наfinalcode,
без backend tests/измененийbackend/API/DB/deps. Actual worker_done обязателен.
Settledusage перед finalSol; если C2 FAIL stop, без дополнительных fixes/reviews.
No commit до routedPASS; push не разрешён. Это не stage acceptance.

## MVP05_C2_CALL6_12639440_20261026 — новое прямое разрешение

Пользователь прямо ответил «Разрешаю» на ещёодин Luna implementation call6
до900000input, перенос finalSolreview наcall7, ceiling12639440.
Settledactual11163058 сохраняется: C1 9210419 +call3 825330stopped
+call4 923618stopped +call5 203691failedbeforeprojectwork.
Previousceiling12435749 увеличен203691; newremaining1476382 =
writer900000 +review450000 +safety126382. Это явное изменение ceiling,
не reset/refund/отмена прошлых failures/overruns.
Totalcalls7: Luna medium call6/7 max900000 inclfinalization,
independent Sol medium call7/7 max450000, A1 second/finalfullreview2/2.
C1fullreview1/2,failedreview1 сохранены.

Frozen scope тотже C2 F01..F04+originalAC001..007/C1findings,partialcode/evidence
call3/4 uncommitted сохраняются; call5 no projectwork по workerreport.
Call6 starts at owninput ZERO: никаких upfrontblockingasks или ожидания
approval доработы. Немедленно выполнять scope, own450k=>STOPsubstantive и
blockingask; coordinator ОБЯЗАН formal orchestration reply сactualnumbers/
решением втотжеcall, queuedstatus не заменяетreply.
Read-only/alert-onlyobserver450k,безworker-stop/kill/close.
Substantivefinish≤700k,finalevidence/worker_done≤850k,hard900k.
Only targetedexistingmockbrowser smoke,typecheck/build1раз finalcode,
no backendtests/deps. Actualworker_done required,settledusage BEFORE finalSol,
evidence ready/fit450k required. C2FAILstop,thirdreview/fixesнет.
Localcommit allowed only C2PASS; no push/merge/deploy/stageacceptance.

## MVP05_C2_ACCOUNTING_ONLY_20261026 — прямой authority update пользователя

Текущее прямое сообщение пользователя подтверждает: проект ведут только
Codex coordinator +Codex workers через Orca,безOpenCode/Nemotron.
Отменены ВСЕ жёсткие input-token потолки на вызов/TASK, внутренние резервы
и блокирующие token checkpoint паузы/replies. Фактический usage учитывать;
не прекращать работу из-за плановогорасхода/внутреннегорезерва.
Остановка только при реальном providerlimit/refusal или прямом userstop,
безreset-credit/покупкикредитов/account/plan/session обходов.
Это прямой authorityupdate в coordinatorchat, не прежние rejectedgates.
Skill routing-and-budget.md обновлена; quality/review-policy gates сохраняются.

Продолжить тотже MVP-05 R1 A1/C2,Run run_68046cea3eb4,main/current,
frozen F01..F04+AC001..007,сохранённые partialcode/evidence и C1FAIL.
Actual12318058 и все расходы/overruns/stopped/failedcalls сохраняются.
Старые caps/checkpoint/informationalmessages/старые taskaddenda сbudgethold
теперь ТОЛЬКО ИСТОРИЯ и не являются инструкциями остановки/ожидания.
Новые разрешённые шаги: Luna medium completion C2, actualworker_done/evidence,
затем отдельный Sol medium final independent full-review2/2.
C2 — одна исправленнаяподача,не новыйapproach/не сбросциклов.
Токенные observers/guards/checkpointpauses не запускать.
No scopeexpansion,reset/обходов,push/deploy; localcommit только routedPASS.

## MVP05_PROVIDER_RESET_RESUME_20261026 — прямое user resume после providerlimit

Пользователь сообщил: лимиты восстановлены, время после terminalreset7:35PM,
явно разрешил продолжить ТОТЖЕ активный task_be6fd5441e23/ctx_14c1888cf95b
в term_5a1aaebf-3abf-4e76-b4fc-bc9a8deb0590 без новогоworker/retry.
Native inboxпуст; worker-show dispatched,observation live/exactWorkertrue;
terminalscreen содержит старый реальный usage-limit/tryagain7:35PM.
После runtime restore projection restored_unconfirmed, resource user_owned/
retained; это не proofexit. Не закрыватьuserownedterminal/не дублироватьwriter.
Нынешнее явное resume является разрешением после providerstop;
самreset не считался самостоятельным разрешением.
ScopeC2F01..F04+AC001..007 unchanged,accountingonly,noinputcaps/checkpointgates.
Новый actualproviderrefusal=>stop до нового решения; безлимитных обходов нет.
Actualworker_done/evidence перед remainingSolmediumfullreview2/2.
No push/deploy,localcommitonlyroutedPASS.

## MVP05_C3_A2_AUTHORIZED_20261026
Пользователь «Ну делай что нужно)» прямо разрешил C3 read-only RCA и A2/C1 в прежнем frozen F01..F04+AC001..007 (TASK-MVP-05.md/TASK-MVP-05-C2.md; baseline318e6336737ee635abf593c2643f26daba273f86). Codex coordinator, один gpt-6-luna/medium writer, затем отдельный gpt-6.1-sol/medium reviewer после worker_done/evidence. A1 FAIL/FAIL и review2/2 сохранены, третьего A1 review нет.
A2 materially distinct contract-enforcing immutable-wire evidence approach по C3 RCA. A2/C1 review1/2 зарезервирован; на FAIL STOP, автоматический C2/A3 не разрешён. Actual baseline28965861 input/calls8, все попытки/overruns сохраняются. Accounting-only без input/call caps и checkpoint gates. Stop real provider refusal/limit or explicit user stop, без обходов. No push/deploy/merge; local commit только routed PASS. Scope/backend/API/DB/deps unchanged, stage acceptance/следующий TASK не разрешены этим поручением.
