# WF-01 — замороженная исправленная подача A1/C2, call3/4

Дата: 2026-10-26, Europe/Moscow. **Результат исполнителя: BLOCKED**, не
приёмка WF-01 и не проектный PASS. Необходимая предпосылка безопасных
разрешений живого координатора не выполнена; worker_done будет `failed`.
Платный повтор и продуктовый dispatch отключены, successor не запускался.

## Основание, пределы и идентичность

Workspace `D:/Antigravity/EquipmentDocumentationRegistry`, ветка `main`,
baseline/HEAD `a405968401eefe6bcbbc2ca3302d14072eb63509`.
Существовавшие изменения и untracked MVP-04 design сохранены; коммитов нет.
Все AC-001…010 сохранены, исправлена только разрешённая подстановка маршрута.
Источник решения — `D:/AI/NemotronBoltE4B/logs/WF01-extra-budget-20261026.json`:
ответ «Разрешаю» на два дополнительных вызова, записан11:33:55 MSK.
Исходные setup + Luna review остаются расходом2/2; новый предел4 calls,
2 full-review. Исходный Sol-план не узаконивает прежний Luna-запуск.
Повторное ревью разрешено отдельно как Astra high, только вперёд.
Глобальные модели/аккаунт/тариф, кредиты, продуктовые требования и данные,
push/merge/deploy не менялись. Исключение истекает27.10 00:00 MSK.

Текущий исполнитель установлен живым preamble и receipt
`D:/AI/NemotronBoltE4B/logs/wf01-sol-correction-20261026-receipt.json`:

| Поле | Фактическое значение |
| --- | --- |
| Run | `run_68046cea3eb4` |
| Task / Dispatch | `task_efe531f9842f` / `ctx_62c8a01dda32` |
| Worker terminal | `term_8bb93ef6-f806-4154-8f6a-158ebe096521` |
| Requested/effective/живой model | `gpt-6.1-sol`, effort `medium` |
| Stable request | `14475672-6f45-4071-926f-05c23cc99187` |
| Текущий coordinator | `term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`, generation9 |
| Control receipt | `D:/AI/NemotronBoltE4B/logs/edr-approved-control-20261026-launch.json` |

Исторический generation8: `term_6f7a2a3e-51b1-4c5b-9056-734a90cd49e7`,
receipt `logs/edr-control-20261026-launch.json` не менялся.
Небезопасный gen7 `term_f2e42ac1…` закрыт11:00:26 MSK по сохранённой истории.
Он ошибочно назван worker в старом C2; настоящий setup worker —
`term_b6bac716-303a-4c27-863a-0cd231697740`.
Наследуемая переменная `ORCA_TERMINAL_HANDLE` не заменяет live Dispatch.

## Учёт подхода, вызовов и ревью

По HISTORY, C1, C2 и фактическим Dispatch восстановлен A1:
первоначальная подача и один независимый Luna review потребили первый
full-review. Ранний текст отчёта с AC-004/008 и окончательный текст с
AC-009/010 относятся к одному `ctx_1fed9cb1a43e`; это не доказательство
второго отдельного запуска. Старое имя C2 не является новым review slot.
Текущая работа — единственная исправленная подача C2; следующий
предусмотренный review — единственный повтор2/2, не третий review.
Новый подход A2 не объявлялся. Если найдётся доказательство второго ранее
потреблённого review, цепочка BLOCKED без переименования или возврата лимита.

Ledger `logs/WF01-extra-ledger-20261026.json` сохраняет предыдущую запись,
точный request, used3 + reserved1 =4/4; full-review used1 + reserved1 =2/2.
Call4 закреплён за отдельной `gpt-6-astra / high`, статус
`BLOCKED_NOT_STARTED`, отчёт `docs/workflow/reviews/TASK-WF-01-repeat.md`.
Ни receipt, ни Dispatch повторного ревью не выдуман; отчёта пока нет.
Call3 не возвращается при failed delivery; новых correction/review calls,
скрытых subagents и successor tasks нет. Изолированный input расход всего
логического TASK недоступен; агрегаты разных rollout не суммируются как
достоверная атрибуция TASK и не объявляются нулевыми.

## Фактические наблюдения текущей сессии

Полные результаты, точные команды, CWD, UTC-время и exits сохранены в
`D:/AI/NemotronBoltE4B/logs/WF01-call3-observations.json`; воспроизводящий
read-only сценарий — `checks/factual-wf01-call3.ps1` в том же host-каталоге.
Все команды ниже выполнены из корня workspace, exit0 и Orca `ok=true`,
если явно не указано иначе:

```powershell
orca orchestration run-show --id run_68046cea3eb4 --json
orca orchestration run-current --json
orca orchestration worker-list --run run_68046cea3eb4 --limit 3 --json
orca terminal list --worktree path:D:/Antigravity/EquipmentDocumentationRegistry --limit 10 --json
orca orchestration worker-show --dispatch ctx_eba8fecff71e --json
orca orchestration worker-show --dispatch ctx_1fed9cb1a43e --json
orca orchestration worker-show --dispatch ctx_62c8a01dda32 --json
orca orchestration worker-show --dispatch ctx_c254370b2df1 --json
Invoke-RestMethod http://127.0.0.1:18080/health -TimeoutSec 3
Invoke-RestMethod http://127.0.0.1:18080/v1/models -TimeoutSec 3
powershell.exe -NoProfile -File D:/AI/NemotronBoltE4B/Open-EDR-Approved-Control-20261026.ps1 -CheckOnly
powershell.exe -NoProfile -File D:/AI/NemotronBoltE4B/Read-EDRQueue.ps1 -Operation Status
git status --short
git diff --name-only a405968401eefe6bcbbc2ca3302d14072eb63509..HEAD
```

`run-current` из worker возвращает `run:null`, что не отменяет owning Run
Dispatch. Bounded fleet имеет `hasMore=true`; полного fleet export нет,
отсутствие прочих workers из первой страницы не утверждается. Четыре exact
worker-show доказывают setup/review succeeded, текущий Sol in_progress/live,
старый DeepSeek `task_efc8f84abfbc / ctx_c254370b2df1` failed/exited.
Ready/input_accepted у Sol не означает done; `agentWait:null` не доказывает exit.
Старые setup/review resources владельцем освобождены; их exact ID сохранены.

Health=`ok`; единственная модель=`nemotron-bolt`, context32768. CIM PID8304
подтверждает ожидаемый llama-server и loopback18080. Серверный лог
`logs/server-20261026-074011-714475.stderr.log` обновлялся после нового launch,
последний наблюдённый task36992 завершён с truncated0. Это доказательство
локальной работы сервера, не изолированный trace каждого отдельного запроса.

Metadata helper выполнен через
`C:/Users/user/AppData/Local/Programs/Python/Python312/python.exe`:
`Get-CoordinatorMetadata.py` вернул `ses_e88a003c5ffed9Qsr23l0i47OU`,
created_epoch_ms1793004141626 (11:42:21.626 MSK),15 local assistant messages,
local-nemotron/nemotron-bolt, cost0, cloud_provider_count0.
Receipt записан11:42:18.643 MSK; actual opencode PID14924 создан11:42:18.993 MSK
с явными `--model local-nemotron/nemotron-bolt --agent edr-coordinator` и
approved-control bootstrap. Корреляция времени/команды/receipt проверена;
старые session metadata не выданы за текущие.

Глобальный OpenCode config hash:
`31032AD46AB3230E75B9A9B0EE9CB255630D188C25949438C76AD9940A5CAE81`;
default остаётся историческим minimax. Dedicated профиль local-only,
`-CheckOnly` вернул CONFIG_VALIDATED, launched=false, run_mutated=false.
Это проверка подготовленного файла, не применение его разрешений к live inline.

## Исправленные guards и предел проверки

`Read-EDRQueue.ps1` остаётся явным адаптером. Нет background scheduler,
native model API, fallback, product operation или произвольного shell argv.
Status делает ограниченные реальные чтения и точные Task/Dispatch сверки.
Мутации требуют receipt terminal/incarnation, живой opencode и проверенной
цепочки процессов с pinned PID/creation time; Codex ancestor отвергается.
Bind теперь только проверяет уже существующую привязку; не делает run-use.
Неуспешные receipts не пропускаются как отсутствующие workers.
Release требует exact owned Dispatch и settled outcome. RecordControl
заблокирован после заморозки, чтобы не затереть факты/счётчики.

Ack не автоматический: требуется весь delivery и явный список обработанных
ID, matching settled outcome для worker_done, подтверждённый reply для
question. Status/escalation/посторонняя почта не удаляется; owner должен её
обработать. Существующий `guarded-last-delivery.json` не менялся этой работой.
Reply привязан к actual repeated-review receipt вместо старого gen8 текста.

Подготовленная последовательность стадий сохраняет full spec, stable request,
точные model/effort, native exit/ok, budget, successful Sol outcome и frozen
manifest/quota prerequisites. Источник post-start model может временно
отсутствовать: это `started_unverified`, без дублирующего старта;
подтверждённый mismatch останавливает цепочку. Receipt replay возвращает
`completion_not_inferred`, а не устаревающий `completed=false`.
Owner follow-up `msg_c6d095c16473` сообщил эту гонку в11:47:45 MSK;
живой worker-show подтвердил правильный Sol medium, retry не было.

**Оставшаяся предпосылка / BLOCKED:** active inline profile разрешает shell
по `*Read-EDRQueue.ps1*`; такой wildcard шире конкретного безопасного вызова.
Подготовленный JSON заменён точными allow-командами без произвольных аргументов,
но изменение файла не меняет живые permissions. Поэтому StartAuthorizedFix и
StartAuthorizedReview сейчас дополнительно закрыты fail-closed; их staged
проверки не считаются испытанным запуском. Dynamic ack/reply/release не входят
в подготовленный точный allowlist; это осознанное ограничение до действий
владельца. Достоверного подтверждения live permission enforcement нет.

## Проверки отказов

