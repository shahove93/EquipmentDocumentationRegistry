# TASK-WINDOWS-LOCAL-01 — дополнение C1: чистая Windows

Статус: G01/G02 PASS по [независимому дополнению](../reviews/TASK-WINDOWS-LOCAL-01-C1-supplement.md).
Совместно с историческим C1 это поддерживает приёмку TASK по критериям 1–8.

- Run `run_5a6ffc6d06c6`; executor `task_4c623f9127b1` / `ctx_996ca9959986`,
  requested/effective и native `gpt-6.1-sol/medium`.
- Matching `worker_done` `msg_ca96eaee959c`, outcome succeeded, 16:01:38Z.
  Delivery `delivery_73722f134f9b` обработан и ACKed. `worker-release` вернул
  retained/user_takeover/processAction none; пользовательский терминал сохранён.
- Baseline `1c362598e67f9a7645de2416e79c2bb8ca3f3dc4`, main. Код и production
  installer не менялись. SHA-256 EXE:
  `b75f7132e2f17988eb213991d22a03fcb965165c5919510087d694c86d21594d`.
- Сырые артефакты ниже сохраняются только в локальном рабочем каталоге и
  исключены из GitHub-публикации; ссылки доступны владельцу локального пакета:
  [отчёт исполнителя](TASK-WINDOWS-LOCAL-01-sandbox/evidence-report.md),
  [хеши](TASK-WINDOWS-LOCAL-01-sandbox/evidence-hashes.json),
  [lifecycle](TASK-WINDOWS-LOCAL-01-sandbox/lifecycle-summary.json),
  [финальные условия](TASK-WINDOWS-LOCAL-01-sandbox/output/final-postconditions-compact.json).

## Наблюдения и результаты

Чистая Windows Sandbox: Windows 11 Enterprise x64, build26100. До проверки
Python/Node/PostgreSQL/Docker не установлены; Windows wsl.exe — заглушка,
`--status` exit50, дистрибутивов нет. Три необходимые CRT DLL действительно
отсутствовали. Production installer показал prerequisite и отказал с exit1.
Пользователь подтвердил: «Да, страница Microsoft открылась. И я ее сам закрыл».
Это пользовательское наблюдение, а не screenshot агента.

Гостевой online download runtime завершился ошибкой соединения; исходная
ошибка сохранена. Официальный пакет Microsoft14.51.36247.0 загружен на host,
подпись Microsoft Valid и одинаковый SHA-256 проверены host/guest; пакет установлен
только в guest. Установщик EDR не содержит CRT. CRT install и production EDR
install завершились exit0. Настоящий установленный EDR.lnk вызван в15:54:21Z;
пользователь подтвердил видимый интерфейс EDR. Дополнительный CDP screenshot и
DOM относятся к отдельному инструментированному Edge, что явно отмечено в evidence.

Гостевой lifecycle driver завершился exit0: synthetic запись и PDF43 bytes,
перезапуск, backup, restore в пустой каталог, same-version update, обычное удаление.
PDF до/после совпадает:
`1412a4820f8723821848d52e799c5d78fb344afdfc3b661692f9b926b3901b3f`.
Busy/duplicate backup и nonempty restore безопасно отклонены. После удаления
исходные DB/вложения сохранены, приложение/ярлык удалены, listeners отсутствуют.

## Границы и приёмка

Windows10 и прочие builds не проверялись. Операции над synthetic данными выполнял
API/CLI; видимый React UI подтверждён отдельно. Host-native backend3803,
native32, frontend typecheck/build и injected failed-migration evidence уже
проверены в [C1 review](../reviews/TASK-WINDOWS-LOCAL-01-C1.md) и не повторялись.
R01 MINOR остаётся backlog; исправлений/новой кодовой подачи нет.

Скопирован ограниченный пакет evidence в соседний каталог. Исходный полный
TEMP-пакет, oversized102MB JSON и тестовые DB сохранены в
`%TEMP%/edr-windows-build/sandbox-20261027-183939`; компактный JSON получен из
исходного результата без повторного теста. Sandbox оставлен открытым; helper
завершён, EDR/PG остановлены. Реальные данные пользователя не использовались.

Независимый Astra/high `ctx_9237392c299b` проверил G01/G02 и неизменность12
исходников/EXE,85 скопированных файлов и18 ledger entries; несовпадений нет.
Matching worker_done `msg_5bba74f6e510`, outcome succeeded16:12:20Z. Полное C1
review не повторялось; full-review1/2 и failed0 сохранены. Новый экспертный вызов
учтён отдельно. Требования/архитектура не меняются.
No commit/push/merge/deployment.

Предыдущая строка описывает состояние на момент приёмки. После отдельного
user approval публикация исходников и итоговых записей выполняется по плану33
файлов; EXE и полный raw пакет остаются локальными. Текущий Git/CI результат
фиксируется в `%TEMP%/EDR-github-publication-result-20261027.json`.

Executor final native usage16:01:55.158Z: input5,110,646 (cached4,948,736 уже
включены), output27,365. Ранее settled14,190,357 +5,110,646 =19,301,003 input,
3 worker calls; coordinator conversation отдельно. Provider snapshot27%/66%,
нового refusal нет. [Учёт](TASK-WINDOWS-LOCAL-01-usage.json).
