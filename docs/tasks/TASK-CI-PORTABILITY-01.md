# TASK-CI-PORTABILITY-01 — переносимые пути import tests

Статус: A1/C1 LOCAL PASS; commit/push и hosted CI delivery pending. Риск R1: один test module,
существующий pathlib pattern; поведение приложения и БД не меняются.
Baseline/main: `9792688d3230c101323106517c824ea08657cb12`.

## Разрешение и точный scope

Пользователь ответил «Да, сделай минимальный патч» на предложение отдельно
исправить tests/test_transaction.py, закоммитить/push и проверить CI. Одобренный
TEMP patch `EDR-ci-portable-import-tests.patch`, SHA256
`930b348118cb0ab5071ed3b890cc9ff354649c460da10bdd6c9d12b4819e7a0e`:
добавить `from pathlib import Path` и заменить ровно два `subprocess.run(cwd=...)`
с локальной WSL-строки на `Path(__file__).resolve().parents[1]`.

Единственный разрешённый исполнителю файл — `tests/test_transaction.py`.
Workflow records пишет coordinator. Не менять app, migrations, dependencies,
CI configuration, другие тесты/fixtures/assertions. Не добавлять skip/xfail.
Сырые Sandbox artifacts и прочие локальные изменения сохраняются вне commit.

Причина: GitHub CI40543432652 на baseline:3798 passed/5 failed/1warning,
все5 failures в TestNoImportCycle — FileNotFoundError локального cwd.
Ошибки PostgreSQL constraint в negative cases не являются причиной провала.
Исходный CI failure и прежние review/counters GitHub/Windows сохраняются.
Это новый явно разрешённый test-only scope, не повторное C2 прежнего TASK,
которому было запрещено менять tests.

## Замороженный локальный чек-лист

| ID | Наблюдаемое условие | Доказательство |
| --- | --- | --- |
| AC1 | Только импорт Path и2 cwd заменены; обе точки берут реальный checkout root от __file__ | Точный diff против baseline и approved TEMP patch |
| AC2 | Пять существующих import tests проходят; свежие интерпретаторы/assertions сохранены | WSL Ubuntu, `.venv/bin/python -m pytest -q tests/test_transaction.py::TestNoImportCycle`, exit0/5passed; PostgreSQL18 online |
| AC3 | Остальные tracked source/deps/CI/tests неизменны; diff чистый | Git diff и git diff --check, exact code allowlist |

Реализация — один Orca Codex Luna/medium; независимое локальное review — отдельный
Sol/medium. A1/C1 fullreview1/2 reserved, failed0, diagnostics0; C2 только по
реальному FAIL и в рамках review-policy. Никакого повторного full suite локально.
Исполнитель даёт evidence, не PASS. После local routed PASS разрешён commit/push;
конечная delivery-проверка — новый GitHub CI на точном delivery HEAD. Успех CI
не объявляется до его actual conclusion. Usage actual, без caps/reset.

Дополнительное прямое поручение пользователя — сделать этот репозиторий public.
Coordinator выполняет отдельный read-only history audit перед visibility switch;
это не расширяет test-code allowlist и не разрешает переписывать Git history.

## Реальная локальная подача C1

Writer task_fbe548560df4/ctx_889fd51d82c9, Luna/medium, succeeded
msg_0f01fa3c4ecc. В архивном transcript непосредственно прочитаны результаты:
`pg_isready`: `/var/run/postgresql:5432 - accepting connections`;
`.venv/bin/python -m pytest -q tests/test_transaction.py::TestNoImportCycle`:
`..... [100%]` и `5 passed in 6.67s`, exit0 по отчёту. Обе команды через WSL Ubuntu
из `/mnt/d/Antigravity/EquipmentDocumentationRegistry`. `git diff --check` exit0.
Diff содержит ровно3 additions/2 deletions в единственном code file; coordinator
docs и untracked raw package сохранены. Worker released, transcript captured,
delivery_f8718e1c7f2b ACKed. Это evidence, не routed PASS.

## Независимое локальное решение

Sol/medium task_18c2fae2f0f2/ctx_868bb502c577 дал [LOCAL PASS](../workflow/reviews/TASK-CI-PORTABILITY-01-C1.md)
по AC1–3, msg_f2a8df78ea58; review1/2, failed0. Повторных тестов не потребовалось.
Writer346,586 +review300,555 =647,141input/2calls, cached включён; coordinator
отдельно. Source/header assertions сохранены, code diff3additions/2deletions.
Новый CI status/HEAD фиксируется в локальном
`%TEMP%/EDR-github-publication-result-20261027.json` и GitHub Actions.
Прежний CI40543432652 failure не перезапускается и не скрывается.

Public disclosure audit — отдельная операция:48commits/704blobs/7,977,814bytes,
реальных секретов/данных не обнаружено. По прямому поручению visibility изменена
на public через gh repo edit и подтверждена двумя API reads; история не переписывалась.
