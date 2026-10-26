# TASK-WF-01 — сбой локального координатора

Дата: 2026-10-26. Run: `run_68046cea3eb4`.

## Факты запуска

- terminal create: `term_356c9014-e142-4bcf-98a5-6a42769ee524`,
  worktree `D:/Antigravity/EquipmentDocumentationRegistry`, receipt —
  `TASK-WF-01-terminal.json`, команда — `TASK-WF-01-terminal-command.txt`.
- TUI: `Build · Nemotron Bolt E4B (local) Nemotron Bolt (local)`.
- OpenCode session: `ses_e89726004ffeafCU74n5N64Qki`; `providerID =
  local-nemotron`, `modelID = nemotron-bolt`, `cost = 0`.
- Привязка Run: `consumer_generation = 5`, coordinator
  `term_356c9014-e142-4bcf-98a5-6a42769ee524`.

## Сбой

После привязки локальная сессия не изменила PENDING-разделы C1 и вывела
сфабрикованные JSON вместо фактического чтения Orca/OpenCode:

```text
worker: worker_7241d4f2-87d0-4e2f-b021-3e109f6b9185, name opencode-coordinator
session: session_1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d, name current_task_session
```

Реальный `orca orchestration worker-list` содержит 50 записей другого формата;
`opencode session list` возвращает массив сессий, а не объект `sessions`.
Фиктивных ID в реальных выводах нет. Это нарушает AC-004 и AC-008
(запрет выдуманных ID/статусов).

Сырой экран терминала сохранён вне репозитория:
`C:\Users\user\AppData\Local\Temp\opencode\wf01-local-fake-output.txt`.

## Решение

Терминал закрыт (`ptyKilled=true`), ложные evidence не записаны. Локальный
сервер PID 8304 остался жив. Пользователь 2026-10-26 выбрал возврат облачного
координатора; `run-use` перепривязал Run к
`term_5ee91075-15e2-494f-8c61-994d6fd16a28`, `consumer_generation = 6`.
TASK-WF-01 — **BLOCKED**; TASK-MVP-04 разрешён отдельным решением пользователя.
