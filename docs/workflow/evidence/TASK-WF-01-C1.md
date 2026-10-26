# TASK-WF-01-C1 — evidence

Дата: 2026-10-26. Baseline: `main`, HEAD
`a405968401eefe6bcbbc2ca3302d14072eb63509`, рабочее дерево до правок WF-01
чистое. TASK/AC: `docs/tasks/TASK-WF-01.md` (заморожены до launch).

## AC-001 — локальный сервер

Выполнено координатором 2026-10-26 (preflight):

```text
health=ok models=nemotron-bolt ctx=32768 pid=8304
started=2026-10-26T07:40:11.739474+03:00
exe=D:\AI\NemotronBoltE4B\bin\llama-server.exe
log=D:\AI\NemotronBoltE4B\logs\server-20261026-074011-714475.stderr.log
```

Сервер запущен через WMI-процесс вне job терминала (`Start-Bolt.ps1`,
`logs\wmi-start.log`, exit 0). `/v1/models` вернул ровно `nemotron-bolt`;
`n_ctx` = 32768. Провайдер `local-nemotron` указывает на
`http://127.0.0.1:18080/v1`, cost 0. Точный PID/лог перепроверить перед review:
сервер может быть перезапущен только штатным `Start-Bolt.ps1`.

## AC-002 — launch receipt

2026-10-25 13:00 предварительная попытка запуска локального OpenCode через
Orca завершилась ошибкой (сервер в тот момент был остановлен):

```json
{"ok": false, "error": {"code": "capability_unsupported",
 "message": "The execution host cannot verify this OpenCode model launch."}}
```

Файл: `D:\AI\NemotronBoltE4B\logs\orca-edr-launch-20261025-130043-537.json`.
Облачный fallback не запускался.

Повторная попытка 2026-10-26 после подъёма сервера (PID 8304, health ok):

```text
orca agent launch --agent opencode --worktree current \
  --model local-nemotron/nemotron-bolt --prompt <handover> --json
→ exit 1
{"ok": false, "error": {"code": "capability_unsupported",
 "message": "The execution host cannot verify this OpenCode model launch."}}
```

Сырой ответ: `docs/workflow/evidence/TASK-WF-01-launch.json`. Модель в launch
receipt не подтверждена. Пользователь 2026-10-26 разрешил альтернативный запуск
(поправка ADR-011). Попытка 2 выполнена: Orca `terminal create` +
`OpenCode-Bolt.ps1` с `--model local-nemotron/nemotron-bolt`; handle
`term_356c9014-e142-4bcf-98a5-6a42769ee524`, worktree
`D:/Antigravity/EquipmentDocumentationRegistry`; команда —
`TASK-WF-01-terminal-command.txt`, receipt — `TASK-WF-01-terminal.json`.
TUI: `Build · Nemotron Bolt E4B (local)`. OpenCode-сессия
`ses_e89726004ffeafCU74n5N64Qki`: provider `local-nemotron`, model
`nemotron-bolt`, cost 0. **PASS** по AC-002; терминал закрыт после сбоя
координации (см. AC-004).

## AC-003 — привязка Run

Исходная привязка Run была устаревшей (`term_d5da…`, generation 3, вкладка
закрыта). 2026-10-26 выполнено:

```text
orca orchestration run-use --id run_68046cea3eb4 --json
→ coordinator_handle=term_5ee91075-15e2-494f-8c61-994d6fd16a28
  consumer_generation=4
```

Передача новой сессии: generation 5 достигнут
(`coordinator_handle=term_356c9014…`), но локальная сессия сфабриковала
Orca/session output (AC-004) и была закрыта; пользователь 2026-10-26 разрешил
вернуть облачного координатора. `run-use` восстановил
`term_5ee91075…`, generation 6. **FAIL** AC-003: handover не удержан;
параллельных координаторов нет.

## AC-004 — фактический статус Orca

На 2026-10-26 после попытки 2:

```text
run-show → run_68046cea3eb4; coordinator term_356c9014…; generation 5
(локальная сессия), затем term_5ee91075…; generation 6 (возврат).
terminal list → term_5ee91075… (local, opencode, worktree main); term_356c9014…
закрыт, ptyKilled=true.
worker-list → 50 записей; фиктивного worker "opencode-coordinator" нет.
```

Локальная сессия вывела сфабрикованные JSON: worker
`worker_7241d4f2-87d0-4e2f-b021-3e109f6b9185` и сессию
`session_1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d`, которых нет в реальном
`worker-list`/OpenCode. Сырой экран: `TASK-WF-01-local-failure.md`.
**FAIL** AC-004: фактические ID/статусы не подтверждены.

## AC-005 — маршруты и default

SHA-256 глобального `C:\Users\user\.config\opencode\opencode.jsonc`:

```text
31032AD46AB3230E75B9A9B0EE9CB255630D188C25949438C76AD9940A5CAE81
```

Default остаётся `opencode/minimax-m3.1-flash-free`; `local-nemotron` добавлен
как отдельный провайдер, глобальный default не менялся. Маршруты: исполнитель
`deepseek-v4.1-flash-free`, R1 `minimax-m3.1-flash-free`, R2/R3 Codex.

## AC-006 — zero-cost / без облака

**PASS для локальной сессии:** OpenCode export
`ses_e89726004ffeafCU74n5N64Qki` — provider `local-nemotron`, model
`nemotron-bolt`, cost 0; лог сервера PID 8304 содержит запросы; облачного
provider в сессии нет. После сбоя пользователь разрешил вернуть облачного
координатора (generation 6); это отдельное исключение, не тихий fallback.

## AC-007 — отсутствие продуктовых изменений

На 2026-10-26 до launch:

```text
git status --short
 M docs/workflow/HISTORY.md
 M docs/workflow/STATE.md
?? docs/tasks/TASK-WF-01.md
```

Разрешённые пути: `docs/tasks/TASK-WF-01.md`, `docs/workflow/STATE.md`,
`docs/workflow/HISTORY.md`, `docs/workflow/evidence/TASK-WF-01-*`,
`docs/workflow/reviews/TASK-WF-01.md`. Продуктовых файлов нет.

## AC-008 — инварианты handover

Handover-промпт сохранён в `docs/workflow/evidence/TASK-WF-01-prompt.txt`.
Он запрещает продуктовые правки, push/merge/deploy, облачный fallback и
выдуманные данные; при сбое локальных предпосылок требует BLOCKED. Локальная
сессия нарушила инвариант «не выдумывать ID/статусы» (AC-004), поэтому
**FAIL**; терминал закрыт, ложные evidence не записаны.

## AC-009 — независимое R1-ревью

**FAIL:** R1 не запускался; передача заблокирована сбоем локальной координации.
Отчёт `docs/workflow/reviews/TASK-WF-01.md` не создан.

## AC-010 — документы

**PASS после обновления:** STATE/HISTORY/TASK отражают BLOCKED; PASS не
присвоен; STATE ≤ 3 КиБ; TASK-MVP-04 разрешён отдельным решением пользователя
от 2026-10-26 после возврата облачного координатора.

## Итог

TASK-WF-01 — **BLOCKED**: альтернативный terminal create + OpenCode-Bolt.ps1
подтвердил локальную модель (AC-002/AC-006 PASS), но локальная сессия
сфабриковала Orca/session output (AC-004 FAIL) и не удержала handover
(AC-003 FAIL); R1 не запускался (AC-009 FAIL). Пользователь 2026-10-26
разрешил вернуть облачного координатора (generation 6) и продолжить
TASK-MVP-04; это зафиксировано в APPROVALS/HISTORY.
