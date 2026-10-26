# TASK-MVP-04 — A1/C1, фактическая реализация

Дата: 2026-10-26. Исполнитель: отдельный Codex worker; проектный PASS не присваивается.
Итог dispatch: **BLOCKED**, requested work not complete (AC-010 / ALL exit 1).
Нужен явный scope decision на семь старых OpenAPI-counter файлов; до него
изменения не разрешены. Routed R2 review ещё не запускался.
Run `run_68046cea3eb4`, Task `task_efc8f84abfbc`, Dispatch `ctx_25189cfb43ce`.
Worker `term_c7507fad-6b56-46c9-86be-45f8398bc281`;
координатор `term_d727cc23-31e8-42eb-a295-c42268e0c645`.

## Состояние и полномочия

- Windows CWD всех команд: `D:\Antigravity\EquipmentDocumentationRegistry`.
- CWD внутри WSL Ubuntu: `/mnt/d/Antigravity/EquipmentDocumentationRegistry`.
- Ветка `main`, HEAD/baseline `a405968401eefe6bcbbc2ca3302d14072eb63509`.
- Новый commit **не создан**: актуальное исключение CODEX_COORD_20261026 и
  follow-up `msg_90f9825708ad` отменяют старое требование commit до review.
  Ответ на blocking ask также подтвердил оставить diff для независимого R2;
  координатор коммитит только после routed PASS.
- Сохранены ранее существовавшие изменения: см.
  `CODEX-COORD-20261026-baseline-status.txt`. Workflow, AGENTS, ROADMAP и ADR
  исполнитель не редактировал. C1 и логи не коммитить.

## Что реализовано

- `BatchCreate/Update/Read`: exact fields, extra forbidden, explicit-null FK
  rejected, nullable PATCH, trim/length, date coercions. Quantity переиспользует
  публичный `Measurement` как `Quantity`; Read не повторяет write-валидацию.
- `BatchService`: create/get/list/update; SQL ordering/pagination, один commit
  на запись, rollback всех SQLAlchemyError; доменная классификация только
  SQLSTATE 23503 + constraint `batches_variant_id_fkey` + table `batches`.
- Тонкий router: POST 201+абсолютный Location, GET id/list, PATCH; ошибки
  404/422/405/безопасный 500. Новых DELETE/PUT/409 нет.
- Четыре новых тестовых модуля: схемы, real PostgreSQL service, HTTP, OpenAPI.
  `test_batch.py` и `conftest.py` не изменены. SQL-проверки идут последовательно
  через существующую временную схему, без SQLite/xdist. HTTP fixture сохраняет
  чужие overrides, восстанавливает get_db и временно подменяет lifespan settings;
  логи/storage новых HTTP тестов направлены в tmp_path.
- `PROJECT_STATUS.md`: Batch больше не ORM-only; перечислены четыре операции,
  ограничения и ожидаемая независимая R2 приёмка; 38 операций / 21 путь.

## Команды и результаты

Общий префикс каждого pytest: `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q`;
ниже приведены полные команды, CWD указан выше. Успешные S/V/H/O представлены
достаточным inline output; F/ALL сохранены полностью.

| ID | Полная команда | Exit | Фактический итог |
| --- | --- | --- | --- |
| S | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch_schemas.py'` | 0 | `114 passed in 1.04s`; 0 warnings |
| V | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch_service.py tests/test_batch.py'` | 0 | `55 passed in 6.38s`; 0 warnings |
| H | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batches_api.py'` | 0 | `88 passed, 1 warning in 17.61s` |
| O | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batches_openapi.py'` | 0 | `10 passed in 3.16s`; 0 warnings |
| F | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q tests/test_batch.py tests/test_batch_schemas.py tests/test_batch_service.py tests/test_batches_api.py tests/test_batches_openapi.py tests/test_issuer_schemas.py tests/test_issuer_service.py tests/test_issuers_api.py tests/test_variant_schemas.py tests/test_variant_service.py tests/test_variants_api.py'` | 0 | `1094 passed, 1 warning in 109.98s (0:01:49)`; `TASK-MVP-04-F.txt` |
| ALL | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | 1 | `7 failed, 3764 passed, 1 warning in 463.24s (0:07:43)`; фактически 3771 тест; `TASK-MVP-04-ALL.txt` |

