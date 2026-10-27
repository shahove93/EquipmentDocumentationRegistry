# TASK-MVP-06 — независимая итоговая приёмка этапа

**Вердикт: PASS по ST-001…ST-006.** Утверждённый локальный MVP + Batch принят на `06f58065022db9c58524909027ddc2d454f7071f`. Открытых BLOCKER/MAJOR не обнаружено. Одно MINOR замечание о документном drift приведено ниже; оно не меняет frozen scope. **ST-007 — последующее обязательство координатора:** написать FINAL-REPORT и зафиксировать итог после этого PASS. Настоящий файл не является FINAL-REPORT и сам по себе не переводит очередь в COMPLETE.

Дата завершения: 2026-10-27, Europe/Moscow. Stage/A1/C1, независимое полное review **1/2**, accounting call **12**. Reviewer не реализовывал продукт и не исполнял stage suite. Применены autonomous-development, routing-and-budget, review-policy, version-matched Orca orchestration guide и текущая прямая authority пользователя: отдельный Codex review, после PASS — FINAL-REPORT координатором, при FAIL — остановка без исправлений. Старые роли OpenCode/Nemotron и внутренние ресурсные потолки не переопределяют это поручение.

## Идентичность и происхождение

- Workspace/Windows CWD: `D:/Antigravity/EquipmentDocumentationRegistry`, ветка `main`, без другого worktree.
- Run: `run_68046cea3eb4`; reviewer Task `task_391aaf782f69`, Dispatch `ctx_97a10d402fdd`, terminal `term_64e33575-cd37-461b-bef5-2db42d2c347f`; coordinator `term_d727cc23-31e8-42eb-a295-c42268e0c645`.
- Executor: `task_bfc414bad7a6` / `ctx_7ddb18624654`, Codex Luna/medium. Matching completion `msg_217815cb0dbe` задан handoff/frozen TASK; непосредственно просмотрены execution report, native command metadata/logs, launch/accounting/release artifacts. Release receipt подтверждает `released`, `closed_agent_terminal`, archive captured для того же Dispatch. Утверждение worker_done не использовалось вместо проверки артефактов.
- Actual HEAD до остановки и после разрешённого возобновления: `06f58065022db9c58524909027ddc2d454f7071f`. Delivery — локальный commit восьми frontend-файлов. Backend/test/alembic diff от принятого MVP04 `0db1f9ede4b4e4b462ded4ce49a2b45967712732` до HEAD пуст. Предыдущий индекс/скачивание — MVP03 `6827ed3ae843b1d3f497257c3796144aab44e234`.
- `git diff --name-only HEAD -- app tests alembic frontend requirements.txt alembic.ini` пуст. Дерево **не объявляется clean**: ROADMAP/APPROVALS/HISTORY/STATE и многочисленные workflow/evidence файлы — отдельные сохранённые изменения. Никаких product edits, commit/push/merge/deployment этот reviewer не выполнял.

Primary pack: [stage evidence](../evidence/TASK-MVP-06-evidence.md), [artifact manifest](../evidence/TASK-MVP-06-hashes.json), pre/post manifests, шесть `*.meta.json`, полные stdout/stderr, migration-source и пустые product-diff snapshots. Независимое SHA-256/length сравнение дало **26/26 совпадений**, self-entry отсутствует. Pre/post содержат по **190** source entries, их полный сериализованный состав одинаков; все **190/190** совпали с текущими файлами. До suite snapshot: `2026-10-26T18:54:59.0858859Z`; после: `19:04:25.2638208Z`. Обе product-diff записи — 0 bytes. После ночной паузы hashes/source/HEAD перепроверены read-only, без нового исполнения продукта.

Manifest охватывает app/tests/migrations/frontend src, package manifests, requirements и alembic.ini; это ограниченный перечень, не снимок DB/storage или всего окружения. Дополнительно фактический Git diff и MVP05 A2 manifest подтверждают восемь frontend-файлов, включая vite.config.ts, которого нет в основном source scope. Проверены **46/46 A2 hashes/sizes**, включая контрактные источники, fixture и browser/wire originals.

| Артефакт | SHA-256 |
| --- | --- |
| TASK-MVP-06-hashes.json | `9D8031D093102232CE752676110258A688111F050EB55F9C26E8A973EFA0A993` |
| TASK-MVP-06-pre.json | `866E33455AF4FD8CB56E8AFAFE52073475757050A5E08A6910BA5CAF13699515` |
| TASK-MVP-06-post.json | `DBD18FDE24D5C147817C08453C1CB38D50717433472810BA5408034AE75B4EEA` |

