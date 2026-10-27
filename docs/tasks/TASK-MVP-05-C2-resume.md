# TASK-MVP-05 C2 resume — frozen addendum

Authority MVP05_C2_RESUME_CALL4_11535749_20261026, exact new user «Разрешаю».
Тот же logical TASK-MVP-05,R1,A1/C2 и Run run_68046cea3eb4,main/current,
baseline318e6336737ee635abf593c2643f26daba273f86.

## Неизменный scope

Code scope/checklist EXACTLY TASK-MVP-05-C2.md: F01..F04 и исходные AC001..007
carry-forward. Не менять требования и не начинать design заново.
Prior C1 и stopped call3 partialcode/evidence UNCOMMITTED уже в workspace:
BatchForm.tsx/BatchesPage.tsx и TASK-MVP-05-C2-* artifacts. Просмотреть только
необходимые остатки этой незавершённой работы и завершить их. Не считать
partial code/logs подтверждёнными checks/completion. C1 FAIL/логи не переписывать.

## Расход / маршрут

C1actual9210419; call3actual825330 STOPPED, без worker_done.
Current actual10035749, новая общая cap11535749, remaining1500000:
- writer Luna medium continuation call4/5 max900000 INCLUDING tests/evidence/
  report/mail/final response; checkpoint600000 BLOCKING ASK координатору.
- substantive edits/checks прекратить ДО750000, финализировать ДО900000;
- final independent Sol medium call5/5 max450000, second/final full-review2/2;
- safety150000 остаётся отдельно, writer им не пользуется.

Stopped call3 остаётся consumed. Никаких refunds/resets/скрытых calls.
Старый TASK-MVP-05-C2-budget-guard.py сохранить, НЕ запускать/не изменять.
Новый observer только читает metadata/пишет alerts на600k, НЕ вызывает
worker-stop/kill/close/reset. Coordinator вручную разбирает checkpoint.
При600k writer прекращает новые actions и делает blocking ask, сообщает
actual/progress/pending. Не расходовать ещё300k молча. Проверять budget по
собственному native rollout с cached input included; без repeated broad reads.
Оставить достаточно budget для report/hash/mail/worker_done.

## Completion

Один writer. Только relevant targeted browser smoke + WSL frontend
typecheck/build по C2, без backend/API/DB/deps изменений. Использовать existing
mock/browser fixture; старые evidence не уничтожать, C2 hashes в самом конце.
Scope/budget failure => stop, не reviewer/новый worker.
После actual worker_done coordinator settles actualusage, только затем
отдельный final Sol review по тем же criteria и full C1 carry-forward.
При C2 FAIL stop, третьего full-review нет.
Coordinator не меняет productcode; commit только после routed C2 PASS;
push/merge/deploy не разрешены. Это не stage acceptance.

## Call4 continuation stopped — current BLOCKED

Call4 Luna ctx_5be9101c483f manually stopped after actual923618 exceeded own900000;
no worker_done/evidence completion, no C2 review/acceptance.
Cumulative10959367/11535749,remaining576382,calls4/5 consumed.
Sol450000+safety150000 remain unspent but cannot both fit: shortfall23618.
Observer was read-only/alert-only, oldguard notrun; manual coordinator reaction
to600k checkpoint was late. No new code/retry/reviewer/commit/push permitted
by current budgetfailure stop condition. All prior scope/criteria/history intact.
