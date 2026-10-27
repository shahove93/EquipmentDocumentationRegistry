# TASK-GITHUB-PRESENTATION-01 — repository presentation and checks

## Authorization and scope

User instruction on 2026-10-27: “Давай, так и сделаем”, approving the proposed GitHub presentation pass: a project README, contribution instructions, issue/PR templates, and CI. Work is limited to local repository files on `main`; no product behavior changes, release/tag, GitHub settings, visibility change, API deployment, commit, or push.

## Target files

- `README.md`
- `CONTRIBUTING.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/ci.yml`
- Documentation status corrections in `docs/workflow/STATE.md` and `docs/workflow/FINAL-REPORT.md` are coordinator-owned and will be handled after the worker settles.

## Change

Present Equipment Documentation Registry as a local-only application for cataloging equipment/material documentation. Explain actual capabilities and boundaries, point to existing project docs, and document setup/checks from AGENTS.md. Add low-maintenance GitHub issue templates and CI for the existing backend/frontend checks only if the workflow can run safely and accurately in GitHub Actions. Do not claim production deployment, authentication, or document-to-batch linkage.

## Constraints

- Preserve unrelated changes and current product code.
- Never include `.env`, `storage/`, `.venv/`, dependency directories, evidence dumps, or private workflow records in the public-facing README/templates.
- Do not introduce credentials, publish data, change repository visibility/settings, create a release/tag, commit, or push.
- Use current supported GitHub Actions versions based on official action documentation; grant minimum workflow permissions.
- Do not state checks pass unless the worker runs them and records actual results. Avoid duplicate full-suite runs when current final-stage evidence is reusable; validate workflow syntax and any newly introduced CI-specific assumptions.

## Acceptance checklist

1. README is clear in Russian, concise enough for GitHub, links to useful architecture/status docs, and accurately describes MVP+Batch, local-only/no-auth limits, WSL/PostgreSQL setup, and existing checks.
2. Contribution guide commands match project instructions and explain the required local environment.
3. Issue and PR forms are useful and contain no secret/data submission prompts.
4. CI workflow is syntactically valid, least-privilege, and uses the actual test/typecheck/build commands and database setup required by this repo; no deploy job.
5. No product code, dependency, migration, runtime data, or unrelated workflow/evidence edits.
6. Report changed files, CI validation evidence, and any checks not run.

## Route and ownership

- Risk class: R1 (new CI configuration plus documentation templates).
- Executor: one Orca Codex worker; reviewer: separate Orca Codex worker after executor settles.
- Workspace: current repository `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`.
- Push/merge/deploy are outside this authorization.

## C1 review outcome and C2 correction scope

- C1 implementation: succeeded, Dispatch `ctx_66aa4def7c13`, model `gpt-6-luna/medium`.
- C1 independent review: FAIL, Dispatch `ctx_4009fddd1ba6`, model `gpt-6.1-sol/medium`.
- MAJOR GP-001 (criterion 4): CI PostgreSQL service starts empty and pytest runs without applying Alembic migrations, while `tests/test_database.py` requires existing public tables.
- MAJOR GP-002 (criteria 1/2): local test database instructions create `equipment_docs_test` but migrate only `equipment_docs`; tests that use the migrated default database therefore encounter the same missing-table assertion. Other fixtures connect to the `edr` role and some test modules use its `postgres` database directly.
- Review reproduced YAML parsing, README links, workflow structure and `git diff --check`; full tests and a GitHub Actions run remain unverified.

C2 is limited to correcting the PostgreSQL test setup in README, CONTRIBUTING and CI: apply Alembic migrations to the explicitly separate disposable test database before pytest; ensure CI's temporary PostgreSQL role/database settings satisfy existing test DSNs; preserve the application database and all product code. Then run only scoped static/source checks and one independent C2 review. No third full review is authorized after a C2 FAIL.

## Final outcome

- C2 final independent review: PASS, no outstanding findings; [review record](../workflow/reviews/TASK-GITHUB-PRESENTATION-01-C2.md).
- Static validation passed. Full pytest, frontend commands, live migrations, and a real GitHub Actions run were not run; see review record for exact evidence and limits.
- Scope prepared locally only. GitHub About/topics/visibility/release settings, commit, push, merge and deployment have not been changed. Waiting for user review of the prepared result before external publication/settings.

## Дополнительное разрешение на публикацию — 2026-10-27

После review пользователь прямым «Делай» разрешил согласованный план33 файлов/
3коммитов и push в origin/main. Шесть файлов presentation/CI сохранены в commit
`61bbdc3be7ad49f58f6e773c5c5d8c7163af0352`; исходная приёмка C2 и её пределы
сохранены. Предыдущее ожидание user review относится к состоянию до этого решения.
Фактический Git/CI статус: `%TEMP%/EDR-github-publication-result-20261027.json`
и GitHub Actions. Настройки/visibility/release/deployment не изменяются.