Hashes устанавливают совпадение сохранённых байтов, не независимое восстановление времени их создания. Временная привязка опирается также на native command metadata и pre/post snapshots. Неразрешённых пробелов происхождения обязательной stage evidence не осталось.

## Frozen checklist

| ID | Disposition | Основание |
| --- | --- | --- |
| ST-001 | PASS | Actual main/HEAD совпадает с заданием; pre/post190 и current190 идентичны; product diff пуст; восемь frontend delivery-файлов соответствуют принятой подаче. Посторонние workflow изменения не скрыты. |
| ST-002 | PASS | Полные pytest stdout/stderr и native metadata прочитаны: exit0, **3771 passed, 1 warning in 471.65s**. Это исполнение Luna на final revision, не запуск reviewer. |
| ST-003 | PASS | Отдельные runtime/typecheck/build metadata и stdout/stderr: **Node v24.22.0**, exit0 каждого; tsc --noEmit и Vite8.3.4/63 modules. |
| ST-004 | PASS | Native Alembic current exit0: **e4b8c2d16a70 (head)**. Migration-count exit0: **13**; independently прочитаны 13 исходных revision/down_revision и migration-source. Единственный terminal source revision — e4b8c2d16a70, от a3f1c72d5b90, только индекс files(document_id,id). Reviewer миграции/DB команды не запускал. |
| ST-005 | PASS | Command/CWD/time/exit/logs, current revision, manifests и предыдущий реальный MVP05 A2 PASS согласованы. Старые FAIL не представлены как успешные проверки. Hashes финального stage pack не изменены. |
| ST-006 | PASS | Настоящее отдельное review сопоставляет VISION1.0, ARCHITECTURE1.0, ROADMAP1.2, ADR008/009/010, actual bounded code/diff и routed evidence. Обязательных повторных запусков или скрытого repair loop не было. |
| ST-007 | COORDINATOR NEXT | Только после этого PASS координатор пишет FINAL-REPORT с проверками, deliveryrevision, ограничениями и историей. Отсутствие будущего отчёта не является круговым prerequisite ST-006. |

## Реально исполненные stage checks

Все шесть команд исполнил stage executor 2026-10-26. Windows launcher CWD — корень workspace выше; `R=/mnt/d/Antigravity/EquipmentDocumentationRegistry`, `F=R/frontend` здесь только обозначения CWD. В таблице команды приведены полностью, без подстановок. Для каждого stem в `docs/workflow/evidence/` прочитаны `.meta.json`, `.stdout.log`, `.stderr.log`.

| Stem TASK-MVP-06-… | Exact command | WSL CWD; UTC start → end; native exit/result |
| --- | --- | --- |
| pytest | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | R; 18:55:06.6185055 → 19:03:10.6224470; **0**, 3771 passed/1warning/471.65s. |
| node | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && node --version'` | F; 19:03:21.4084495 → 19:03:23.0115695; **0**, v24.22.0. |
| typecheck | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'` | F; 19:03:28.7696888 → 19:03:31.2178059; **0**, tsc --noEmit. |
| build | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'` | F; 19:03:41.7191660 → 19:03:45.7713916; **0**, tsc + Vite8.3.4, 63 modules, built464ms. |
| alembic-current | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic current'` | R; 19:03:57.5503279 → 19:04:02.2823428; **0**, e4b8c2d16a70 (head). |
| migration-count | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py \| wc -l'` | R; 19:04:08.7794322 → 19:04:09.9349413; **0**, 13. Markdown escape перед pipe не часть shell command. |

Pytest warning — StarletteDeprecationWarning о httpx/TestClient в `.venv/lib/python3.14/site-packages/fastapi/testclient.py:1`; failed/skipped tests в итоговой сводке нет. Pytest/runtime/typecheck/build/count stderr пусты. Alembic stderr содержит INFO `PostgresqlImpl` и transactional DDL, обёрнутые Windows PowerShell в NativeCommandError diagnostic; это не ненулевой native exit. Pipeline count сам по себе доказывает exit последней команды, поэтому результат дополнен исходным списком 13 файлов и revision chain, а не выводом об успехе `ls` только по pipe exit.