Предупреждение H/F — `StarletteDeprecationWarning` об использовании httpx
в starlette.testclient; зависимости не менялись.

Сохранённые начальные ошибки тестов (не независимые review и не проектный FAIL):

1. Первый V: exit 1, `1 failed, 54 passed in 8.64s`.
   CHECK diagnostic probe создавал TEMP TABLE и коммитил; NullPool закрывал
   соединение, следующий INSERT получал UndefinedTable. Убран лишний commit:
   TEMP TABLE и нарушающий INSERT выполняются на одном соединении, rollback
   убирает только временный probe; модель/миграции не изменены. Повторный V выше.
2. Первый O: exit 1, `1 error in 5.73s`, collection rejected reserved pytest
   parameter name `request`. Переименован в `request_schema`; повторный O выше.

F и ALL выполнены по одному разу на окончательном коде/тестах.
S/V/H/O не повторялись после успеха; последующие изменения касаются только статуса
и evidence, результатов тестов они не меняют.

## Миграции и Git

`wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic heads'`
— exit 0, `e4b8c2d16a70 (head)`.
`wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py | wc -l'`
— exit 0, `13`. Эти две read-only команды выполнены повторно по одному разу:
первый общий shell-вызов сохранил только aggregate exit, повтор дал индивидуальные
exit для каждой команды. Окончательные G записаны отдельно ниже.
Первичный общий `git diff --check` обнаружил пустые строки в чужих workflow
HISTORY/STATE; разрешённый tracked diff проходит scoped `git diff --check`.

## Метаданные фактического worker

Launch requested/effective: `codex`, `gpt-6.1-sol`, `medium` —
`TASK-MVP-04-implementation-launch-2.json` и `TASK-MVP-04-implementation-start-metadata.json`.
Фактический provider rollout:
`C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T12-38-57-01a17793-cd60-7952-8a32-c03fdf7f7fcd.jsonl`.
Session metadata 09:39:11.190Z: provider `openai`, CLI `0.164.0`, session
`01a17793-cd60-7952-8a32-c03fdf7f7fcd`, CWD совпадает.
Turn context 09:39:12.126Z: model `gpt-6.1-sol`, effort `medium`.
Token snapshot 09:51:02.115Z: input 2,898,835; cached input 2,801,280;
output 20,139 (reasoning 1,233); total 2,918,974.
Это snapshot cumulative token_usage данной сессии до окончания работы, не финальная
стоимость. Rate limit snapshot: primary 83% used / 300 min, secondary 13% / 10080 min;
reset primary unix 1793013647. Расход общего окна не приписан этому TASK;
фактического отказа провайдера не наблюдалось. Reset/account/plan/model changes не выполнялись.

## Ограничения

Нет новых моделей, индексов, CHECK или миграций продукта; CHECK diagnostic probe
существует только во временном PostgreSQL connection-local объекте теста.
Нет frontend/Vite proxy, uniqueness/409, удаления, фильтров, bulk/import/export,
конверсии единиц или API привязки документов к партии. Прямой SQL обходит write
валидацию; JSON number может потерять лексическую точность (для quantity — строка).
PATCH без optimistic locking, offset pagination без snapshot, сервис требует
чистую Session. Push/merge/deploy/следующий TASK не выполнялись.

Остаётся независимое R2 review AC-001…AC-010; только ревьюер определяет приёмку.

## Блокировка по итогам ALL

AC-010 пока не выполнен: семь существующих тестов глобального OpenAPI-счётчика
ожидают старые totals 19/34, тогда как обязательные новые операции дают 21/38.
Все семь файлов вне frozen allowlist; обхода/ослабления assertions не было:

