# TASK-MVP-05 A2/C1 — независимое R1 review

**Вердикт: PASS.** Все frozen AC-001..007 выполнены; F-01 закрыт новым A2 evidence, F-02/F-03/F-04 подтверждены на неизменном продукте и соответствующих оригиналах. Открытых BLOCKER/MAJOR, MINOR/NIT в пределах чек-листа не обнаружено. Это первый full-review slot 1/2 подхода A2, не третье review A1 и не итоговая приёмка этапа. Исторические A1/C1 и A1/C2 FAIL сохраняются.

## Идентичность и границы

Основание: прямое поручение MVP05_C3_A2_AUTHORIZED_20261026 и frozen `docs/tasks/TASK-MVP-05-A2-C1.md`, исходные scope/allowlist/AC из TASK-MVP-05.md, F-01..04 из TASK-MVP-05-C2.md. Прочитаны оба предыдущих review и A1/C3 RCA; старые numerical/role holds не применялись. Run `run_68046cea3eb4`; reviewer Task `task_36ad667176f9`, Dispatch `ctx_90f25030eaee`, terminal `term_4b9425d1-d82d-4b8f-bf07-890d307aa470`. Отдельный A2 implementer `task_0fdf463a7de1` / `ctx_11a366a6c3d4`, settlement `msg_b142517ece06`; reviewer реализацию не писал.

