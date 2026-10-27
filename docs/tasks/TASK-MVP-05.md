# TASK-MVP-05 — Batch frontend

Статус: FAIL / NOT_ACCEPTED (независимое R1 review завершено; дальнейшая работа остановлена). Риск R1, подход A1, цикл C1.
Run run_68046cea3eb4; main, baseline318e6336737ee635abf593c2643f26daba273f86.
Предшественник MVP-04 PASS. Основание: повторное прямое поручение пользователя
26.10.2026; ROADMAP v1.2 и VISION, без изменения требований/архитектуры.
Координатор Codex; единственный отдельный writer gpt-6-luna / medium.

## Scope и контракт

Реализовать экран списка, просмотра деталей, создания и редактирования партий,
доступный из навигации. Использовать только существующие POST /batches,
GET /batches, GET /batches/{batch_id}, PATCH /batches/{batch_id}.
Подключить Vite proxy /batches к существующему backend127.0.0.1:8000.
SPA navigation не должна перехватываться API proxy: HTML GET экрана возвращает
SPA, JSON GET и POST/PATCH идут к API. Допустим один экран с detail/form panel;
отдельная архитектура/новый router framework не нужны.

Поля BatchRead: id, variant_id, batch_number, manufacture_date, quantity,
quantity_unit. variant_id обязателен и положительный, выбирается из существующих
типоразмеров через имеющиеся product/variant API; понятные подписи и ID fallback.
Четыре остальных поля nullable. Quantity отправлять точной строкой или null,
не преобразовывать через float; дата ISO YYYY-MM-DD или null.
PATCH различает неизменённые поля и явную очистку nullable полей (null).
Не вводить uniqueness, DELETE/PUT, поиск/фильтры, новые связи или новые API.
Список использует server limit/offset и корректно обрабатывает конец/пустую страницу.
Детали получать через GET id; создание/правка обновляют отображение из API.
Сохранять готовые паттерны ошибок, отмены/stale запросов, pending submit и стили.
Ошибки сервера показывать безопасными UI сообщениями, не выводить raw detail/SQL.

## Allowlist

Создать frontend/src/api/batches.ts, frontend/src/pages/BatchesPage.tsx,
frontend/src/components/BatchForm.tsx; при необходимости
frontend/src/hooks/useBatches.ts.
Изменить только для Batch: frontend/src/types/api.ts, frontend/src/App.tsx,
frontend/src/components/Nav.tsx, frontend/vite.config.ts,
frontend/src/styles.css, frontend/README.md, docs/PROJECT_STATUS.md.
Допускаются TASK-MVP-05-* evidence/log/screenshot/smoke артефакты только под
docs/workflow/evidence/. Workflow TASK/STATE/HISTORY/APPROVALS ведёт координатор.

