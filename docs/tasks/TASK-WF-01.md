# TASK-WF-01 — Локальный Nemotron как координатор Orca

Статус: **WITHDRAWN BY USER (2026-10-26)**. Работа прекращена; повторные
запуски, исправления и приёмка запрещены. Исторический результат остаётся
BLOCKED/NOT_ACCEPTED, ограниченное исправление A1/C2 не было принято.
Пользователь решил больше не использовать Nemotron; текущая маршрутизация —
Codex по `docs/workflow/MODEL-ROUTING.md`. Сохранять документ и evidence как
аудиторскую историю; не считать TASK-WF-01 активным проектным блокером.

Исторический независимый FAIL сохранён в `docs/workflow/reviews/TASK-WF-01.md`.
Run `run_68046cea3eb4`: coordinator `term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`, generation 9.
Исполнитель: `task_efe531f9842f` / `ctx_62c8a01dda32`, terminal
`term_8bb93ef6-f806-4154-8f6a-158ebe096521`, фактический Sol medium.
Класс R1, пользовательское исключение WF01_EXTRA_2_20261026: call3/4 —
исправление, call4/4 — отдельная Astra high, единственный повторный слот 2/2.
Ранее setup + Luna review потребили 2 calls и 1 full-review; они не возвращены.
Функциональные требования и AC-001…010 сохранены. Исторические запуски,
preflight и runbook ниже описывают прежние поколения и не разрешают повторять
старые команды. Текущее основание — APPROVALS и новый C2-correction packet.
Активный inline wildcard нельзя исправить правкой JSON; старты заблокированы
до действия владельца. Продуктовый dispatch выключен безусловно.

## Цель и область

Передать роль координатора Run `run_68046cea3eb4` новой сессии OpenCode на
локальной модели `local-nemotron/nemotron-bolt` через `http://127.0.0.1:18080/v1`
так, чтобы:

- Orca terminal receipt подтверждает запуск с явной моделью, handle и рабочую
  копию; фактическая модель подтверждена одобренной альтернативной
  совокупностью (OpenCode metadata, локальный лог/процесс, Run binding);
- новая сессия привязалась к существующему Run и читала фактический статус
  через Orca-инструменты, не выдумывая данные;
- параллельных координаторов не осталось;
- локальная сессия не расходовала облачные токены;
- маршруты исполнителя (`deepseek-v4.1-flash-free`), R1 (`minimax-m3.1-flash-free`)
  и R2/R3 (Codex) сохранились;
- при неготовом сервере, неподтверждённой модели или неработающем инструменте
  цепочка остановилась как BLOCKED без облачного fallback.

Целевые компоненты: Orca Run/terminals, `docs/tasks/TASK-WF-01.md`,
`docs/workflow/STATE.md`, `docs/workflow/HISTORY.md`, evidence и review WF-01.
Исторический allowlist первоначального запуска (текущее расширение см. APPROVALS): этот TASK, `STATE.md`, `HISTORY.md`,
`docs/workflow/evidence/TASK-WF-01-C1.md`, evidence-файлы WF-01 и
`docs/workflow/reviews/TASK-WF-01.md`.
Не затрагивать: `app/**`, `tests/**`, `alembic/**`, `frontend/**`, `.env`,
`.venv/`, `storage/`, зависимости, глобальный `opencode.jsonc` (только читать),
TASK других этапов. AGENTS/ROADMAP/ADR-011 разрешены текущим ограниченным исправлением документации. Push, merge, deploy и
удаление данных запрещены.

## Preflight (факты до диспатча)

- Baseline Git: `main`, HEAD `a405968401eefe6bcbbc2ca3302d14072eb63509`,
  рабочее дерево чистое; продуктовое состояние — `6827ed3` / `40c6343`.
- 2026-10-25 в 13:00 запуск OpenCode через Orca с локальной моделью вернул
  `capability_unsupported`: «The execution host cannot verify this OpenCode
  model launch»; в тот момент локальный сервер уже был остановлен. Попытка
  сохранена в `D:\AI\NemotronBoltE4B\logs\orca-edr-launch-20261025-130043-537.json`.
