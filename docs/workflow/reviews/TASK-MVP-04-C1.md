# TASK-MVP-04 A1/C1 — независимое R2 review

Вердикт: **BLOCKED / NOT_ACCEPTED — ограничение бюджета ревью**.
Дата: 2026-10-26. Первый полный review slot 1/2, последний вызов 4/4.
Ревьюер не реализовывал продукт и не вносил исправлений. Полная приёмка не завершена; PASS/FAIL по продукту не присвоен. BLOCKER/MAJOR дефектов в просмотренном коде не обнаружено; это не заменяет завершённую проверку доказательств.

Run `run_68046cea3eb4`; child Task `task_e54c9b327d43`; Dispatch `ctx_666d79cff077`; reviewer `term_1cda0a5c-f4e1-4d86-b844-df01891ca05b`; coordinator `term_d727cc23-31e8-42eb-a295-c42268e0c645`.
Основание: прямое разрешение «Разрешаю только Astra review call4», CODEX_COORD_20261026 и MVP04_OPENAPI_COUNTERS_20261026. WF-01 не проверялся и не исправлялся; его BLOCKED не изменён. Прочитаны autonomous-development, review-policy, routing-and-budget и установленная справка Orca orchestration.

## Идентичность состояния

Рабочий каталог `D:/Antigravity/EquipmentDocumentationRegistry`, main. Фактический HEAD и baseline: `a405968401eefe6bcbbc2ca3302d14072eb63509`; итоговый продуктовый diff не закоммичен.
Текущий TASK SHA-256: `3008C6B479AC37254A31B2040711A63747DA6FEC56CE5DD6559A832B3D69DA2F`. Исторический frozen-task-hash содержит другой hash; текущий TASK включает последующие разрешённые поправки. Ревью использовало заданные пользователем актуальные AC-001…010 и точечную поправку allowlist.
Идентификатор итогового набора файлов: [SHA256-final](../evidence/TASK-MVP-04-SHA256-final.txt), SHA-256 самого манифеста `DEEBF64C47910D6427BC10E1C2B8FBB383D7DE34964E4FB252901ACD7B6670AF`.
Ревьюер вычислил SHA-256 всех 17 перечисленных файлов: **17/17 совпали**, включая пустой `app/api/batches/__init__.py`.

Полностью просмотрены все восемь новых файлов: schemas/router/__init__, batch_service и четыре тестовых модуля. Просмотрен tracked diff app/api/router.py, docs/PROJECT_STATUS.md и семи старых тестов. Router меняется только импортом/include; в семи тестах изменены только разрешённые totals 19→21 / 34→38 и два числовых имени. Статусные изменения описывают Batch, ограничения и ожидаемую приёмку. Посторонние workflow/AGENTS/ROADMAP/ADR изменения отделены по [baseline-status](../evidence/CODEX-COORD-20261026-baseline-status.txt) и инструкции dispatch. Продуктовый код ревьюером не менялся.

## Карта AC и просмотренных доказательств

Общее состояние всех AC — **не принято**, поскольку полный проход доказательств остановлен. Ниже указаны результаты статического сопоставления и источники выполненных исполнителем проверок; статическое соответствие не выдаётся за новый запуск тестов.

| AC | Сопоставление фактического кода и тестов | Доказательства и состояние |
| --- | --- | --- |
| AC-001 | schemas.py:19–63: точные поля, extra forbid, required FK, explicit null rejection, exclude_unset и Read.from_attributes. test_batch_schemas.py:14–35,80–113 проверяет формы и шесть ключей. | C1 S114; статически соответствует, итоговая приёмка не завершена. |
| AC-002 | schemas.py:20–45: trim/границы/null/date; схемные тесты:37–77; service:118–126 и API:81–98,167–171 проверяют очистку/сохранение/Unicode/date. Кросс-обязательности quantity/unit нет. | C1 S/H, F; статически соответствует. |
| AC-003 | Публичный Measurement импортирован как Quantity; прочитан оригинальный валидатор finite/>0/exponent/bound. Сервис не округляет и не использует float; Read Decimal. Схемные тесты:46–57,99–113; service:34–52; API:61–70,163–165. | C1 S/V/H, F; статически соответствует. |
| AC-004 | batch_service.py:38–76: get/create/list/update, неизвестный Batch первым, require_variant до setattr, delete отсутствует. Service tests TestCreate/GetAndList/Update, включая перенос между Product. | C1 V55; статически соответствует. |
| AC-005 | batch_service.py:79–86: один commit, rollback SQLAlchemyError, классификация только sqlstate+constraint+table. Tests:147–243: реальный commit-spy, настоящий FK rollback/reusable Session, реальные чужие diagnostics и отсутствие retry. | C1 V55 и F; статически соответствует. |
| AC-006 | batch_service.py:51–53: SQL id ASC/limit/offset/default50, без фильтра/join. Tests:54–60,70–99,128–131 и API:72–79,101–110: дубли/null/global pagination. | C1 V/H; статически соответствует. |
| AC-007 | router.py:13–60 и include diff: четыре маршрута, POST201+absolute Location, GET/list/PATCH200, no DELETE/PUT. API TestBatchEndpoints проверяет followable Location, empty PATCH и 405 с сохранением строки. | C1 H88; статически соответствует. |
| AC-008 | Router преобразует только доменную ошибку в 404; Pydantic/FastAPI validation, default safe500. API:122–214 проверяет 422 до сервиса, приоритеты, null/extra, no partial write, no Location при ошибке. | C1 H88; статически соответствует. |
| AC-009 | tests/test_batches_openapi.py полностью просмотрен: два path/четыре операции, refs/tags/summaries/unique IDs, статусы, обязательный body, nullable/date/Decimal; no linking/delete/put. | C1 O10, F; статически соответствует. |
| AC-010 | Фактический продуктовый diff соответствует amended allowlist; tests/conftest.py и Batch model прочитаны как контекст. C1 содержит F1094 и final ALL3771; 17 hashes совпали. | Проверка underlying F/ALL/G не завершена: большой совмещённый вывод инструмента был усечён. PASS не присваивается на основании одного пересказа C1. |