**Reviewer execution exceptions: 0.** Pytest/typecheck/build/Alembic/browser/API/DB не перезапускались. Reviewer выполнял только чтение/поиск, SHA-256/size/JSON сравнения, `git rev-parse HEAD`, `git branch --show-current`, status/diff/show и Orca mailbox/heartbeat; успешные команды идентификации вернули exit0. Несколько объединённых чтений были обрезаны; необходимые source/log/JSON sections прочитаны отдельно или распарсены с ограниченным выводом. Ошибочно запрошенные пути `evidence/TASK-MVP-04-evidence-final.md` и отдельные frontend files.ts/documentVariants.ts не существуют; правильный review находится в reviews/, функции вложений/связей — в api/documents.ts. Эти read-tool ошибки не засчитаны как продуктовые проверки.

## Соответствие утверждённому MVP и архитектуре

| Выход / инвариант | Actual implementation и основание приёмки |
| --- | --- |
| Локальный реестр, CRUD реквизитов, материалы/справочники | `app/api/router.py:21` подключает существующие вертикальные срезы и Batch; `frontend/src/App.tsx:22` и Nav связывают реестр/карточку/материалы/партии. `api/documents.ts:31` строит существующие фильтры, `:63` и далее — карточку, файлы, варианты, историю. Baseline MVP00 routed PASS + неизменённые baseline paths, текущие full suite/build и bounded source inspection. Не заявляется новый browser прогон всех старых экранов. |
| ADR005/006: отдельные изделия/SDR, уникальный размер внутри изделия | Существующая Product→ProductVariant связь сохранена, `app/models/variant.py:34` задаёт UniqueConstraint(product_id,size_text); Batch ссылается на variant. Ни frontend Batch, ни новые API не вводят смешение размеров разных Products или новый SDR-контракт. |
| ADR008: pending/verified/rejected и история | `document_service.py:488`/`:543` — verify/reject, `:597` — требование вложения, `:485` — record_reopened для значимых реквизитов. Общий `transaction.py:50` блокирует документ, проверяет modified до populate_existing. `tests/test_documents_integration_api.py:170` реально описывает create→upload→verify→history→edit→reopen→reject→attach/detach→download с assertions статуса/истории/байтов; он входит в исполненный full suite. |
| ADR009: файлы и безопасная компенсация | `file_service.py:279`/`:287` сохраняет reopen+file одним commit; `:379`/`:388`/`:409` удаляет blob только после successful commit. Неизвестный detach commit сохраняет blob и журналирует. Файловая система не объявляется атомарной с PostgreSQL; сохраняются принятые ограничения. |
| MVP01: постоянный журнал | `logging_config.py:39`/`:73` — JSONL whitelist и append UTF-8 handler; `main.py:11` — lifespan configure/shutdown. Никаких последующих изменений этих принятых модулей по bounded Git comparison. Inherited MVP01 review подтверждает restart/process/idempotence tests; stage full suite зелёный. |
| MVP02: report-only reconciliation | `storage_reconciliation.py:86` сначала завершает inventory, затем один SELECT storage_key отдельным connection (`:147`); success=complete, canonical keys, LOG_FILE exclusion, safe failure, без DML/deletion. `local_storage.py:135` использует fd-relative обход/O_NOFOLLOW. CLI разбирает аргументы до ресурсов. Принятый C2 код этих модулей до HEAD не изменён; inherited C2 closure/fault/concurrency evidence + stage suite. |
| MVP03: integrity download и индекс | `app/api/files/download.py:51` копирует bounded chunks в TemporaryFile, сверяет SHA-256 до ответа, отдаёт именно snapshot; ClosingStreamingResponse закрывает его при завершении/отмене. Миграция e4b8c2d16a70:21 создаёт nonunique files(document_id,id). Current head/source и inherited C2 disk-backed ASGI/race/index checks согласованы с stage suite. |
| ADR010: атомарная замена связей, неизменный статус, корректный поиск | `document_variant_service.py:204` и далее: duplicates/transaction guard, shared lock, все FK до изменений, set difference и один commit; status/history не изменяются. `document_service.py:284`…`:337`: один correlated EXISTS по document_variants→variants→products, все material filters на одном варианте, затем order/limit/offset; number/status отдельны. Product/Batch links не участвуют. |
| MVP04: Batch API | `batches/schemas.py:28`/`:39`, `batch_service.py:38`, router:13 — Create/Get/List/Patch, required positive variant, nullable поля, Decimal, exclude_unset, один write commit/rollback, 404 unknown variant/record, limit/offset/id ASC. Нет DELETE/PUT или Document→Batch. `test_batches_openapi.py:21`/`:22` фиксирует **21 путь/38 операций**, входит в stage full suite. |
| MVP05: Batch UI и контракт | Полностью просмотрены восемь delivery-файлов/diff. BatchForm:33–60 передаёт quantity строкой/null, PATCH только изменённые поля, явную очистку; mounted/submission guards сохраняют новый выбор. BatchesPage:28–49 отменяет stale reads, :52–76 учитывает selection epoch; pagination25+lookahead, состояния loading/error/empty/retry. api/batches.ts использует относительные GET/POST/PATCH. Vite config:45–68 разделяет HTML navigation и JSON API, target loopback8000, /batches proxy добавлен. A2 inherited routed PASS и отдельно проверенные originals ниже. |