Не менять backend app/**, API contracts, tests/**, alembic/**, DB schema/data,
dependencies/package-lock/package.json, .env, .venv, storage, node_modules.
dist может генерироваться обязательным build, не редактировать вручную/не коммитить.
Нет auth, Document→Batch/Product linking, миграций, deployment, push/merge.
Существующие document/variant UI только переиспользовать, не переписывать.
Не делать commit до независимого routed PASS; не запускать других workers/reviewer.

## Замороженный observable checklist

| ID | Критерий | Доказательство |
| --- | --- | --- |
| AC-001 | Навигация ведёт на Batch экран; доступны список и details; прямое открытие/refresh экрана работают. Vite различает SPA HTML и API JSON. | Реальный browser snapshot/URL и HTTP content-type/status через Vite; screenshot. |
| AC-002 | Список отображает шесть полей с понятными null/date/quantity; loading/empty/error/retry различимы, limit/offset и конец страницы корректны. Detail GET id показывает выбранную партию; отсутствие записи безопасно обработано. | UI/API журнал со status и состоянием; просмотр pagination/query и detail результата. |
| AC-003 | Create с существующим variant_id и nullable реквизитами сохраняется POST201; последующий GET показывает ту же запись и Decimal string/date. Невалидный ввод не считается успехом; submit блокируется на время запроса. | Browser create и фактические request/response записи; последующий GET. |
| AC-004 | Edit использует PATCH и сохраняет отсутствующие поля; nullable очищаются null, variant остаётся обязательным; после сохранения список/details актуальны. Дубликаты разрешены. | Browser edit/clear и фактический PATCH payload/response/GET; просмотр отсутствия DELETE/PUT/409 логики. |
| AC-005 | Quantity не проходит через float; допустимы независимые quantity/unit и будущая корректная дата. Серверные 404/422/network ошибки безопасны; stale/unmount запросы не перетирают новый выбор. | Код и ограниченные UI/API edge-case записи без новых backend тестов. |
| AC-006 | Доказуемый UI/API сценарий: list→detail→create→read→edit→clear→read через имеющиеся Batch API. Понятные подписи/клавиатурные controls, нет Document→Batch/Product действий. | Фактический пошаговый browser/API evidence с URL/ID/status/payload и screenshot; без выдуманных результатов. |
| AC-007 | WSL frontend typecheck и build завершаются exit0 на конечном коде. Backend/API/DB и зависимости неизменны; diff в allowlist. | Точные команды/CWD/exits и stdout logs; git diff/check/status, hash manifest. |

## Проверки и evidence

Из Windows CWD D:/Antigravity/EquipmentDocumentationRegistry:
wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'
wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'

Сохранить точные command/CWD/exit/output для обоих в отдельные небольшие логи.
Реальный UI smoke допустим с временными API fixtures/mock transport,
явно обозначенными как mock, без изменения рабочей DB/storage; проверить реальные
URL/method/payload/response contracts существующего API. Не выдавать mock за
real-backend round-trip. При доступном изолированном стенде использовать его
без product DB изменений. Для proxy дополнительно доказать реальное forwarding
к локальному fixture endpoint либо существующему backend read-only.
Не устанавливать новые зависимости. Browser/Orca CLI использовать только по
реальной installed help. Если необходимый ресурс недоступен — задать вопрос
координатору через live preamble, не имитировать UI checks.
Backend3771 passed — historical reuse из MVP-04, новый pytest не запускать.

Evidence docs/workflow/evidence/TASK-MVP-05-C1.md: фактический diff/baseline,
Orca lifecycle IDs, AC mapping, artifacts, limitations, failed checks сохранены.
git diff --check; git diff --name-only; git ls-files --others --exclude-standard;
git diff -- app alembic tests frontend/package.json frontend/package-lock.json
(последний diff пустой). До worker_done проверить mailbox и сообщить фактическое
завершение с текущими Task/Dispatch, не присваивая проектный PASS.

## Лимиты и приёмка

Логический TASK-MVP-05 R1, A1/C1. Совокупный input ceiling1000000 (cached включён).
План максимум2 Codex worker calls под явным пользовательским маршрутом:
implementation Luna medium call1 (reserve600000 включая финализацию),
independent R1 Sol medium call2 (reserve250000), safety150000.
Рутинный reviewer НЕ запускается исполнителем и НЕ запускается до worker_done.
Перед reviewer координатор проверяет остаток/актуальные routing/review policy;
экспертные вызовы/эскалации не считаются автоматически разрешёнными.
A1 максимум2 полных review; счётчики/расход не сбрасывать; budget2calls имеет
приоритет над доступностью последующих correction/review slots.
Остановиться до исчерпания резерва; отдельный snapshot actual model/effort,
rollout/input metadata в evidence, без secrets/prompts. На provider exhaustion
BLOCKED и остановка без reset/account/plan/session обходов.
Только локальный commit после routed PASS; push/merge/deploy запрещены.

Checkpoint13:31:15Z: actual8812350input/1000000,call1/2; workerfailed/released, no review/PASS. Evidence TASK-MVP-05-C1.md и usage-final.json; прежние лимиты/расход не сброшены. Нужен явный resource decision до любого продолжения.

## MVP05_REVIEW_ONLY_9300000_20261026 — актуальное исключение

Пользователь явно разрешил только один независимый Sol medium reviewer call2/2.
Новый совокупный input ceiling9300000; used8812350 сохранён, включая cached input.
Reviewer hard reserve250000 ВКЛЮЧАЯ финализацию; safety237650 не расходовать worker.
Исторические cap1000000/reserve600000 и превышения7812350/8212350 сохранены.
A1/C1, первый full-review slot1/2; frozen AC001..007 и submission неизменны.
Только чтение ограниченного полного diff/evidence и один review report.
Нет кода, исправлений, тестовых повторов, новых функций, stage acceptance,
commit/push/merge/deploy. После любого verdict остановиться; новые работы
требуют отдельного разрешения/бюджета. Рутинный R1 Codex review здесь явно
разрешён пользователем как исключение. Источник — APPROVALS с точным решением.

Final R1 review: FAIL, report docs/workflow/reviews/TASK-MVP-05-C1.md, F01/F02/F03 MAJOR иF04MINOR. Calls2/2,full-review1/2,failed-review1,input9210419/9300000. Revieweractual398069 превышает reserve250000 на148069; все прежние overruns сохранены. Только verdict/accounting, без исправлений/новых проверок/commit/push; поручение завершено остановкой.

## C2 explicitly authorized
MVP05_C2_EXTRA_1500000_20261026: frozen correction checklist [TASK-MVP-05-C2.md](TASK-MVP-05-C2.md) связывает F01..F04 и carry-forward AC001..007. C1 FAIL/used9210419 не сбрасываются. Totalcap10710419,calls4 cumulative; implementation3/4 Luna900000/checkpoint600000, review4/4 Sol450000/slot2/2, safety150000. Сейчас C2 подготовлен; PASS только после review. No push, commit только после C2 PASS.

## C2 blocked mid-implementation — guard RCA

Текущий статус C2: BLOCKED / NOT_ACCEPTED. ctx_00fa3aee8c79 failed/stopped,
нет worker_done/evidence completion. Call3actual825330; C1actual9210419;
cumulative10035749/10710419. Calls3/4 consumed; full-review2/2 не запускался.
Guardian threshold800000 ошибочно остановил до implementationcap900000.
RCA — преждевременная coordinator cancellation, не исчерпание выделенногоcap.
Remaining impl74670+review450000+safety150000=674670; user указан675089
с арифметическим расхождением419, ceiling и резервы не увеличиваются.
Никаких code edits/reviewer/implementation retry/new Dispatch без нового
решения. Call3 израсходован остановкой, aggregate token balance не создаёт
дополнительного writer call. Partialcode/evidence/oldFAIL сохраняются.
Rawstopreceipt записан доresource release; см. STATE/HISTORY.

## C2 continuation authorized
MVP05_C2_RESUME_CALL4_11535749_20261026: [frozen resume](TASK-MVP-05-C2-resume.md). Currentactual10035749 preserved,cap11535749; call4/5 Luna≤900k,call5/5 Sol≤450k,safety150k. Same C2 scope/checklist, original guard NEVER rerun, newobserver alert-only600k. C1 FAIL/stopped call3 retained, no early PASS.

## Call4 continuation stopped — current BLOCKED

Call4 Luna ctx_5be9101c483f manually stopped after actual923618 exceeded own900000;
no worker_done/evidence completion, no C2 review/acceptance.
Cumulative10959367/11535749,remaining576382,calls4/5 consumed.
Sol450000+safety150000 remain unspent but cannot both fit: shortfall23618.
Observer was read-only/alert-only, oldguard notrun; manual coordinator reaction
to600k checkpoint was late. No new code/retry/reviewer/commit/push permitted
by current budgetfailure stop condition. All prior scope/criteria/history intact.

## C2 call5 explicit resume
MVP05_C2_CALL5_12435749_20261026: [frozen addendum](TASK-MVP-05-C2-call5.md). Actual10959367preserved,cap12435749; Luna call5/6≤900k, Solcall6/6≤450k,safety126382. Blocking450k,substantive≤700k,finalize≤850k. Oldguard/terminalneverreuse; no scopechange/reset/earlyPASS.

## Call5 outcome: premature settlement, coordination BLOCKED

Actualcall5 203691input<450kcheckpoint and<900kcap; worker_donefailed без
substantiveC2 и без completionreport. Coordinatorpathstatus не был formalreply
на initialblockingask; worker не дождалсяreply/завершился, replyполучилinactive.
Нет C2full-review/verdict. Parentactual11163058/12435749,remaining1272691;
calls5/6 consumed, call6только finalSolreview. History/noreset сохраняются.
Никакой новогоwriter/reviewer/rechecks/commit/push автоматически не разрешается.

## C2 call6 explicitresume
MVP05_C2_CALL6_12639440_20261026: [frozenaddendum](TASK-MVP-05-C2-call6.md),actual11163058 preserved,cap12639440; Lunacall6≤900k,Solcall7≤450k/fullreview2/2,safety126382. StartownZERO,no upfrontasks; mandatory450kask/formalreply; substantive≤700k,final≤850k. Scope/C1history unchanged,noearlyPASS.

## Call6 latest outcome — budget BLOCKED, not C2 acceptance

Own actual1155000/900000,over255000; cumulative12318058/12639440,
remaining321382. Calls6/7consumed; finalSol450000+safety126382 cannotfit,
shortfall255000. Formalcheckpointreply was sent butlate; worker stoppedmanually
afterconfirmedowncapexceeded,rawreceiptpreserved,noworker_done/completionreport.
Partialcode/evidence/historypreserved. No C2review/PASS, no morecalls/checks/
commit/push/stageacceptance. ExistingC1failures/overruns notreset.

## CURRENT AUTHORITY: accounting only
MVP05_C2_ACCOUNTING_ONLY_20261026 directuserupdate removes ALL hardinputcaps/reserves/blockingtokencheckpointgates. Oldnumbers/stops historyONLY. [Currentcompletionaddendum](TASK-MVP-05-C2-completion.md) governs sameC2scope/criteria; actual12318058/allcalls preserved. Luna completion then finalSolreview2/2, noearlyPASS, no push/deploy; localcommitonlyPASS.

## 2026-10-26 17:26Z — A1/C2 final independent review FAIL; chain stopped
Sol gpt-6.1-sol/medium (native turn_context confirmed), task_c90a6464b95b / ctx_20bcbbca831b, matching worker_done msg_b2454d21cbb3 at17:26:02Z. Final report docs/workflow/reviews/TASK-MVP-05-C2.md: FAIL, F-01 MAJOR open on AC003/004/006. Full CRUD scenarios ID29/32 have out-of-contract Quantity; fixture response_body aliases mutable rows so historical POST/GET bodies reflect later PATCH/clear. API-valid create/read alternatives lack complete edit/clear sequence. F02/F03/F04 closed; 139/139 manifest hashes/sizes matched; inherited final typecheck/build exit0 reused, no extra tests/fixes. C1 FAIL remains history; full reviews2/2 consumed, failed-review count2.
Final reviewer native input1525345, cached1427968 INCLUDED, output10097, reasoning1558, total1535442; observed17:26:07.978Z. Receipt evidence/TASK-MVP-05-C2-final-review-usage-final.json. Prior27440516 +1525345 = cumulative28965861 input. Calls8 settled; no reset/refund. Primary40% reset1793050838, secondary38% reset1793600447; no new provider refusal. Hard token caps/checkpoint pauses remain removed.
Reviewer resource released17:26:12Z, processAction closed_agent_terminal, transcript captured; worker-show receipt evidence/TASK-MVP-05-C2-final-review-settled.json. Delivery82034089e1b7 ACKed. Reclaimable enumeration empty. User-owned Luna terminal retained unchanged.
Product remains NOT_ACCEPTED; dependent chain BLOCKED under explicit C2 FAIL=>STOP authority. No third review, fixes, C3, next TASK, local commit, push/merge/deploy. All uncommitted product code, C1/C2 evidence and earlier failures preserved. Stop caused by quality verdict, not budget. Further work requires a separate user decision.

## MVP05_C3_A2_AUTHORIZED_20261026
Пользователь «Ну делай что нужно)» прямо разрешил C3 read-only RCA и A2/C1 в прежнем frozen F01..F04+AC001..007 (TASK-MVP-05.md/TASK-MVP-05-C2.md; baseline318e6336737ee635abf593c2643f26daba273f86). Codex coordinator, один gpt-6-luna/medium writer, затем отдельный gpt-6.1-sol/medium reviewer после worker_done/evidence. A1 FAIL/FAIL и review2/2 сохранены, третьего A1 review нет.
A2 materially distinct contract-enforcing immutable-wire evidence approach по C3 RCA. A2/C1 review1/2 зарезервирован; на FAIL STOP, автоматический C2/A3 не разрешён. Actual baseline28965861 input/calls8, все попытки/overruns сохраняются. Accounting-only без input/call caps и checkpoint gates. Stop real provider refusal/limit or explicit user stop, без обходов. No push/deploy/merge; local commit только routed PASS. Scope/backend/API/DB/deps unchanged, stage acceptance/следующий TASK не разрешены этим поручением.
Current additive scope/checklist: TASK-MVP-05-A2-C1.md; A1/C3 read-only RCA complete, A2/C1 authorized without reset.

## 2026-10-26T18:46Z — routed TASK-MVP-05 A2/C1 PASS
Independent gpt-6.1-sol/medium task_36ad667176f9/ctx_90f25030eaee worker_done msg_e550b99b5d97 at18:45:51Z, report reviews/TASK-MVP-05-A2-C1.md. All AC001..007 PASS, F01 closed via actual schema-backed immutable same-ID trace, F02/F03/F04 confirmed. No open in-scope findings;46 A2+139 inherited hashes/sizes matched; no routine reruns. A1 FAIL/FAIL/review2/2 remain unchanged; A2 used review1/2, total fullreviews3, failed2, C3 diagnostics1. A2/C2/A3 not started.
Reviewer final input1853222 (cached1738112 included), output10030; prior40806402=>cumulative42659624 input/calls10 settled. Receipt evidence/TASK-MVP-05-A2-C1-reviewer-usage-final.json. Provider primary64%,secondary41%; no refusal; accounting-only remains. Reviewer released closed_agent_terminal/transcript captured; delivery_399fedfe6d41 ACKed. No push/deploy/merge/stage acceptance/next TASK. Local product commit authorized after this routed PASS; workflow/evidence and all history preserved.