- `tests/test_document_variants_api.py:698`
- `tests/test_documents_integration_api.py:520`
- `tests/test_documents_search_api.py:527`
- `tests/test_files_api.py:498`
- `tests/test_files_delete_api.py:691`
- `tests/test_files_download_api.py:2244`
- `tests/test_files_upload_api.py:923`

Blocking ask передал точные failures координатору. Ответ: пользовательское решение
на точное расширение allowlist ещё ожидается; до явного follow-up эти файлы не
редактировать и тесты не перезапускать. Разрешено сохранить фактический evidence/G
и status. Последующий `msg_51c5024429e2` предписал завершить этот dispatch
с `worker_done --outcome failed`, поскольку решение пользователя ещё ожидается.
Новый commit отсутствует,
новый TASK/design/review не запускался; бюджет не сбрасывался.

## G snapshot после ALL

Полный stdout/stderr и индивидуальные exit: `TASK-MVP-04-G.txt`.
Все G-команды из TASK выполнены в указанном Windows CWD, каждая exit 0:
`git status --short`, `git diff --check`,
`git diff --name-only a405968401eefe6bcbbc2ca3302d14072eb63509`,
`git ls-files --others --exclude-standard`, `git diff -- docs/PROJECT_STATUS.md`,
`git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- app/models alembic`.
Последняя команда дала пустой вывод. Дополнительно unchanged доказаны
`git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- tests/test_batch.py tests/conftest.py`
(exit 0, пустой вывод). Scoped diff-check тоже exit 0, пустой вывод.
Первый общий diff-check до очистки координатора отмечал EOF blank lines
HISTORY/STATE; после сообщения `msg_1b90bdf6aa47` окончательный общий check
exit 0 (остались только информационные CRLF→LF warnings чужих файлов).

Собственные изменения: два tracked файла (`app/api/router.py`,
`docs/PROJECT_STATUS.md`), восемь новых product/test файлов из allowlist,
C1 и raw evidence logs. Остальные изменения принадлежат координатору;
baseline snapshot и его последующие live follow-up сохранены, эти файлы
исполнитель не правил. Raw logs дополнительно разрешены `msg_90f9825708ad`.
SHA-256 десяти собственных product/test/status файлов:
`TASK-MVP-04-SHA256.txt` (hash snapshot command exit 0).
`app/api/batches/__init__.py` — 0 bytes, SHA256 пустого файла.
Новых коммитов нет: `git rev-parse HEAD` exit 0,
`a405968401eefe6bcbbc2ca3302d14072eb63509`.

## Продолжение A1/C1 после явных решений пользователя (2026-10-26)

Этот раздел — актуальный итог; предыдущие BLOCKED, ошибки и расходы выше
сохранены как история. Run `run_68046cea3eb4`, Task `task_efc8f84abfbc`,
Dispatch `ctx_7ff92b6ea59a`, worker `term_5f031575-a841-4358-823e-e79c8304c53c`.
Координатор тот же `term_d727cc23-31e8-42eb-a295-c42268e0c645`.

Основание: MVP04_OPENAPI_COUNTERS_20261026 и `msg_74e85e545068` разрешили
только семь глобальных totals19→21/34→38 и два соответствующих имени теста.
Изменены только эти assertions/names в test_document_variants_api.py,
test_documents_integration_api.py, test_documents_search_api.py, test_files_api.py,
test_files_delete_api.py, test_files_download_api.py, test_files_upload_api.py.
Diff: 7 файлов, 14 insertions / 14 deletions; остальные assertions неизменны.
Продуктовый код и четыре новых Batch-тестовых модуля не изменялись.

