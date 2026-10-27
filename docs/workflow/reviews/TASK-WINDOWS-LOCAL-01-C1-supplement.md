# TASK-WINDOWS-LOCAL-01 A1/C1 — независимое дополнение по G01/G02

Дата: 2026-10-27. Риск R2. Режим: ограниченная дополнительная экспертиза отсутствовавших доказательств, без новой подачи кода и без повторного полного ревью.
Ревьюер: task_07a7800b876e / ctx_9237392c299b, terminal term_6e206529-b517-45d6-a61a-44716655548c.
Исходная реализация: ctx_68e68e4cf252; завершённое полное C1: ctx_8051ae00e9fd; новый сбор доказательств: ctx_996ca9959986; Run run_5a6ffc6d06c6.

**Вердикт: G01 — PASS, G02 — PASS. Совокупность прежнего полного C1 и настоящего дополнения поддерживает PASS и приёмку TASK по неизменным критериям 1–8.** Ресурсные пробелы закрыты; нового BLOCKER/MAJOR не установлено. R01 MINOR остаётся в backlog. Координатор фиксирует итоговую приёмку; исторический C1 BLOCKED сохраняется как действовавший на момент того ревью, а не переписывается задним числом.

## Основание и пределы экспертизы

Прочитаны AGENTS.md, MODEL-ROUTING.md, autonomous-development SKILL и routing-and-budget/review-policy, orchestration SKILL и справка установленного Orca, TASK-WINDOWS-LOCAL-01.md, C1 review, clean-windows evidence и исходный implementation-report.md. Применён явно заданный проектный маршрут Codex через Orca.

Проверены только новые доказательства критериев 1/2/7/8 и их привязка к прежнему финальному состоянию. Прежние PASS критериев 3–6, включая injected failed migration, переиспользованы. Исходники продукта заново не рецензировались. Установщики, VM, приложение, backend/frontend suites, native smoke и миграционные тесты не запускались. Исключений для повторного исполнения проверок не потребовалось. Новых критериев, изменения архитектуры и waiver нет.

## Идентичность исходников и доказательств

Workspace D:/Antigravity/EquipmentDocumentationRegistry; HEAD/main совпадает с baseline 1c362598e67f9a7645de2416e79c2bb8ca3f3dc4. Git status/diff прочитан только для границы изменений; посторонние GitHub presentation и workflow изменения сохранены.

Командой Get-FileHash -Algorithm SHA256 независимо пересчитаны все 12 финальных файлов по оригинальному %TEMP%/edr-windows-build/source-ledger.json. Совпали 12/12:

| Файл | SHA-256 |
| --- | --- |
| app/local_web.py | affb6c39b2ec61a2c14023a0ce64fa3a469502c3bfe325b3311c739f0583b833 |
| app/windows_local.py | 85de8d3053807d354e1dba99dd2a2cae4072a12a0357a4046697bbc15d63a0af |
| docs/installation/windows.md | fa3348bcc3028a813791f09109c0842616dc0e6e493163b9f20cdf6c9baba9fd |
| packaging/windows/build.ps1 | 1c502ab440c192f0549bce4c011a32c092d7f82d01975df15d9964d86a0a2b05 |
| packaging/windows/prepare.py | 67bde812f84cc417f31c8e22577a4e55d6daf270695b597bf539b6f456c6c847 |
| packaging/windows/requirements.lock | 269bd0c33ead7cab4e78c1dc0c1c32cb73cf416cf9f86178d132cee412179d48 |
| packaging/windows/edr.iss | f0484c01cad30a99f5be82256f97f3bfc6ab1823f11cdb7fcc9c6885b69b6d6f |
| packaging/windows/EDR.cmd | 89acf13db3f74183e2393dd1cf72e4be632cd7a39c7e0e5fa23a64187d3e7ca3 |
| packaging/windows/launcher.ps1 | 3cf7ba26c114210f6adb6a0e438997fa290e2aeddba2974012d2a93c6c3de5ad |
| packaging/windows/smoke.ps1 | c257370e3e029ef228e6008a099a8716367b1e6c53feb9c7356da198a7c74df7 |
| packaging/windows/smoke.py | e44d57bfd5156c156cb4cb1610311915cace5e403be06fb118eed4ba40af3b20 |
| tests/test_windows_local.py | 422e33c2f3d1c6e07966475026f6a56cdb253d75d9235974e9df9485164e0d22 |

Независимо пересчитаны оригинальный release/EDR-0.2.0-windows-x64.exe и sandbox/input/production.exe: оба SHA-256 b75f7132e2f17988eb213991d22a03fcb965165c5919510087d694c86d21594d. Размер release EXE 55 379 088 байт. Guest inventory и финальные postconditions фиксируют тот же hash. Таким образом, прежняя C1-проверка payload/исключения CRT и suites применима без новой сборки.

