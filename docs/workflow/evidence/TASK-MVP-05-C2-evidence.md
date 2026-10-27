# TASK-MVP-05 C2 — implementation and evidence handoff

Status: C2 implementation/evidence complete; **not acceptance**. C1 FAIL and its
review, logs and receipts remain unchanged. Run `run_68046cea3eb4`, Task
`task_be6fd5441e23`, Dispatch `ctx_14c1888cf95b`; workspace
`D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`, baseline
`318e6336737ee635abf593c2643f26daba273f86`.

## C1 findings and frozen AC

| Finding / AC | C2 result and evidence |
| --- | --- |
| F-01; AC-003/004/006 | Real browser actions against the in-memory MOCK completed list → detail → create → GET detail → edit PATCH → clear PATCH with `manufacture_date: null` → explicit GET detail after selecting another row. New record `32` was created with future date `2027-02-03` and quantity string `12345678901234567890.001`; create returned 201, subsequent GET and both PATCH/GET responses returned 200 with bodies. See `TASK-MVP-05-C2-browser-crud-sequence.json`, `TASK-MVP-05-C2-browser-api-log-complete.json`, and the `browser-*-ui/action.json` files. |
| F-02; AC-005 | `BatchForm` submission generation/mounted guards prevent callbacks after unmount or field changes. `BatchesPage` now captures a create-form selection epoch and rejects an obsolete `onSaved` after table selection changes. Evidence: delayed PATCH A→B left B selected with no old form; delayed POST followed by B selection left B selected and the create form open; delayed PATCH plus a subsequent quantity edit left the current form and `88.25` intact. The fixture delays PATCH for ID 1 by 2 seconds; the POST test held the actual MOCK response promise for 2.5 seconds in the browser before returning it to the app. See `TASK-MVP-05-C2-browser-stale-patch-result.json`, `TASK-MVP-05-C2-browser-stale-post-result.json`, `TASK-MVP-05-C2-browser-stale-formchange-result.json`, and corresponding request logs. |
| F-03; AC-001/002/003/005 | Existing Orca browser page `a5a98608-453d-4c3c-b8be-5effd41ecae6` loaded `http://localhost:5175/batches`; a real reload reported `type=reload`, status 200, `text/html`. `curl.exe` through the temporary Vite proxy returned HTML 200 `text/html`; JSON list returned 200 `application/json`. Browser requests captured 404 detail, 422 POST and PATCH bodies, and a real fetch refusal to `127.0.0.1:8999`. A one-shot browser fetch fault showed the list error and Retry control; retry made a real list request and rendered page 2 with the end control disabled. See `TASK-MVP-05-C2-browser-reload-result.json`, `TASK-MVP-05-C2-http-html-check.log`, `TASK-MVP-05-C2-http-api-check.log`, `TASK-MVP-05-C2-browser-edge-case-results.json`, `TASK-MVP-05-C2-browser-retry-*.json`, `TASK-MVP-05-C2-browser-final-snapshot.json`, and `TASK-MVP-05-C2-browser.png`. The retry fault was injected at the browser fetch layer; no MOCK request was sent for that failed attempt. |
| F-04; AC-007 | This report and all logs/artifacts were written before the C2 hash manifest. `TASK-MVP-05-C2-hashes.json` is the final generated file and is not included in its own hash set; no hashed file was edited afterward. |

AC-001 direct navigation/refresh and HTML/API negotiation: above. AC-002 list,
detail, safe missing-record handling, pagination, retry and end-page state:
above. AC-003/004 create, separate edit and explicit nullable clear round-trip:
above. AC-005 exact Decimal string, future date, safe 404/422/network handling
and stale callback guards: above. AC-006 full UI/API sequence and visible controls:
browser action/UI files and screenshot. AC-007 final WSL checks and scope record:
below.

## Commands and environment

- Browser: Orca `snapshot`, `eval`, `goto`, `keypress` and `screenshot`, all on
  page `a5a98608-453d-4c3c-b8be-5effd41ecae6`; Orca receipts in the linked JSON
  artifacts report `ok: true` for completed actions.
- Temporary isolated MOCK: `wsl.exe -d Ubuntu -- bash -lc 'cd
  /mnt/d/Antigravity/EquipmentDocumentationRegistry && python3
  docs/workflow/evidence/TASK-MVP-05-C2-fixture-8001.py'`; foreground session
  `61739`, bound to 8001, in-memory only. Temporary Vite: `wsl.exe -d Ubuntu --
  bash -lc 'source /home/djeka/.nvm/nvm.sh; cd
  /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run dev --
  --config ../docs/workflow/evidence/TASK-MVP-05-C2-vite.config.ts'`;
  foreground session `55827`, port 5175. The repository Vite config was not
  changed for these isolated runs. The earlier collision attempt is preserved
  in `TASK-MVP-05-C2-browser-create-collision-attempt.json`; the in-memory
  fixture initially reused ID 3 and its GET returned seeded `PAGE-03`. The
  final isolated fixture starts at free ID 29. All API bodies/statuses are from
  the MOCK request recorder, never the product DB.
- `wsl.exe -d Ubuntu -- bash -lc 'source /home/djeka/.nvm/nvm.sh; cd
  /mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend && npm run
  typecheck'` — CWD `/mnt/d/Antigravity/EquipmentDocumentationRegistry/frontend`,
  Node `v24.22.0`, exit 0. Full stdout is in
  `TASK-MVP-05-C2-typecheck.log`.
- Same WSL CWD, `npm run build` — Node `v24.22.0`, exit 0; full stdout in
  `TASK-MVP-05-C2-build.log`.
- Windows CWD `D:\Antigravity\EquipmentDocumentationRegistry`,
  `curl.exe -sS -H "Accept: text/html" -D - -o NUL
  http://localhost:5175/batches` — exit 0, HTTP 200, `Content-Type: text/html`.
  `curl.exe -sS -H "Accept: application/json" -D - -o NUL
  "http://localhost:5175/batches?limit=26&offset=0"` — exit 0, HTTP 200,
  `application/json`. Command output is in the two `http-*-check.log` files.
- Windows CWD as above, `git diff --check` — exit 0. The scope log lists the
  frontend changes and confirms no status entries for backend/app, tests,
  Alembic, dependency manifests, `.env`, `.venv`, storage, `node_modules` or
  `dist`. The only new page logic in this continuation is the create-selection
  epoch guard in `frontend/src/pages/BatchesPage.tsx`; temporary fixture/proxy
  files are under `docs/workflow/evidence/`.

## Limits

The fixture is volatile memory and does not represent a real backend or DB
round-trip. No backend tests ran. C2 completion is not a routed PASS or stage
acceptance; the separate remaining Sol medium full review 2/2 is next. Existing
unrelated workflow-document edits and all C1 failures/receipts were preserved.
