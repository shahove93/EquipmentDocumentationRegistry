# TASK-MVP-05 A1/C1 — независимое R1 review

Вердикт: FAIL. Первый full-review slot 1/2, Codex call 2/2; это не приёмка этапа. Проверены frozen AC-001..007 без запуска тестов, UI или API. Исправления и продолжение не разрешены.

## Идентичность и границы

Reviewer: task_0e67a288d075 / ctx_41b021641e99 / term_d9c62fe8-a19a-4d31-9524-69451d7f0837; Run run_68046cea3eb4. Реальный native turn_context: gpt-6.1-sol, medium. Реализация: task_1f8ceba36e9e / ctx_e9800c446d2d, отдельный исполнитель. Workspace D:/Antigravity/EquipmentDocumentationRegistry, main; HEAD и baseline 318e6336737ee635abf593c2643f26daba273f86, submission uncommitted.

Полностью прочитан tracked frontend diff относительно baseline и все три новых файла batches.ts, BatchForm.tsx, BatchesPage.tsx. Все восемь продуктовых файлов совпадают с SHA256 в TASK-MVP-05-hashes.json. Manifest SHA256 D2964EAB25E1135C3288010D906570519BD167E1451B9B743444E81A8303BDF6. Изменения продукта находятся в allowlist; остальные tracked изменения ROADMAP.md и workflow APPROVALS/HISTORY/STATE — отдельно разрешённая работа координатора. Backend, tests, migrations, package manifests/dependencies отсутствуют в списке tracked изменений; это проверка Git, не аудит живой БД. Новых посторонних продуктовых файлов в git status нет.

Артефакты api-log, browser.png, fixture.py, typecheck.log, build.log совпадают с manifest. C1.md НЕ совпадает: expected 72C684D6DEE0CD65FD772CDD1C2ADEF9D8CEDD9B7C6F34748470175B16212B04, current 878227BFA2962612AFA8B1007F771FCAC8E65C260DF0409E8F9E9483C3D036AB. Это не расхождение продуктового кода, но prose evidence не имеет заявленной идентичности.

## Frozen AC

| AC | Результат | Основание |
| --- | --- | --- |
| AC-001 | Частично / FAIL evidence | App/Nav добавляют /batches; Vite GET HTML bypass и JSON proxy корректны при /batches. Screenshot показывает экран и навигацию. C1.md:16 утверждает URL/refresh/HTML200 text/html, но underlying HTTP/browser snapshot с заголовками отсутствует: журнал содержит только fixture API. F-03. |
| AC-002 | Частично | Код показывает шесть полей, null как тире, date через formatDate, loading/error/retry/empty; 26-row lookahead при pageSize25 и offset25 корректен, Prev возвращает с пустой страницы. GET id и безопасный 404 обработаны. Журнал подтверждает только offset0/status200, screenshot одну запись; нет response bodies, 404/error/retry или непустой следующей страницы. F-01/F-03. |
| AC-003 | Частично / FAIL evidence | POST payload variant7, quantity строка 99.25, nullable date, status201, затем GET1/200. Форма требует positive integer variant, блокирует submit pending, ошибки не вызывают onSaved. Нет сохранённого POST/GET response body, ненулевой даты и invalid/422 проверки. F-01. |
| AC-004 | Частично / FAIL evidence | PATCH отправляет только изменённые поля, очистку null; variant required; нет Batch PUT/DELETE/uniqueness/409 запрета. Журнал PATCH1 quantity/unit null,200, затем только list GET. Screenshot согласуется с очищенными полями. Отдельного edit изменения и последующего detail GET после clear нет. F-01/F-02. |
| AC-005 | Частично / FAIL | Quantity нигде не преобразуется в float; quantity/unit независимы; date input без запрета будущей даты. List/detail/picker reads имеют AbortController и проверяют aborted. describeError безопасно отображает 404/422/network без raw detail. Pending mutation после unmount всё ещё вызывает onSaved и меняет новый выбор; edge-case UI/API записей нет. F-02/F-03. |
| AC-006 | Частично / FAIL | Реальный screenshot, native buttons/select/label, отсутствие Document→Batch/Product действий подтверждены. Mock разрешён и явно обозначен; fixture хранит данные только в памяти. Журнал начинается пустым list, затем create→read, а edit представлен единственным clear; полного list→detail→create→read→edit→clear→read с response bodies нет. F-01. |
| AC-007 | PASS для code/build, MINOR integrity | Оба WSL npm лога содержат Node24.22.0, CWD, точную npm команду, stdout, EXIT_CODE0; hashes продукта совпадают. Scope соблюдён. git diff --check exit0 сохранён в C1.md:36, повтор не выполнялся. Prose hash mismatch — F-04. |

## Findings

### F-01 — MAJOR — AC-003/004/006: обязательный round-trip не доказан

Место: docs/workflow/evidence/TASK-MVP-05-api-log.json, весь массив value; TASK-MVP-05-C1.md:18–24; TASK-MVP-05-fixture.py:reply.
Наблюдение: 14 записей содержат method/path/status и лишь POST/PATCH request payload. Ни одной response body; fixture reply сохраняет только status. Единственный POST имеет manufacture_date:null; единственный PATCH одновременно очищает quantity/unit. Последняя запись — GET /batches?limit=26&offset=0; после PATCH нет GET /batches/1. До POST нет GET detail существующей партии. Screenshot доказывает лишь конечное состояние одной записи, не промежуточные round-trip результаты.
Ожидание: frozen фактические request/response/GET доказательства create с Decimal/date, edit и clear, полный UI/API сценарий. Метод просмотра: полностью прочитаны журнал, fixture, C1.md и screenshot; исполнение не повторялось. Для закрытия нужны реальные недостающие артефакты в отдельно разрешённой работе, без приписывания fixture-коду статуса выполненной проверки.