## Проверки и границы доказательств

Ревьюер **не запускал pytest/Alembic/frontend повторно** и не изменял зависимости, модели, миграции, настройки или данные. Только read-only чтение, git diff/status/rev-parse и сравнение hashes.
[C1](../evidence/TASK-MVP-04-C1.md) прочитан с историей исходных отказов и continuation. Он содержит точные команды/CWD/exit и inline S114/V55/H88/O10; F1094 и final ALL3771 с exit0 заявлены в пакете. [F](../evidence/TASK-MVP-04-F.txt), [ALL-final](../evidence/TASK-MVP-04-ALL-final.txt) и [G-final](../evidence/TASK-MVP-04-G-final.txt) были запрошены инструментом, но совмещённый вывод усечён, поэтому полное независимое подтверждение этих логов здесь не заявляется. Это пробел просмотра, не доказательство ошибочности или отсутствия исходных артефактов; повтор тестов этим не оправдывается.
Просмотрен хвост исходного [ALL](../evidence/TASK-MVP-04-ALL.txt): семь конкретных старых OpenAPI totals failures, `7 failed, 3764 passed, 1 warning`; история сохранена. Просмотрен [coordinator-G-cleanup](../evidence/TASK-MVP-04-coordinator-G-cleanup.txt): общий git diff --check exit0 после удаления чужой EOF-ошибки. В видимом G-final model/migrations и tests/test_batch.py/conftest.py diffs пусты, HEAD совпадает. Alembic e4b8c2d16a70/13 отражён C1; заново не запускался.
API fixture действительно сохраняет и восстанавливает get_db и чужие overrides; временные Settings направляют LOG_FILE/STORAGE_ROOT в tmp_path, monkeypatch app.main.get_settings восстанавливается; TestBatchFixtures покрывает оба прежних состояния и исключение.

## Стабильная запись блокировки

**MVP04-R2-001 — BLOCKED, ресурсный лимит (не продуктовый severity BLOCKER/MAJOR).**
Критерий: завершённая независимая приёмка, прежде всего AC-010; location: данный review, раздел проверок.
Наблюдение: hard review input cap400000 включает cached input, каждый следующий шаг повторно оплачивает накопленный контекст; оставшегося резерва недостаточно для недостающего просмотра и безопасного завершения всей цепочки. Выводы крупных batch reads усекались; повторные чтения уже увеличили фактический расход. Ревью остановлено без PASS.
Воспроизведение/доказательство: tool outputs текущего rollout с truncation и cumulative token_count; последний безопасный snapshot ниже. Ожидание: полный просмотр сохранённых F/ALL-final/G и завершение review внутри явно выделенного бюджета. Закрытие требует нового явного решения пользователя о ресурсе; текущий worker не запускает новый call/context, не сбрасывает расход, не исправляет код и не присваивает PASS. Новый слот/повтор не подразумевается.
MINOR/NIT backlog не добавлен. Следующий владелец — координатор: зафиксировать BLOCKED и фактический расход; продуктовый commit по этому отчёту не разрешён. Этот review расходует call4 и первый review slot; отсутствие продуктового FAIL не возвращает расход.

## Фактические модель и расход

Requested/effective `gpt-6-astra / high` подтверждены review-start-metadata; собственный turn_context подтверждает ту же модель/effort и CWD. Provider openai, отдельный rollout указан ниже. До review сообщено 11534652/12000000 input. Cached input уже входит в input, дополнительно не складывается. Snapshot ниже — последний наблюдаемый на момент записи, **не финальная стоимость**: запись отчёта/worker_done/последний ответ могут ещё отразиться позднее. Координатор должен дочитать terminal token_count после завершения; финальные значения, недоступные самому worker до завершения, не выдумываются. Сбросов, новых workers/Run/Task, model/account/plan changes и provider exhaustion не было.

`json
{
    "timestamp":  "2026-10-26T12:01:12.544Z",
    "usage":  {
                  "input_tokens":  297176,
                  "cached_input_tokens":  233984,
                  "cache_write_input_tokens":  0,
                  "output_tokens":  2112,
                  "reasoning_output_tokens":  236,
                  "total_tokens":  299288
              },
    "last_usage":  {
                       "input_tokens":  76772,
                       "cached_input_tokens":  63488,
                       "cache_write_input_tokens":  0,
                       "output_tokens":  864,
                       "reasoning_output_tokens":  123,
                       "total_tokens":  77636
                   },
    "model":  "gpt-6-astra",
    "effort":  "high",
    "rollout":  "C:/Users/user/.codex/sessions/2026/10/26/rollout-2026-10-26T14-58-48-01a17813-d547-7581-8499-c5aa94ab0427.jsonl"
}
` 