Workspace и Windows CWD: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`; baseline и actual HEAD `318e6336737ee635abf593c2643f26daba273f86`. Submission uncommitted. Полностью просмотрены tracked frontend diff от baseline и новые `api/batches.ts`, `components/BatchForm.tsx`, `pages/BatchesPage.tsx`. Восемь продуктовых файлов находятся в исходном allowlist: эти три файла, App.tsx, Nav.tsx, styles.css, types/api.ts, vite.config.ts. A2 продукт не менял: соответствующие текущие байты совпадают с C2 manifest. Остальные tracked ROADMAP/workflow изменения и поздние receipts принадлежат отдельно разрешённой работе координатора.

Reviewer независимо сравнил SHA256 и размер **46/46 A2 entries и 139/139 C2 entries**, расхождений нет. Использовалось read-only FileStream/FileShare.ReadWrite, включая занятые старые логи. Manifest identities:

- `TASK-MVP-05-A2-C1-hashes.json`: `9D6A06CBB2AB3B1F047314D7CB4AA2BBCEEF5FEB499A2547CD8F3053BF2B6417`.
- `TASK-MVP-05-C2-hashes.json`: `5B2F2F24BADBE4C94DC376354B6E2C7DA5F2FDC7409808B5388943BB0CB939CA`.

Первый включает текущие product, contract sources, fixture, wire/browser originals и report; manifests не включают сами себя. Проверка хешей устанавливает финальную идентичность, а не независимо восстанавливает порядок создания файлов. Ни один hashed artifact reviewer не менял. Actual protected Git diff по app/alembic/tests/package.json/package-lock.json пустой; Git status не выявил посторонних продуктовых изменений. Это проверка файлов, не аудит живой DB. Изолированный MOCK явно обозначен и не выдаётся за real-backend/DB round-trip.

## Frozen AC

| Критерий | Disposition | Основание |
| --- | --- | --- |
| AC-001 | PASS | App/Nav подключают экран `/batches`. A2 HTML headers/body: HTTP200 text/html, SPA root и main.tsx; API headers/body: HTTP200 application/json, список. A2 config5176/8002 повторяет product GET/Accept/path negotiation для Batch; production target8000 сохранён. A2 browser URL localhost:5176/batches существует, screenshot содержит навигацию. Настоящий reload наследуется из hash-verified C2 browser-reload-result: URL localhost:5175/batches, type reload, status200, text/html. A2 navigation:navigate не засчитан как reload. |
| AC-002 | PASS | Код, A2 list/detail originals и просмотренный screenshot показывают все шесть полей, date DD.MM.YYYY, null как тире, quantity строкой. GET1 и GET29 подтверждают detail lookup. List limit26/offset0 даёт lookahead для25 строк, offset25 возвращает26..29; Prev enabled/Next disabled на странице2. Loading/empty/error/retry — отдельные ветви текущего BatchesPage.tsx; пустая страница не блокирует Prev. Hash-verified C2 retry-error/retry-success UI и edge-case404 originals подтверждают ограниченные error/retry/missing-record сценарии. |
| AC-003 | PASS | Actual POST ordinal10 возвращает201 для существующего mock variant7, quantity string12345.67, ненулевой future date2027-02-03; GET29 ordinal11 возвращает ту же запись. Browser create-ready и created согласуются с wire. BatchForm требует positive integer variant, disabled pending submit, rejected submit не вызывает onSaved. A2 отрицательные POST/PATCH Quantity probes возвращают422 без изменения state; прежний C2 browser422 не считается positive create. |
| AC-004 | PASS | Отдельный PATCH29 ordinal16 содержит только batch_number, ordinal21 — только manufacture_date:null; response и explicit GET29 ordinal25 сохраняют variant7, edited number, quantity12345.67, unitkg. Current BatchForm.tsx:44–52 формирует только изменённые поля и явный null для пустых nullable. Variant остаётся required. В Batch API/UI нет PUT/DELETE, uniqueness/409 запрета или новых связей. Список после save refetch, final page2/detail показывают актуальное состояние. |
| AC-005 | PASS | Quantity проходит как string/null; Number применяется только к variant ID. Quantity/unit независимы, future date не запрещена. Read AbortController и aborted checks, mutation mounted/submission guards, create selection epoch подтверждены текущим кодом и hash-verified delayed POST/PATCH/form-change action/result originals. Safe client отображает собственные404/422/network сообщения, не raw detail/SQL; фактические C2 transport ошибки и UI list retry просмотрены. |
| AC-006 | PASS | A2 originals доказывают coherent browser list→detail1→create29→GET29→edit29→clear29→GET29 после clear. Все mutation/read шаги относятся к одной новой записи29; product/variant lookup подтверждает variant7. Wire statuses/bodies и промежуточные UI snapshots согласованы; screenshot просмотрен через view_image. Native labels/select/date/buttons позволяют клавиатурную работу. Document→Batch/Product действий нет. MOCK разрешён и не касается рабочей DB/storage. |
| AC-007 | PASS | Все product hashes совпали с окончательным C2 кодом; прочитаны полные C2 typecheck/build logs с точными WSL commands/CWD/Node24.22.0/exit0. По reuse rule не перезапускались. Просмотрены A2 diff-check log/report exit0, empty protected-diff, identity/status; independently просмотрены actual frontend diff/status/HEAD и protected diff. Scope соблюдён, backend/dependencies не менялись. A2 manifest46 и inherited139 совпали. |

## Findings и closure provenance

### F-01 — прежний MAJOR, закрыт в A2

Источник исходного FAIL: C2 review F-01, permissive fixture и alias recorder; старые ID29/32 с недопустимыми Quantity остаются неуспешными доказательствами A1. Они не используются для положительной приёмки A2.

Ожидание: один API-valid positive CRUD trace с ненулевой будущей датой, отдельными edit/clear и detail GET после clear; неизменные реальные request/response/status snapshots. Наблюдение A2 соответствует ожиданию:

| Ordinal A2 api-log | Request/status | Сохранённый response |
| --- | --- | --- |
| 1/2 | GET /batches?limit=26&offset=0,200 | Seeded список; browser-list подтверждает экран,6 полей и страницу1. |
| 6 | GET /batches/1,200 | DETAIL-01, variant7, date2026-01-01, quantity1.00, kg. |
| 10 | POST /batches,201 | Новый ID29, A2-BROWSER-001, variant7, date2027-02-03, quantity string12345.67, kg. |
| 11 | GET /batches/29,200 | Точно исходный created record29 с ненулевой датой и исходным номером. |
| 16 | PATCH /batches/29,200; только batch_number:A2-BROWSER-001-EDITED | Изменён номер; date/quantity/unit/variant сохранены. |
| 21 | PATCH /batches/29,200; только manufacture_date:null | Очищена дата, остальные поля сохранены. |
| 24→25 | GET28, затем GET29, оба200 | Явный повторный GET29 после clear: edited number, null date, variant7, quantity12345.67, kg. |

`TASK-MVP-05-A2-api-log.json:1` содержит25 событий: проверены полный bounded порядок, все mutation bodies/statuses, detail bodies, product/variant responses и обе pagination страницы. `crud-trace.json` отбирает ordinals1/6/10/11/16/21/25 и согласуется с оригиналом. Это инспекция originals, не доверие флагам verifier. Browser create-ready подтверждает выбранный variant7/date/quantity/unit; created показывает исходные номер и03.02.2027, edited — новый номер и ещё ненулевую дату, cleared-ui/final-detail — null при сохранённых остальных полях. Final screenshot показывает ID29 и страницу2/end. Выбор28 перед29 объясняет реальный новый GET, отсутствовавший в первом failed trace-verifier запуске.

Contract provenance: `app/api/batches/schemas.py` импортирует Measurement как Quantity; `app/api/variants/schemas.py:19–20,30–50` задаёт finite positive Decimal, maximum99999999.99, scale2. Значение12345.67 удовлетворяет контракту. A2 fixture.py:14,100,116 импортирует и вызывает настоящие BatchCreate/BatchUpdate; rejection выполняется до next_id/rows.append/row.update. В validation.json POST scale3 и PATCH zero/scale3 получили422, их request/status/response совпадают с api-log ordinals3..5. State-before и state-after wire strings совпадают; это bounded fixture smoke, не новый backend test.

Temporal provenance: fixture.py:40–51 сначала вычисляет `response_wire`, сохраняет строку в event и отправляет **те же UTF-8 bytes** через wfile.write. request_json сохраняет исходный прочитанный request wire; record:53–62 хранит строку и metadata. Последующее row.update:129 меняет только mutable store; строки событий уже отделены от row. Actual POST10/GET11 после обоих PATCH всё ещё содержат исходный номер/date; PATCH16 сохраняет ненулевую дату, PATCH21/GET25 — null. Это устраняет прежнюю alias проблему, а не только меняет тестовое число. Repro reviewer: parse api-log/validation/crud-trace originals, сопоставить перечисленные ordinals, текущий validator и serializer/send/update source, затем промежуточные browser snapshots. Никакого нового исполнения fixture/verifier не требовалось.

### F-02 — прежний MAJOR, closure C2 подтверждён

Место: `BatchForm.tsx:17–19,39–40,55–60`, `BatchesPage.tsx:25,52–56,68–76,95`. Ожидание — late POST/PATCH после смены selection/form/unmount не перетирает новый выбор. Наблюдение: mounted/generation проверяется до onSaved/error/finally, field/variant edit инвалидирует submit; выбор снимает edit, create callback проверяет selection epoch. Все файлы совпали с reviewed C2 bytes.

Просмотрены underlying C2 stale-patch/post/formchange action и result JSON, post-setup delay2500ms, fixture-8001.py:67 delay2s. PATCH A→B result оставляет detail ID2 SELECT-B/formCount0; delayed POST result — ID2/formCount1/«Создание партии»; field-change result — текущая edit форма1 с quantity88.25. Ожидание соблюдено. Repro/provenance: соответствующие `TASK-MVP-05-C2-browser-stale-*-action/result.json` и текущие guards; это inherited executed browser MOCK evidence, не повторный запуск и не API-valid full CRUD acceptance старых ID29/32.

### F-03 — прежний MAJOR, closure C2 подтверждён

Место: `frontend/vite.config.ts:35,45–60`, `BatchesPage.tsx:28–49,77–90`, reused `api/client.ts` status mapping и apiRequest. Ожидание — реальные URL/reload/negotiation и ограниченные safe404/422/network/retry/pagination proof. Просмотренные C2 reload-result, edge-case-results, retry-error-ui/retry-success-ui имеют actual URLs/statuses и безопасный UI alert/Retry; успешный retry показывает страницу2/end. A2 дополняет headers/body и pagination originals на5176. Для404/422/network edge results — browser transport fetch; это не отдельный UI screenshot каждой ошибки. Safe UI mapping и rejected mutation path подтверждены кодом; требование не расширялось. Repro — прочитать эти originals вместе с mapping и Batch catch ветвями. Loading/empty ветви проверены статически, их отдельные новые screenshots не заявляются.

### F-04 — прежний MINOR, closure подтверждён

Место: A2/C2 manifests `.files`; expected — финальная идентичность product/evidence/report без self-entry. Наблюдение —46/46 и139/139 hashes/sizes совпали, self-entry отсутствует. Repro — независимое read-only SHA256/length сравнение каждого entry; выполнено reviewer. C1 report hash mismatch остаётся историей; старый evidence не исправлялся.

## Проверки: executed implementer, inherited, reviewer

Reviewer не запускал product tests, typecheck/build, браузер, API, fixture/verifier, backend/DB команды; exception rerun не понадобился. Все required complete checks переиспользованы по policy.

| Кто / точная команда или действие | CWD / результат / original |
| --- | --- |
| C2 implementer: `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'` | WSL frontend, Node v24.22.0, tsc --noEmit, exit0; C2-typecheck.log. |
| C2 implementer: `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'` | Тот же CWD/runtime, tsc+Vite8.3.4/63 modules/built765ms, exit0; C2-build.log. |
| A2 implementer: `curl.exe -sS -D docs/workflow/evidence/TASK-MVP-05-A2-html-headers.txt -o docs/workflow/evidence/TASK-MVP-05-A2-html-body.html -H "Accept: text/html" http://localhost:5176/batches` | Windows repo; report exit0, underlying200 text/html и SPA body. |
| A2 implementer: `curl.exe -sS -D docs/workflow/evidence/TASK-MVP-05-A2-api-headers.txt -o docs/workflow/evidence/TASK-MVP-05-A2-api-body.json -H "Accept: application/json" "http://localhost:5176/batches?limit=26&offset=0"` | Windows repo; report exit0, underlying200 application/json и list body. |
| A2 implementer: WSL `.venv/bin/python docs/workflow/evidence/TASK-MVP-05-A2-fixture.py`, validation-probe и browser capture | Точные launcher команды в A2-C1-evidence.md; mock source, validation JSON,25-event API log, browser snapshots и screenshot просмотрены. Script success assertions не заменяли inspection originals. |
| A2 implementer: `git diff --check`, protected diff/status/identity | Report exit0; A2-git-diff-check.log содержит только CRLF warnings; protected-diff.log пустой. C2-diff-check.log также явно exit0. |
| Reviewer: `git status --short`, `git rev-parse HEAD`, `git diff 318e6336737ee635abf593c2643f26daba273f86 -- frontend`, `git diff --name-only 318e6336737ee635abf593c2643f26daba273f86 -- app alembic tests frontend/package.json frontend/package-lock.json` | Windows repo, exit0; HEAD=baseline, frontend allowlist, последний output пустой. |
| Reviewer: file/source/JSON inspection, SHA256/size comparison46+139, `view_image` A2-browser.png, own native metadata, Orca check/heartbeat | Read-only; никаких новых execution checks и repairs. Единственная запись reviewer — этот report. |