Это mapping approved поведения к коду и свидетельствам, а не новый аудит всего репозитория. Сервисы сохраняют принятую модель транзакций; read/no-op ветви могут не коммитить. Новых UoW, auth, search features, Document→Product/Batch linking либо архитектурного redesign не вводилось.

## Routed predecessors и разграничение доказательств

| TASK | Действующая приёмка и история |
| --- | --- |
| MVP00 | [Review](TASK-MVP-00.md), R1 OpenCode `task_67d2d98ace9c/ctx_b4d619f7a180`, PASS ee4e699. Baseline frontend/typecheck/build и 3377 tests — историческая точка, не текущий count. |
| MVP01 | [Review](TASK-MVP-01.md), R1 OpenCode `task_1d61cb577817/ctx_7ef3ef86a791`, PASS 5b9d916; 23 logging tests/3400 full тогда. |
| MVP02 | [C1 FAIL](TASK-MVP-02.md) с шестью MAJOR сохранён. [C2 PASS](TASK-MVP-02-C2.md), Codex `task_f5a7cda011c4/ctx_f8b4e389182a`, fde5406, MVP02-R2-001…006 closed; 386 focused/3483 full — inherited execution evidence. |
| MVP03 | [C1 FAIL](TASK-MVP-03.md) — два пробела обязательного доказательства, не установленная потеря данных. [C2 PASS](TASK-MVP-03-C2.md), Codex `task_b03f28ce101c/ctx_894373b5df1a`, 6827ed3; MVP03-R2-001/002 closed, 372 focused/3530 full/117 download — inherited, не повторённые здесь проверки. |
| MVP04 | [C1 BLOCKED](TASK-MVP-04-C1.md) не был PASS. Настоящее закрытие — [final evidence review](TASK-MVP-04-evidence-final.md), `task_f46401946eef/ctx_ab6321c6c683`, PASS AC001…010, MVP04-R2-001 closed. Исходные ALL7failed и G exit2 сохранены; final ALL3771/exit0 и поздний scoped/document cleanup закрывают соответствующие вопросы. |
| MVP05 | [A2/C1 PASS](TASK-MVP-05-A2-C1.md), независимый Sol/medium `task_36ad667176f9/ctx_90f25030eaee`, AC001…007/F01…04 closed. A1/C1 и C2 FAIL, затем C3 read-only RCA сохранены; это не третье A1 review. A2 evidence-only подход исправил доказательство на том же frontend product, принятом затем commit06f5806. |

MVP04 original reviewed manifest сейчас совпадает **16/17**: единственное отличие — docs/PROJECT_STATUS.md. Это проверенное изменение provenance: HISTORY.md:416–419 описывает пять post-PASS замен статуса и отдельный commit-manifest. **TASK-MVP-04-commit-SHA256.txt совпадает 17/17**, а Git diff 0db1f9e..HEAD для app/tests/alembic и PROJECT_STATUS пуст. Исторический manifest не исправлялся; продуктовая подача и тесты сохранились.

Для MVP05 самостоятельно просмотрены контракт Measurement (`variants/schemas.py:24`: finite, >0, scale≤2, max99999999.99), Batch schemas, A2 fixture serialization/validation и исходный api-log. В событиях **10→11→16→21→25** один ID29: POST201 variant7, quantity string12345.67, date2027-02-03; GET200 исходного состояния; PATCH200 только номера; PATCH200 только date:null; отдельный GET200 после clear сохраняет variant/number/quantity/unit. События3–5 — реальные сохранённые 422 для scale3/zero, не positive CRUD. Fixture:40 сериализует response_wire до отправки и отправляет те же bytes; :100/:116 валидирует настоящими BatchCreate/BatchUpdate до mutation. Старые created responses остаются с исходными номером/датой после последующих PATCH — alias defect A1 не используется как доказательство A2.