### F-02 — MAJOR — AC-005 (также AC-004): завершение старого submit перетирает новый выбор

Место: frontend/src/components/BatchForm.tsx:38–51; frontend/src/pages/BatchesPage.tsx:51–63,70–72,79,90–91.
Наблюдение по коду: POST/PATCH не получает AbortSignal, submit не имеет mounted/generation guard; onSaved вызывается безусловно. На странице кнопка «Новая партия» и выбор строк остаются активны при pending формы. Статическая последовательность: открыть edit A, отправить PATCH с задержкой, выбрать B (choose снимает editing, форма A unmount, начинается GET B), затем получить PATCH A. Старый onSaved вызывает saved(A), устанавливает selected/requestedId A, отменяет/заменяет новый GET B и закрывает форму. Аналогично старый submit может закрыть новую create-форму. Это логически следует из callbacks, динамически не воспроизводилось ввиду запрета новых проверок.
Ожидание: obsolete/unmounted запрос не меняет новый выбор; наличие abort для GET не защищает этот callback. Доказательство закрытия должно покрывать запоздалое завершение submit после смены выбора/формы в отдельно разрешённой работе.

### F-03 — MAJOR — AC-001/002/003/005: обязательные наблюдаемые проверки отсутствуют

Место: docs/workflow/evidence/TASK-MVP-05-C1.md:16–22; TASK-MVP-05-api-log.json; TASK-MVP-05-browser.png.
Наблюдение: screenshot без адресной строки показывает только конечный экран. HTML200/text/html и refresh существуют лишь как утверждение C1.md, без underlying HTTP headers/body или browser snapshot. API журнал имеет только успешные200/201 и offset0, date:null; нет ограниченных edge-case записей 404/422/network/invalid/pagination. Fixture не валидирует POST и не моделирует422. Код подтверждает часть поведения, но не заменяет явно требуемые реальные артефакты. Нельзя принять утверждение успеха как выполненную проверку.
Ожидание: указанные frozen browser/HTTP и ограниченные edge-case артефакты; никаких новых backend тестов. Повторы запрещены последним поручением, поэтому пробелы сохранены как FAIL, а не заполнены предположениями.

### F-04 — MINOR — AC-007/evidence integrity

Место: docs/workflow/evidence/TASK-MVP-05-hashes.json, entry TASK-MVP-05-C1.md.
Наблюдение: SHA256 prose evidence отличается от manifest, exact значения выше; продукт и underlying артефакты совпадают. Ожидание: manifest идентифицирует фактически представленный evidence pack. Не блокирует самостоятельно продуктовую приёмку; отчёт и manifest reviewer не исправлял.

## Provenance, reuse, ограничения и расход

Прочитаны полные SMALL api-log.json, typecheck.log, build.log, hashes.json, fixture.py, C1.md; browser.png просмотрен как изображение. Existing client.ts, references.ts, Pagination.tsx, formatDate прочитаны только для интерпретации reused behavior. Никаких новых tests/typecheck/build/UI/API/DB проверок не запускалось. Read-only действия reviewer: git rev-parse/status/diff/name-only, SHA256 manifest comparison, чтение файлов/картинки, собственных native metadata и mailbox. По frozen reuse правилам использованы npm run typecheck / npm run build из /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend через WSL Ubuntu; оба exit0. Логи содержат команды npm и runtime/CWD, полные внешние WSL invocation зафиксированы frozen TASK. Исторические backend3771 не запускались и не являются доказательством нового UI. Реальный DB round-trip не заявляется; mock допустим, но не отменяет frozen требования к содержимому evidence. README/status опциональны и не использованы как дополнительные критерии.

Авторитетный собственный rollout: C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T16-37-59-01a1786e-a5c1-7ca3-bf08-1e5c54e987fb.jsonl. Без prompts/secrets прочитаны только поля turn_context model/effort и token_count. Доступный snapshot 2026-10-26T13:39:19.306Z: input187134, включая cached146176 (не суммировать повторно), output1088, reasoning39, total188222; это НЕ settled usage и не включает последующую финализацию. Provider primary54%, window300min, resets_at1793032523; secondary24%, window10080min, resets_at1793600447; exhaustion не наблюдалось. Final settled usage записывает координатор после worker_done; дополнительные quota polls не делались. Parent actual8812350 сохранён, ceiling9300000; reserve reviewer250000, parent safety237650 не предоставлен reviewer. Содержательная инспекция завершена; финализация выполняется немедленно без дополнительного чтения. Никаких reset/new session/new worker или correction calls нет.

FAIL основан на frozen критериях и actual code/evidence, а не на историческом input overrun исполнителя. Ни один продуктовый файл не изменён; записан только этот report. После передачи verdict вся работа останавливается; corrections/review/новые проверки требуют отдельного решения и бюджета. Lifecycle succeeded означает завершённый bounded review, не продуктовый PASS.