A2 failed attempts (первый Vite config import, date/option interaction, первый verifier без нового GET) честно сохранены в report; финальные underlying artifacts разрешают соответствующие пробелы. A2 listeners после capture остановлены владельцем; для artifact review они не нужны. Новые ports5176/8002 и evidence-only config не меняют архитектуру/продуктовый scope.

Tooling reviewer: ошибочно запрошены несуществующие docs/workflow/tasks пути вместо docs/tasks, затем прочитаны правильные bounded files; позднее неверно назван diff-check.log вместо git-diff-check.log, затем прочитан настоящий manifest entry. Некоторые combined reads были обрезаны выводом: релевантные данные перечитаны отдельно или распарсены bounded JSON; clipped output не считался полным доказательством. Прямой ReadLines собственного live rollout получил file lock; shared read успешно прочитал только metadata поля. Эти read failures не являются product checks или product defects.

## Accounting и завершение

Actual native rollout: `C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T21-40-17-01a17983-6641-70f2-ad67-8c49ae781675.jsonl`; turn_context `2026-10-26T18:40:32.156Z`: **gpt-6.1-sol / medium**. Launch receipt A2-C1-reviewer-launch.json также сообщает requested/effective Sol medium. Доступный snapshot18:43:09.261Z: input1091321, включая cached985728 (не суммировать повторно), output4244, reasoning416, total1095565. Это промежуточный snapshot до финализации, не settled usage; coordinator устанавливает final actual после worker_done. Переданный cumulative40806402/calls9 сохранён, этот accounting call10. Caps/reserves/checkpoint asks/pauses не применялись. Provider primary61%, secondary41%, refusal/exhaustion не наблюдался; reset/account/plan/session bypass отсутствует.

PASS относится только к TASK-MVP-05 A2/C1 в frozen scope и допустимому MOCK evidence. Stage acceptance, commit/push/merge/deploy и successor TASK не выполнялись. Только coordinator вправе записать статус/приёмку и решить дальнейшее действие. После matching worker_done dispatched review завершается.