Пакет: docs/workflow/evidence/TASK-WINDOWS-LOCAL-01-sandbox; оригинал: C:/Users/user/AppData/Local/Temp/edr-windows-build/sandbox-20261027-183939. Все 85 скопированных файлов побайтно связаны с оригиналами через независимо пересчитанные SHA-256; несовпадений нет. Все 18 записей финального evidence-hashes.json совпали. Ledger не объявляется исчерпывающим списком 85 файлов. Backup.zip дополнительно имеет ожидаемый SHA-256 a4cd335cc6c16cda0eb1002b718d24dd8816e4b0d32383bff14b55ff2c4e9e15; повторная полная ревизия его внутренней структуры не проводилась.

## G01: чистая установка и smoke — PASS (критерии 1/7)

Осмотрены evidence.wsb, manifest.json, host-launch.json, input/guest.ps1, output/guest-inventory.json, wsl-status.json и сырой wsl-stderr.bin, command-04-offline-prerequisite-install.ps1, production-install-result.json и окончание production-install.log.

Sandbox запущен 15:40:16Z; маппинги ограничены TEMP input (readonly) и output (writable). Реальный guest — Windows 11 Enterprise x64 10.0.26100, WDAGUtilityAccount. В начальной инвентаризации Python/Node/npm/PostgreSQL/Docker не найдены ни как команды, ни в проверенных типовых каталогах/installed apps. Наличие системного wsl.exe не равно работающему WSL: --status exit 50, distributions пуст, UTF-16 stderr прямо сообщает, что WSL не установлен. Python/PostgreSQL для продукта доставлены самим EDR. Копия bundled Python для тестового driver создавалась уже после успешной установки/запуска EDR и не являлась prerequisite установки.

После отдельно установленного согласованного Microsoft CRT production installer выполнился с exit 0, CWD C:/EDRInput, target C:/EDRTest/application; production-install.log подтверждает установку файлов/ярлыков и Installation process succeeded. Основная установка выполнялась /VERYSILENT, что не выдаётся за ручное прохождение мастера.

Проверены lifecycle.py, command-07-lifecycle.ps1, lifecycle-summary.json, полный output/lifecycle/results.json, lifecycle-driver-result.json, пустой lifecycle.stderr, окончание update.log, command-08-final-postconditions.ps1 и его done.json, compact-evidence.py, final-postconditions-compact.json. Driver завершился exit 0 в 15:58:24Z; CWD C:/EDRTest/application, фактические вложенные команды с CWD C:/EDROutput/lifecycle записаны в results.json. Harness действительно сравнивает API-ответ и PDF после restart, restore в новый каталог и same-version update; это не только текстовые отметки успеха. Файл синтетический, 43 байта, SHA-256 1412a4820f8723821848d52e799c5d78fb344afdfc3b661692f9b926b3901b3f. Busy/duplicate backup и nonempty restore ожидаемо отвергнуты exit 1 с осмысленными сообщениями. Успешные backup/restore/stop, update и uninstaller — exit 0. После удаления сохранены исходные runtime pointer/revision e4b8c2d16a70, PG_VERSION 18 и вложения; установленный Python и ярлык отсутствуют, listeners пусты.

Oversized final-postconditions.json не загружался. Компактный результат оценивается как производный артефакт: прочитан точный преобразователь, удаляющий PowerShell-метаданные и извлекающий value, а также команда получения исходных postconditions и успешный done marker. Ключевые postconditions дополнительно согласуются с lifecycle assertions и результатами; это не новый прогон.

Прежние C1-доказательства финального backend 3803 passed/1 warning, native 32 tests, frontend typecheck/build и production compile переиспользованы при неизменной привязке исходников. Новое clean Windows evidence закрывает недостающую часть критерия 7.

## G02: ярлык/UI и genuine missing-CRT flow — PASS (критерии 2/8)

Начальная инвентаризация показывает настоящее отсутствие всех трёх DLL: msvcp140.dll, vcruntime140.dll, vcruntime140_1.dll; meetsCrt=false. input/guest.ps1 и stage.json связывают запуск именно с production.exe, без /EDRTestMissingCRT. Ветвь synthetic-smoke-id предусмотрена harness, но не использовалась.

Прочитаны prerequisite-installer.log и prerequisite-exit.json: non-silent запуск /LANG=en /LOG, явное русское сообщение о Microsoft Visual C++ x64 >=14.44, User chose OK в 18:41:38 local, официальный learn.microsoft.com URL, InitializeSetup returned False, exit 1. Сам лог не доказывает видимость браузера. Недостающий факт покрыт прямым наблюдением пользователя, переданным координатором и сохранённым в user-observation.txt: «Да, страница Microsoft открылась. И я ее сам закрыл». Это пользовательское наблюдение, не screenshot ревьюера/исполнителя.