- 2026-10-26 сервер Nemotron перезапущен вне job-дерева терминала (WMI,
  `Start-Bolt.ps1`); `/health` = `ok`, `/v1/models` = `nemotron-bolt`,
  `n_ctx` = 32768, процесс `D:\AI\NemotronBoltE4B\bin\llama-server.exe`.
  Точный PID, время старта и лог фиксируются в evidence C1 при проверке.
- Текущая глобальная модель OpenCode: `opencode/minimax-m3.1-flash-free`;
  провайдер `local-nemotron` с cost 0 присутствует, но default не меняется.
- Текущая координационная привязка Run: `term_5ee91075-15e2-494f-8c61-994d6fd16a28`,
  `consumer_generation` 4; при передаче ожидается generation > 4.

## Результат попытки 2026-10-26

Команда:

```text
orca agent launch --agent opencode --worktree current \
  --model local-nemotron/nemotron-bolt --prompt <handover> --json
```

Результат: exit 1, `ok: false`, `error.code: capability_unsupported`,
`error.message: The execution host cannot verify this OpenCode model launch.`
Локальный сервер в этот момент отвечал: `/health` = `ok`, `/v1/models` =
`nemotron-bolt`, ctx 32768, PID 8304. Сырой ответ:
`docs/workflow/evidence/TASK-WF-01-launch.json`.

Результат: `agent launch` не может подтвердить модель. Пользователь 2026-10-26
разрешил альтернативный запуск (поправка ADR-011). Попытка 2 выполнена через
`terminal create` + `OpenCode-Bolt.ps1` с явным `--model`; локальная модель
подтверждена (session `ses_e89726004ffeafCU74n5N64Qki`, provider
`local-nemotron`, model `nemotron-bolt`, cost 0) и Run привязан с generation 5.
Однако локальная сессия вывела сфабрикованные `worker-list`/session ID,
не изменила PENDING-разделы C1 и была закрыта. Сбой зафиксирован в
`docs/workflow/evidence/TASK-WF-01-local-failure.md`. Пользователь 2026-10-26
разрешил вернуть облачного координатора (`term_5ee91075…`, generation 6) и
продолжить TASK-MVP-04; TASK-WF-01 — **BLOCKED**, R1 не запускался.

## Критерии приёмки

Чек-лист заморожен до запуска новой сессии. Ревьюер проверяет строго по нему.