Выполнены реальные отрицательные проверки из текущего worker:

- `Read-EDRQueue.ps1 -Operation ReleaseSettled -DispatchId ctx_62c8a01dda32`
  с намеренно скопированным env coordinator handle: exit1, ok=false,
  `A Codex worker cannot act as the control caller`; release не выполнен.
- `Read-EDRQueue.ps1 -Operation Bind` при отсутствующем caller: exit1,
  `Caller is not the receipt-owned control terminal`; binding не менялся.

Сценарий `checks/test-wf01-negative.ps1`, exit0, отдельно проверил извлечённые
функции guard с **синтетическими** native exit7, ok=false, malformed JSON и
wrong Task ID. Все четыре отвергнуты; это не actual Orca receipts.
Результаты — `logs/WF01-call3-negative-tests.json`.
PowerShell AST обоих активных файлов синтаксически корректен; JSON текущего и
старого профилей, decision, ledger и launch receipts распарсен без ошибок.
Операции StartAuthorizedFix/Review в тестах не выполнялись вообще.
Положительная мутация от нового caller не проверена — новая authority ещё не
создана. Backend/frontend/migration tests не запускались;3530 passed относится
только к2026-10-25, продуктовые файлы не менялись.

## Сохранённые сбои и доступный бюджет

Старый review `docs/workflow/reviews/TASK-WF-01.md` не изменён: FAIL по
WF01-AC009-001 (Luna вместо Sol) и WF01-AC010-001 (gen7 вместоgen8).
Раннее AC-004/008 ложное heartbeating/investigating при failed/exited
сохранено в HISTORY/C2. Сохранены C1 false worker/session IDs, пять
неуспешных edit с заявлениями успеха, context/compaction и потеря ID,
rejected worker-start, ошибочная dotted-property projection и преждевременный
review до фактического завершения setup. Denial/readiness не считаются успехом.
Старый C2 дополнен явной ссылкой на это исправление, без переписывания истории.

Quota источник `logs/WF01-call3-quota.json`: наблюдение11:51:18.985 MSK,
primary51%,300 минут, resets_at1793013647 (14:20:47 MSK), то же окно baseline15%.
Secondary8%,10080 минут, reset1793600447 — отдельное окно.
Rollout текущего call3: input847207, cached758912, output8051,
reasoning1185,total855258. Это агрегат rollout на тот момент, не изолированная
стоимость полного WF-01; подписочный расход не пересчитан в API dollars.
Исторические наблюдения15/18/26/29/31/38% привязаны к их времени, не смешаны
с новым окном. При исчерпании — остановка до явного решения, даже после reset.

## Что должен сделать владелец

Это подготовка, не поручение запустить новый платный worker. После actual
failed settlement этого Dispatch владелец должен сохранить текущие receipts,
mail и ledger; контролируемо остановить старый coordinator и запустить
подготовленный `Open-EDR-Approved-Control-20261026.ps1` через Orca terminal create.
Точную syntax команды следует брать из установленного `terminal create --help`.
Он должен сохранить НОВЫЙ launch receipt, сверить реальную inline effective
permission с точным allowlist, новый opencode PID/creation/incarnation и
существующий Run binding, обновить process pin и snapshot как операционные
факты. Guard самостоятельно restart/rebind/kill не делает, старые ID не
переиспользует. Текущий Bind дополнительно ожидает generation9 и не годится
для новой generation без явной сверки владельцем.

До устранения этих конкретных предпосылок и решения владельца оставлены
BLOCKED и paid-start lock. Дополнительная коррекция call5 не разрешена;
call4 зарезервирован, но не расходован и не запускается после failed
исправления автоматически. Продуктовый gate вообще не добавлен: будущий
MVP-04 может стать доступен только после matching Astra completion плюс
`VERDICT: PASS` для exact packet, correct model/high, budget design1/4,
old DeepSeek failed/exited и отсутствия другого writer. Сейчас этого нет.

## Заморозка и изменённые файлы

Полный SHA-256 manifest после фиксации этого файла:
`D:/AI/NemotronBoltE4B/logs/WF01-call3-frozen-hashes.json` (он не хеширует сам
себя). Manifest включает packet, неизменённый исходный FAIL, текущие документы,
decision/ledger/receipts, host guards/profile/prompt, проверки и raw evidence.
Существующий baseline diff содержит более ранние изменения других исполнителей;
они не присвоены этой коррекции.

В репозитории изменены только AGENTS.md, ROADMAP.md, ADR-011, APPROVALS.md,
HISTORY.md, STATE.md, TASK-WF-01.md, историческая приписка TASK-WF-01-C2.md
и этот новый packet. Host: Read-EDRQueue.ps1, approved-control JSON/prompt,
ledger; добавлены process pin, raw observations/quota/negative evidence,
manifest, backup исходного guard/profile/prompt и сценарии этой коррекции
в `D:/AI/NemotronBoltE4B/checks/`. Launcher, глобальный config, product и старый
FAIL report не менялись. STATE2317 байт. Повторного отчёта и PASS нет.
