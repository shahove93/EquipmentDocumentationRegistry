# TASK-MVP-05 C2 — frozen correction / evidence checklist

R1,A1/C2. C1 FAIL и все7 frozen AC основного TASK сохраняются.
Baseline318e6336737ee635abf593c2643f26daba273f86,main/current;
Run run_68046cea3eb4. User exception MVP05_C2_EXTRA_1500000_20261026.
Читать только основной TASK по необходимости и C1 findings F-01..F-04
в docs/workflow/reviews/TASK-MVP-05-C1.md; не повторять design/историю.

## Замороженный scope

| Finding | Исправление / доказательство закрытия |
| --- | --- |
| F-01 | Сохранить фактические request И response bodies/status для полного browser list→detail→create→read→edit→clear→read. Create с ненулевой ISO-датой (в т.ч. future) и точной Decimal-строкой. Edit реально меняет реквизит отдельно от clear. Clear отправляет null; ПОСЛЕ clear явный detail GET подтверждает сохранение прочих полей. |
| F-02 | Guard позднего POST/PATCH completion после unmount/смены selection/form. Доказать delayed submit A→выбор B либо новая форма→late response A не меняет новый selection/form. Guard должен предотвращать obsolete onSaved; только abort GET недостаточен. |
| F-03 | Реальные browser URL и refresh артефакты, фактический HTML status/content-type через Vite. Ограниченные 404/422/network/error-retry и pagination/конец страницы доказательства. Mock явно маркирован, без DB/storage writes; новый backend/validation API не создаётся. |
| F-04 | В самом конце обновить отдельный C2 hash manifest всех изменённых product/fixture/evidence файлов; сначала закончить C2 report/logs, затем hash. Не включать manifest в самого себя; после hashing ничего хешированного не менять. C1 артефакты/FAIL не перезаписывать. |

Original AC001..007 carry-forward: навигация/proxy HTML/JSON; list/detail/
pagination/loading/empty/error/retry; create/patch/null/date/quantity;
safe errors/stale behavior; real browser+MOCK API evidence; typecheck/build/scope.
C2 не вводит новые требования. Нет Document→Batch/Product/auth/search/backend/
DB/migration/dependency изменений. Исходный TASK allowlist сохраняется.
Основные code targets BatchForm.tsx/BatchesPage.tsx; другие разрешённые файлы
менять лишь если необходимо для этих findings.

## Артефакты и проверки

Использовать существующую MOCK fixture и browser page
a5a98608-453d-4c3c-b8be-5effd41ecae6 через настоящий Orca browser CLI.
Если эта page недоступна, её точная ошибка — вопрос координатору в этом Dispatch,
не новая сессия/worker. Все новые C2 logs/snapshots/screenshots/script/report:
docs/workflow/evidence/TASK-MVP-05-C2-*; existing fixture.py допустимо исправить
для bodies/delay/error/pagination fixtures, сохранив C1 оригинал отдельной C2 copy
перед изменением; backend приложение и реальная DB не меняются.
Браузерные actions должны быть реальными, records не выводить из ожидаемого кода.

После конечного исправления один relevant targeted browser smoke и:
wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'
wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'
Точные command/CWD/exit/output сохранить компактно. Не повторять успешные
проверки без новых изменений/неясностей; не запускать backend pytest.
C2 report TASK-MVP-05-C2-evidence.md: F01..F04 closures/AC mapping, actual IDs,
snapshot/hash identity, limitations и НЕ project PASS.
Git scope/diff-check evidence подтверждает неизменные app/alembic/tests/deps.

## Бюджет и границы

C1 actual9210419 сохранён; totalceiling10710419. Calls2 consumed,
implementation call3/4 gpt-6-luna/medium max900000 input INCLUDING finalization,
checkpoint600000: ОСТАНОВИТЬ новые edits/checks и спросить координатора с actual
usage/remaining/status. Не продолжать молча после checkpoint.
Для безопасности закончить substantive work до750000, оставить финализацию;
не приближаться к900000. Cached input считается. Собственные actual counters
читать native через D:/AI/NemotronBoltE4B/Get-CodexUsage.py --rollout <own exact path>.
Координатор также следит за actual metadata; минимум чтений/вывода/пересказов.
Отдельный Sol reviewer call4/4 max450000 + safety150000 не принадлежат writer.
Один writer; не запускать reviewer/другие workers. На provider exhaustion STOP.
Никакого commit/push/merge/deploy до routed C2 PASS. На C2 FAIL stop; два full
reviews на A1 максимум. Workflow документы пишет координатор, код — worker.

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