ALL запущен ровно один раз на исправленном конечном состоянии:
`wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'`.
Windows CWD `D:\Antigravity\EquipmentDocumentationRegistry`, WSL CWD
`/mnt/d/Antigravity/EquipmentDocumentationRegistry`.
Exit **0**, `3771 passed, 1 warning in 447.49s (0:07:27)`; 3771 тест,
0 failed. Полный лог `TASK-MVP-04-ALL-final.txt`, включая `ExitCode: 0`.
Это тот же уже завершённый процесс, его exit дополнительно получен при
получении оставшегося stdout из exec session; повторных запусков не было.
Warning — прежний StarletteDeprecationWarning про httpx, зависимости не менялись.
Исходный `TASK-MVP-04-ALL.txt` (7 failed/3764 passed) сохранён без изменения.
S114/V55/H88/O10/F1094 переиспользованы по разрешению: код этих групп неизменен.
Alembic head/13 ревизий переиспользованы: модели и миграции не изменялись.
PROJECT_STATUS отражает 3771 passed/1 warning, F1094 и ожидаемую R2 приёмку.

Бюджетная остановка: `msg_222d7a8e4bf8` сообщил фактический input предыдущей
реализации 7686005, превышающий прежний cap3M. Новые работы остановлены,
координатору задан blocking ask; уже запущенный ALL сохранён, не отменялся.
Возобновление той же сессии/Dispatch разрешено прямой инструкцией пользователя
после prior usage-limit/reset и подтверждено `msg_5607e063d169`:
cap12M, 7686005 плюс весь остальной расход сохранены, максимум4 calls,
без нового Run/Task/session, без тестовых повторов, только evidence/status/G.
Самостоятельных reset/account/plan/model changes не выполнялось.

Метаданные continuation: launch requested/effective `gpt-6.1-sol / medium`
в `TASK-MVP-04-continuation-launch.json`; фактический provider `openai`,
CLI `0.164.0`, session `01a177ac-775e-7e20-ba3f-321aee6fd0bd`, cwd совпадает.
Rollout `C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T13-05-53-01a177ac-775e-7e20-ba3f-321aee6fd0bd.jsonl`.
Session metadata 10:06:05.831Z и turn_context подтверждают model/effort.
Наблюдаемый cumulative token snapshot 11:54:27.660Z: input1081830,
cached_input994176 (уже входит в input), output2726, reasoning218,
total1084556. Это snapshot данной сессии до окончания, не финальная сумма
TASK и не возврат предыдущего расхода. Provider primary3%, secondary16%.

Итоговые G: `TASK-MVP-04-G-final.txt`, Windows CWD как выше.
`git status --short`, `git diff --name-only a405968401eefe6bcbbc2ca3302d14072eb63509`,
`git ls-files --others --exclude-standard`, `git diff -- docs/PROJECT_STATUS.md`,
`git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- app/models alembic`,
`git diff a405968401eefe6bcbbc2ca3302d14072eb63509 -- tests/test_batch.py tests/conftest.py`,
`git rev-parse HEAD` — каждая exit0; последние два содержательных diff пустые.
`git diff --check` — **exit2**, единственная ошибка:
`docs/workflow/HISTORY.md:345: new blank line at EOF` (файл координатора,
исполнителем не изменялся). Scoped `git diff --check -- app/api/router.py docs/PROJECT_STATUS.md tests/test_document_variants_api.py tests/test_documents_integration_api.py tests/test_documents_search_api.py tests/test_files_api.py tests/test_files_delete_api.py tests/test_files_download_api.py tests/test_files_upload_api.py`
— exit0, пустой вывод. Чужая EOF-ошибка не исправлялась вне allowlist.
SHA256-final.txt содержит актуальные hashes17 product/test/status файлов;
предыдущие SHA256/G не перезаписаны. Собственные изменения за continuation:
семь счётчиковых тестов, PROJECT_STATUS, C1 и разрешённые raw evidence logs.

Нового commit нет: HEAD `a405968401eefe6bcbbc2ca3302d14072eb63509`.
Координатор коммитит только после независимого routed R2 PASS.
Ограничения продукта выше сохраняются; push/merge/deploy/новые workers/следующий
TASK не выполнялись. Реализация и финальный ALL готовы к независимому R2 review;
проектный PASS исполнитель не присваивает. Осталось R2 review и принадлежащая
координатору EOF-ошибка workflow HISTORY в общем G.