Guest online download завершился Unable to connect to the remote server; ошибка сохранена и не объявляется успешной загрузкой. host-crt-download.json и guest crt-download-signature.json фиксируют официальный aka.ms permalink, redirect download.visualstudio.microsoft.com, Valid Microsoft Authenticode, одинаковый SHA-256 843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c и версию 14.51.36247.0. command-04 проверяет подпись и hash перед запуском guest-only установки; crt-install-result.json/лог дают exit 0, crt-after.json — три DLL нужной версии. Это внешний тестовый prerequisite, не часть EDR-дистрибутива. Прежнее отсутствие CRT в production payload переиспользуется из C1 при идентичном EXE.

installed-shortcut.json, shortcut-stage.json и команда исполнения подтверждают вызов реального установленного Start Menu EDR.lnk через Start-Process в 15:54:21Z. Target — системный x64 PowerShell с launcher.ps1 start. shortcut-browser-process-evidence.json в 15:54:30Z показывает health=ok, окно Edge с заголовком EDR и только loopback 127.0.0.1:18765/55432. Дополнительная проверка всех listeners PID API/PG в lifecycle/results.json также показывает только 127.0.0.1, без LAN listeners.

Прямой пользовательский ответ о видимом интерфейсе передан координатором; исходная формулировка усечена до «Да, интерфейс EDR виде», в evidence восстановлена как «виде[н]». Принимается именно подтверждение пользователя в контексте предложенного варианта, а не выдуманное полное цитирование или агентское визуальное наблюдение. uiObserved=false в stage означает отсутствие агентского наблюдения на стадии запуска; последующее пользовательское подтверждение этому не противоречит.

Отдельно прочитаны cdp-provenance.json и cdp-react-dom.json и визуально осмотрен cdp-react.png: реально отрисован реестр, навигация, фильтры, кнопка добавления, сообщение об отсутствии документов. DOM имеет rootChildren=2 и URL http://127.0.0.1:18765/. Это другой инструментированный Edge с CDPProfile, запущенный позже; изображение НЕ является скриншотом исходного окна ярлыка. Два доказательства дополняют друг друга, их provenance не смешивается.

## Платформенные границы и связь с C1

Фактически проверен один чистый Windows 11 build 26100; Windows 10 и другие builds в этом дополнении остаются NOT_RUN. Frozen критерий 1 требует установку «на чистой поддерживаемой Windows x64 машине», а критерий 7 требует явно пометить неподтверждённые платформенные проверки. Раздел ресурсов называет Windows 10/11 x64, но не задаёт обязательные отдельные прогоны каждой версии/сборки. Windows 11 удовлетворяет требуемой чистой поддерживаемой машине; добавлять матрицу обеих ОС как новый gate нельзя. PASS не означает проверку совместимости Windows 10 и не является waiver такого прогона.

Синтетические операции с записью/PDF выполнены через API/CLI; ручное создание/редактирование записи через UI не проверено. Наблюдение пользователя подтверждает исходное окно, а отдельный CDP — отрисовку React. Интерактивный CRT flow проверен до provisioning; успешная guest online загрузка не доказана и не является frozen критерием. Прогон обновления — обычное same-version обновление, не переход между разными выпусками. Injected migration failure остаётся ранее проверенным host-native доказательством, не новым Sandbox тестом.

Критерии 3–6 сохраняют ровно прежний C1 PASS и его пределы. R01 MINOR про orphan PostgreSQL после аварии супервизора не исправлялся и не закрывается этим обычным lifecycle. Остальные ограничения из C1 (включая unsigned installer и ограничения путей) также не меняются.

Итоговая матрица: 1 PASS новым clean evidence; 2 PASS новым ярлыком/наблюдением/loopback; 3–6 PASS переиспользованы из C1; 7 PASS прежние suites плюс новый clean smoke; 8 PASS genuine prerequisite flow плюс прежняя проверка отсутствия CRT в неизменном EXE. G01/G02 больше не блокируют TASK.

Счётчики сохраняются: полное ревью C1 остаётся 1 из 2, failed reviews 0, A1/C1; настоящее дополнение — отдельный экспертный вызов, а не дополнительное полное ревью и не C2. Исторический расход не обнуляется. Фактические native usage этого dispatch фиксирует координатор; чисел токенов/стоимости ревьюер не выдумывает. Отказа провайдера в ходе этой экспертизы не наблюдалось.

Ревьюер создал только этот TEMP-отчёт; repo/workflow/product файлы не записывал, никаких app/OS inputs, исправлений, сборок, commit/push/merge/deployment не выполнял. Следующее действие координатора — записать совокупный verdict и сохранить все прежние ограничения и историю.