**Это изолированный MOCK, а не реальный browser→FastAPI→PostgreSQL round-trip.** Его применение прямо разрешено TASK-MVP-05.md:68–70. Browser interaction/reload/stale-response/screenshot acceptance наследуется из отдельного A2 review с указанными им C2 originals; stage reviewer браузер не запускал и не заявляет нового visual QA. Проверены hashes A2 artifacts и bounded final-detail snapshot. Реальный backend Batch persistence/API контракт подтверждён отдельной MVP04 приёмкой и новой интегрированной stage suite. Не заявляется выполненным единый browser-сценарий «партия связана с документом».

## Findings, ограничения и backlog

### MVP06-ST-001 — MINOR, документный drift; OPEN/backlog

- Критерий: ST-006, точность mapping/остаточных ограничений; функциональные frozen критерии удовлетворены.
- Locations: `ARCHITECTURE.md:48` (19 путей/34 операции), `:52` (список proxy без Batch), `ROADMAP.md:16` (смешанная формулировка «создать партию, приложить документ, привязать, проверить, открыть историю»).
- Observed: final API — 21/38, Vite содержит /batches; действующий frozen MVP05 AC006 — Batch list/detail/create/read/edit/clear/read. Document lifecycle существует отдельно; связь документа с Batch/Product остаётся прямо вне объёма VISION/ROADMAP/ADR010. Старые ADR counts/head являются датированными историческими снимками.
- Expected: итоговая поставка должна описываться актуальными числами и явно разделять Batch CRUD и существующий Document lifecycle; не выдавать narrative за реализованную связь или единый real-DB browser smoke.
- Repro/provenance: сопоставить эти строки с `tests/test_batches_openapi.py:21–22`, `frontend/vite.config.ts:66`, `docs/tasks/TASK-MVP-05.md:58,68–70`, A2 api-log и source mapping выше. Это file inspection + уже исполненные tests, без нового HTTP запроса.
- Disposition: не расширяет requirements и не вызывает FAIL/новый correction review. Координатор отражает фактическое ограничение в FINAL-REPORT; сами исходные документы этим reviewer не менялись.

Сохраняются принятые ограничения: локальный анонимный однопользовательский API, без публичного deployment/auth/ролей; без Document→Product/Batch linking, удаления документов/каскадной политики ProductVariant, pg_trgm/GIN, истории изменения variant links и pagination verification-history. Reconciliation только report-only, без автоматической очистки/расписания. DB+filesystem общей атомарности не имеют; orphan/unknown commit требуют журнала и последующего разбора, attach использует существующую сессию после rollback (принятое ADR009 отступление). Disk snapshot скачивания требует свободного места и полного чтения до ответа; Range/HEAD/ETag не введены. Отдельный крайний случай исключения source.close остаётся известным ограничением MVP03, не новым воспроизведённым дефектом. Долговременная эксплуатация, hardware failure, все возможные filesystem races и живые DB/storage после suite этим review не сертифицируются. Единственный warning зависимости сохранён без обновления dependencies.

## Расход, возобновление и передача

Requested/effective `gpt-6-astra/high` подтверждены stage-review-launch.json; native turn_context того же rollout подтверждает `gpt-6-astra`, effort `high`, CWD workspace, timestamp `2026-10-27T03:11:30.046Z`. Rollout: `C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T22-13-26-01a179a1-c25f-7212-b925-261aa8b0d7dc.jsonl`.

После provider-stop пользователь 27окт прямо разрешил «продолжи» после reset; продолжен **тот же** Task/Dispatch/rollout/call12. Переданные прежние **1,202,405 input** не обнулены. Наблюдаемый native cumulative snapshot `2026-10-27T03:12:38.416Z`: input **1,594,197**, cached input **1,361,152** уже включён в input, output **4,639**, total **1,598,836**. Это snapshot до окончания чтения/отчёта, **не финальная стоимость**. Координатор снимает settled total после worker_done; не прибавляет прежние1,202,405 второй раз к cumulative этой сессии. До call12 retained ledger **45,285,107 input/11calls**, включая stage executor **2,625,483**; все A1 failures и расходы сохраняются. Нового refusal после возобновления не наблюдалось; лимиты/аккаунт/тариф/сессия не сбрасывались и не менялись.

Записан только этот review report. No new workers/tasks, product fixes, test reruns, dependencies, migrations, commits, push, merge или deploy. Coordinator mailbox проверен при возобновлении и перед записью, сообщений не было; перед worker_done выполняется финальная проверка. Следующий владелец — координатор: принять реальный **stage PASS**, завершить ST-007/FINAL-REPORT, учёт и settlement в пределах прямого поручения пользователя.
