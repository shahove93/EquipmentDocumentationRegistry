# TASK-MVP-06 — Stage verification evidence

**Run:** `run_68046cea3eb4`  
**Task / dispatch:** `task_bfc414bad7a6` / `ctx_7ddb18624654`  
**Workspace:** `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`  
**Executor:** Codex `gpt-6-luna`, medium; dispatched as checks-only executor (accounting call 11; coordinator settles actual usage separately).

## Result

The required verification commands completed successfully. The tested delivery revision remained `06f58065022db9c58524909027ddc2d454f7071f`; no bounded backend/frontend source identity changed. This report records evidence only and does not accept the Stage.

| Checklist | Result | Evidence / observed result |
|---|---|---|
| ST-001 | PASS | Pre/post HEAD is the required revision on `main`; pre/post bounded manifest contains 190 files and reports zero changed or removed paths. Product diff snapshots are empty. The working tree is **not clean**: unrelated workflow changes and pre-existing MVP05 evidence remain; see `TASK-MVP-06-pre.json` and `TASK-MVP-06-post.json`. |
| ST-002 | PASS | Backend pytest exit 0: `3771 passed, 1 warning in 471.65s (0:07:51)`. Full stdout and stderr are retained. |
| ST-003 | PASS | Node `v24.22.0`; frontend typecheck exit 0; build exit 0 (`vite v8.3.4`, 63 modules transformed). Build output is the permitted ignored `frontend/dist/`. |
| ST-004 | PASS | `alembic current` exit 0 reports `e4b8c2d16a70 (head)`. Source provenance identifies migration `e4b8c2d16a70_add_ix_files_document_id_id.py` with revision `e4b8c2d16a70`; actual migration file count is 13, count command exit 0. No migration was run. |
| ST-005 | PASS | This report links the actual commands, exits, complete logs, source identities, scope, and preceding MVP05 A2/C1 PASS context recorded in the frozen task. Final artifact hashes are in `TASK-MVP-06-hashes.json`. |
| ST-006 | PENDING | Separate Codex stage-acceptance review is not part of this executor dispatch. Stage remains `NOT_ACCEPTED` pending review of VISION, ARCHITECTURE, ROADMAP, and these actual evidence artifacts; reuse the command logs rather than rerunning the full checks. |
| ST-007 | PENDING | Coordinator may create FINAL-REPORT only after a real stage PASS. This executor created no FINAL-REPORT and makes no PASS claim for the Stage. |

## Commands and logs

All commands were launched from Windows CWD `D:/Antigravity/EquipmentDocumentationRegistry`. Actual WSL CWD and UTC start/end timestamps are recorded in the corresponding `*.meta.json` files. stdout and stderr are kept separately, in full.

| Check | Exact command | Exit | Logs |
|---|---|---:|---|
| Backend suite | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/python -m pytest -q'` | 0 | `TASK-MVP-06-pytest.stdout.log`, `TASK-MVP-06-pytest.stderr.log` |
| Node version | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && node --version'` | 0 | `TASK-MVP-06-node.stdout.log`, `TASK-MVP-06-node.stderr.log` |
| Typecheck | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run typecheck'` | 0 | `TASK-MVP-06-typecheck.stdout.log`, `TASK-MVP-06-typecheck.stderr.log` |
| Build | `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run build'` | 0 | `TASK-MVP-06-build.stdout.log`, `TASK-MVP-06-build.stderr.log` |
| Alembic current | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && .venv/bin/alembic current'` | 0 | `TASK-MVP-06-alembic-current.stdout.log`, `TASK-MVP-06-alembic-current.stderr.log` |
| Migration count | `wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/d/Antigravity/EquipmentDocumentationRegistry && ls alembic/versions/*.py | wc -l'` | 0 | `TASK-MVP-06-migration-count.stdout.log`, `TASK-MVP-06-migration-count.stderr.log` |

`alembic current` stderr contains the actual Alembic INFO lines (`PostgresqlImpl` and transactional DDL); they are retained even though the Windows PowerShell host rendered stderr as a native-command diagnostic. The native WSL exit code was 0 and stdout reported the head shown above.

## Scope and identities

The before/after SHA256 manifest covers `app/`, `tests/`, `alembic/versions/`, `frontend/src/`, and the frontend package manifests plus `requirements.txt` and `alembic.ini`; it excludes this report and all evidence artifacts. Exact manifests, Git status snapshots, and bounded product diffs are `TASK-MVP-06-pre.json`, `TASK-MVP-06-post.json`, `TASK-MVP-06-product-diff-pre.txt`, and `TASK-MVP-06-product-diff-post.txt`. The snapshots preserve unrelated workflow modifications and existing untracked evidence rather than describing the tree as clean. No product source, tests, API, schema, dependency, environment, storage, or migration was changed by this dispatch. No commit, push, merge, or deployment was performed.

The frozen predecessor is MVP05 A2/C1 PASS at the unpushed revision above. MVP05 A1 failures and all prior usage remain historical and were not rewritten. This report records only checks performed by this dispatch; stage review and final reporting remain coordinator-owned.