| ID | Критерий | Способ независимой проверки | Severity |
| --- | --- | --- | --- |
| AC-001 | Локальный сервер готов: `/health` = `ok`, `/v1/models` содержит только/ровно `nemotron-bolt` с `n_ctx` 32768, процесс — ожидаемый `llama-server.exe`, провайдер указывает на `127.0.0.1:18080`, cost 0. | Повторить HTTP-запросы, сверить `/proc`/`Get-Process`, `server-state.json`, фрагмент конфига; без секретов. | BLOCKER |
| AC-002 | Новая сессия запущена Orca с явной моделью `local-nemotron/nemotron-bolt` одобренным альтернативным способом: `terminal create` + `OpenCode-Bolt.ps1` (или эквивалент) с `--model local-nemotron/nemotron-bolt`; receipt содержит handle, worktree и точную команду; фактическая модель подтверждена метаданными OpenCode-сессии (`model`, provider, cost 0) и запросом к локальному серверу. | Прочитать terminal create receipt и команду; проверить сессию через доступные метаданные/export, серверный лог и процесс; при несоответствии модели или отсутствии доказательств — FAIL; `agent launch` receipt не требуется по поправке ADR-011 от 2026-10-26. | BLOCKER |
| AC-003 | Новая сессия привязана к `run_68046cea3eb4`; `run-show` показывает её handle и generation > 4; старая привязка (generation 4) больше не действует; параллельных координаторов нет. | `run-show` до/после, `run-current`, `terminal list`; старая вкладка закрыта после передачи либо явно зафиксирована как fenced server-host без роли координатора. | BLOCKER |
| AC-004 | Новая сессия читает фактический статус через Orca: `run-current`, `run-show`, `terminal list`, `worker-list`; её отчёт совпадает с независимым чтением ревьюера; выдуманных TASK/worker ID и статусов нет. | Терминальный вывод новой сессии + независимые read-only команды ревьюера; сравнение generation, handles, task/worker IDs. | BLOCKER |
| AC-005 | Глобальные настройки/default не изменены; отдельный локальный Nemotron профиль/launcher настроен для координатора. Исполнитель и независимый reviewer используют разрешённые Codex-подстановки; облачный OpenCode отключён. | Сравнить хеш глобального конфига, dedicated profile/launcher и model metadata; проверить provider/cost и bounded diagnostics. | BLOCKER |
| AC-006 | Локальная сессия zero-cost и не использует облако: метаданные сессии показывают локальную модель, cost 0 и отсутствие cloud provider; сервер получал запросы новой сессии (лог/PID/слот), без cloud fallback. | OpenCode session metadata/`stats` или эквивалент, лог llama-server, процесс, terminal receipt; секреты не печатать. | BLOCKER |
| AC-007 | Продуктовый код и данные не изменены: `git diff a405968..HEAD` содержит только разрешённые docs/evidence; `git status` не содержит продуктовых, конфигурационных или storage-файлов. | `git diff --stat`, `git status --short`, список путей; сравнение с разрешённым списком. | BLOCKER |
| AC-008 | Инварианты передачи зафиксированы и подтверждены новой сессией: запрет продуктовых правок, push/merge/deploy, облачного fallback и выдуманных данных; при сбое локальных предпосылок — BLOCKED. | Текст handover-промпта в evidence + первый отчёт новой сессии; ревьюер сверяет формулировки и фактическое поведение. | BLOCKER |
| AC-009 | Независимое R1-ревью выполнено отдельным Codex; исходный Sol medium маршрут нарушен Luna-запуском (FAIL сохранён). По WF01_EXTRA_2_20261026 единственный повтор выполняет `gpt-6-astra / high`, проверяет те же AC и историю ошибок, пишет только `docs/workflow/reviews/TASK-WF-01-repeat.md`. | Review report и worker receipt; сверка модели и независимости. | BLOCKER |
| AC-010 | Документы согласованы: STATE/HISTORY/TASK отражают фактический результат, STATE ≤ 3 КиБ, следующий TASK указан только при PASS, ложного PASS/счётчиков нет. | Прочитать документы, сверить с evidence и review; проверить размер STATE. | MAJOR |

Любой FAIL по AC-001…AC-009 блокирует PASS. При BLOCKED запрещено переходить к
следующему TASK до routed PASS. Разрешение Codex-подстановки истекает
2026-10-27 00:00 Europe/Moscow; исчерпание провайдера блокирует цепочку до
нового решения пользователя.

## Handover новой сессии

Новая сессия обязана выполнить шаги в этом порядке и записать фактические
команды/выводы в `docs/workflow/evidence/TASK-WF-01-C1.md`:

1. Прочитать `AGENTS.md`, `docs/workflow/STATE.md`, этот TASK, ADR-011,
   `ROADMAP.md` (раздел workflow) и `docs/workflow/APPROVALS.md`.
2. Привязаться: `orca orchestration run-use --id run_68046cea3eb4 --json`;
   убедиться, что `coordinator_handle` равен `$env:ORCA_TERMINAL_HANDLE`, а
   `consumer_generation` больше 4. Не продолжать при другом handle.
3. Проверить terminal create receipt, команду запуска и фактическую модель
   (AC-002): receipt содержит handle/worktree/команду с
   `local-nemotron/nemotron-bolt`; OpenCode session metadata подтверждает
   модель и cost 0; локальный сервер обслужил запрос. Если доказательств нет
   или модель не локальная — BLOCKED; не запускать облачного координатора.
