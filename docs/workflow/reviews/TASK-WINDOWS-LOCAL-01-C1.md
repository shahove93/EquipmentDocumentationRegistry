# TASK-WINDOWS-LOCAL-01 — независимое R2 review (C1)

**Дата:** 2026-10-27
**Dispatch:** `ctx_8051ae00e9fd`, task `task_bfa78842c0e9`
**Модель:** `gpt-6-astra/high` (requested=effective)
**Вердикт:** **BLOCKED — не PASS**. Review завершено; приёмка ждёт недостающих
проверок на чистой Windows и интерактивных запусков. Кодовые проверки не выявили
подтверждённого BLOCKER/MAJOR в frozen happy path.

## Объём и provenance

Проверена база `1c362598e67f9a7645de2416e79c2bb8ca3f3dc4`; все 12 новых файлов
исполнителя прочитаны полностью. SHA-256 всех исходников независимо совпали с
`%TEMP%\edr-windows-build\source-ledger.json`; 67 Python-файлов приложения и
14 миграций совпали с упакованной нагрузкой. Проверены отчёт исполнителя,
финальные логи, build manifest, smoke results, архив backup и production EXE.
Production installer: `EDR-0.2.0-windows-x64.exe`, 55,379,088 bytes,
SHA-256 `b75f7132e2f17988eb213991d22a03fcb965165c5919510087d694c86d21594d`.
Изменения GitHub presentation вне review. Ревьюер не менял файлы, не запускал
installer и не повторял проверки.

## Критерии

| # | Результат | Основание |
|---|---|---|
| 1 | **BLOCKED / NOT_RUN** | Smoke прошёл на Windows 11 build 26300 с уже установленным VC++ Runtime; чистая Windows и Windows 10 не проверялись. Нужен чистый поддерживаемый образ/VM, waiver не подразумевается. |
| 2 | **PARTIAL / NOT_RUN** | Зафиксированы только loopback listeners `127.0.0.1:18765/55432`, host/origin guards и метаданные ярлыка. Smoke запускает `python.exe --no-browser` и проверяет HTML shell; настоящий `.lnk → launcher → browser` и React UI не запускались. |
| 3 | **PASS — native API/data scenario** | Synthetic запись/PDF созданы, скачаны с теми же байтами до и после restart; PDF SHA-256 `1412a4820f8723821848d52e799c5d78fb344afdfc3b661692f9b926b3901b3f`. Интерактивный UI не заявляется. |
| 4 | **PASS — native backup/restore** | Backup включает DB и файлы; ревьюер прочитал retained ZIP и сверил manifest sizes/checksums, revision `e4b8c2d16a70`, оригинальный и восстановленный PDF. Busy backup и nonempty/existing targets отвергаются. |
| 5 | **PASS — injected SQL migration failure** | Alembic clone миграция действительно завершилась с exit 1; исходный `runtime.json`, sentinel-вложение и доступность исходного документа/PDF сохранены. Не доказывает поведение будущего произвольного миграционного кода, пишущего внешние файлы. |
| 6 | **PASS — tested ordinary update/uninstall** | Update/uninstaller завершились exit 0; runtime pointer, cluster и attachment sentinel остались, запись/PDF читаются после update. Не проверено аварийное завершение супервизора перед update/uninstall (R01). |
| 7 | **PARTIAL / BLOCKED** | Финальный backend: `3803 passed, 1 warning` за 491.61 s; 32 native tests, frontend typecheck/build и production compile имеют записанные успешные результаты. Clean-install smoke в чистой Windows **NOT_RUN**, так что обязательный критерий не закрыт. |
| 8 | **PARTIAL / NOT_RUN** | Исходники содержат проверку VC++ Runtime и официальный URL; silent forced-missing probe отказал до записи payload, CRT DLL отсутствуют в EXE. Интерактивное окно/открытие страницы Microsoft и действительно runtime-free система не проверялись. |

## Acceptance gates

- **G01 — блокирует:** чистый Windows ресурс (критерии 1/7). Чистая среда
  обязательна для согласованной приёмки; без неё status остаётся BLOCKED.
- **G02 — блокирует:** интерактивный ярлык/UI и отсутствующий CRT → browser flow
  (критерии 2/8). Метаданные и кодовые вызовы не заменяют наблюдение запуска.

## Риск backlog

**R01, MINOR:** `app/windows_local.py:427-430` возвращает success, когда lock
супервизора свободен, не проверяя orphan PostgreSQL, запущенный отдельным
`pg_ctl` процессом. После аварии супервизора `Stop EDR` может не остановить
кластер, а `edr.iss:84-86` продолжить update/uninstall. Наблюдаемой потери данных
не было; проверка update заранее останавливала EDR, поэтому crash edge не
проверен. Оставить отдельной задачей; закрытие — изолированный orphan process
smoke плюс остановка принадлежащего EDR кластера либо безопасный отказ менять
installation.

Другие ограничения: EXE unsigned; порты фиксированы; Cyrillic paths на томах без
8.3 aliases требуют ASCII path; optional POSIX storage reconciliation CLI не
портирован. ACL-код очищает inherited grants, но не посторонние explicit ACEs на
заранее настроенных custom directories. Не трактовать это как подтверждённые
дефекты frozen criteria.

## Следующий шаг

Пользователь разрешил подготовить Windows Sandbox, но текущая shell-сессия не
имеет admin elevation (`Enable-WindowsOptionalFeature ...` вернул `requires
elevation`), а пользователь сейчас не у ПК и перезагрузиться не может. Не
пытаться обходить UAC. После ручного включения Sandbox и reboot выполнить
проверки G01/G02. Installer/production artifact остаются локальными; commit,
push, merge и deployment не выполнялись. Provider usage review: unavailable.
