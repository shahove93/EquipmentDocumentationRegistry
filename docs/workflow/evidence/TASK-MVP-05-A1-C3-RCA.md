# TASK-MVP-05 A1/C3 — read-only RCA, 2026-10-26

Authority: пользователь «Ну делай что нужно)» явно разрешил C3 и A2/C1. Run run_68046cea3eb4; main HEAD318e6336737ee635abf593c2643f26daba273f86. Исторические A1 FAIL/FAIL, full-review2/2, actual28965861 input/calls8 сохранены.

C3 координатором выполнен только чтением source/review/JSON и Git/Orca state. Код, fixture, тесты/API/browser не запускались/не менялись; это не третье acceptance review.

## Подтверждённые причины F01
- app/api/batches/schemas.py импортирует Measurement как Quantity. app/api/variants/schemas.py: конечное Decimal>0, <=99999999.99, exponent>=-2; null разрешён. Fixture-8001 POST проверяет лишь variant_id, PATCH Quantity не проверяет. Поэтому mock201 не подтверждает API-контракт.
- Actual94-record browser-api-log-complete: ordinal63 POST32 quantity12345678901234567890.001, date2027-02-03, mock201. Ранняя полная ID29 цепочка quantity1234567890.123456 также недопустима. API-valid POST30/31/33 не имеют полной edit/clear цепочки; actual PATCH paths29/1/2/32.
- Fixture reply сериализует wire body, но recorder response_body=data сохраняет ссылку. PATCH row.update меняет объект. Ordinal63/64 response уже содержит edited номер/date:null, хотя create request содержит исходные номер/дату. Это не исторические ответы на соответствующие запросы.
- C2 расширил evidence, но оставил permissive mock и mutable recorder: проверял transport stress вместо coherent positive contract sequence. Hashes подтверждают идентичность файлов, не достоверность исторического тела. Guard/provider interruptions сохранены отдельно и не объясняют дефект завершённой подачи.
F02/F03/F04 закрыты независимым Sol; final typecheck/build0 и139 hashes подтверждены. C3 не устанавливает новый продуктовый дефект.

## Materially distinct A2
Заменить способ доказательства: contract-enforcing isolated mock + immutable serialized wire snapshots, отделённые от mutable store + единый связанный browser CRUD trace с проверкой всей последовательности и неизменности начального snapshot после поздних PATCH. Это замена permissive observational harness на contract/temporal oracle, не переименование/свежая сессия/одна замена параметра.
Предпочтителен reuse фактических BatchCreate/BatchUpdate validators в WSL fixture без DB access; иначе точное ограниченное воспроизведение с source provenance. Backend/API/DB/deps не меняются.
Альтернативы: только заменить quantity не решает alias recorder; реальная DB нарушает scope. Выбран isolated contract/wire oracle, устраняющий обе причины.
План и frozen carry-forward docs/tasks/TASK-MVP-05-A2-C1.md. A2 отдельный подход с собственными slots, но разрешён только C1 implementation+review1/2; FAIL=>stop без автоматического C2/A3. Старый расход не обнуляется.