4. Выполнить read-only проверки Orca: `run-current`, `run-show`, `terminal list`,
   `worker-list`. Не придумывать ID, статусы и результаты.
5. Заполнить evidence C1 по AC-001…AC-008. Не менять продуктовые файлы,
   глобальный конфиг и чужие TASK.
6. Запустить независимого R1-ревьюера:
   `orca orchestration worker-start --spec "<краткий spec>" --worktree current --agent opencode --model minimax-m3.1-flash-free --json`.
   Ревьюер читает evidence, live Orca и TASK, пишет только
   `docs/workflow/reviews/TASK-WF-01.md`, затем `worker_done`. Координатор ждёт
   `check --wait` и обрабатывает сообщение; `worker_done` не является PASS.
7. При PASS: закоммитить только разрешённые docs/evidence/review, обновить
   STATE/HISTORY/TASK, закрыть/оставить fenced старую вкладку согласно AC-003,
   затем подготовить TASK-MVP-04 по действующему маршруту. При FAIL/BLOCKED:
   остановиться, записать фактическую причину, не запускать следующий TASK и не
   переключаться на облако.
8. Не выполнять push, merge, deploy, удаление данных и не менять
   `opencode.jsonc`/`.env`/`storage/`.

## Evidence и проверки

- `docs/workflow/evidence/TASK-WF-01-C1.md`: preflight, terminal receipt,
  привязка, Orca-чтения, zero-cost, git diff, handover-промпт.
- `docs/workflow/evidence/TASK-WF-01-launch.json`: сырой JSON `orca agent launch`
  (историческая неудачная попытка).
- `docs/workflow/evidence/TASK-WF-01-terminal.json`: сырой JSON
  `orca terminal create` для альтернативного запуска.
- `docs/workflow/evidence/TASK-WF-01-session.json`: выдержка метаданных
  OpenCode-сессии (модель/cost), без секретов.
- `docs/workflow/reviews/TASK-WF-01.md`: независимый R1-вердикт.
- Обязательные команды: `/health`, `/v1/models`, `server-state.json`,
  `Get-FileHash` глобального конфига, `orca orchestration run-show`,
  `run-current`, `terminal list`, `worker-list`, `git diff --stat a405968..HEAD`,
  `git status --short`.
- Полный pytest/typecheck/build для WF-01 не требуются: продуктовый код не
  меняется; AC-007 подтверждает отсутствие продуктовых изменений.


## Уточнение WF01_EXTRA_2_20261026 — исправление call3

Решение «Разрешаю» от 2026-10-26 11:33:55 MSK сохранено в
`D:/AI/NemotronBoltE4B/logs/WF01-extra-budget-20261026.json`:
общий потолок 4 вместо 2, полных ревью 2 вместо 1, без возврата расхода.
Исправление — `gpt-6.1-sol / medium`, единственное повторное ревью —
`gpt-6-astra / high`, только вперёд; прежний Luna FAIL остаётся FAIL.
Срок — до 2026-10-27 00:00 Europe/Moscow. Объём AC и продукта не меняется.
Текущий Run `run_68046cea3eb4`, coordinator
`term_0fbc4883-985d-4f82-8d13-4f3bca5ec2b3`, generation 9; generation 8
(`term_6f7a2a3e-51b1-4c5b-9056-734a90cd49e7`) — история.
Новый фактический пакет: `docs/workflow/evidence/TASK-WF-01-C2-correction.md`.
Старый C2 содержит неверный worker handle и устаревшие данные; его нельзя
использовать как текущий снимок. Повторный отчёт предназначен для
`docs/workflow/reviews/TASK-WF-01-repeat.md`; он ещё не создан.
Текущий результат исправления — BLOCKED: активное inline shell-разрешение
слишком широко, подготовленный точный профиль ещё не загружен.
Платные старты и продуктовый dispatch отключены. Restart/rebind/закрытие
координатора исполнителем не выполнялись; требуется действие владельца.
