# TASK-CI-WINDOWS-01 — CI-CLOUD-01 correction, additional A1 review record

- Reviewer: Codex `gpt-6.1-sol`, effort `high`, read-only.
- Orca Task `task_a94305c36847`, Dispatch `ctx_cb17f595c1f0`,
  Run `run_b556ddaf13c3`, terminal `term_f6fa6b80-869f-4ec6-a530-6667ae2722ee`.
- Worker result: `worker_done` msg_4eb5ce74dddc, outcome `succeeded` (verdict PASS).
- Revision reviewed: `main` HEAD
  `11d66b1c8a86dd59b7b1d7e693f8c27f43796196` plus the scoped working-tree
  correction.
- Corrected files:
  - `.github/workflows/windows-installer.yml`
    `DA22EDF5E8A00E291667FA7DC38C8ADEAF40B96CC9761CDB2B2424844D8FEBCB`
  - `docs/installation/windows.md`
    `CFC8BC96685FE156E228F7B6D316E261A649D2B6190F187CEF6EFC0B0EAE6D41`
- Packet: `docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/review-packet/`.

## Verdict

**PASS.** Only the workflow and CI item 3 were added to baseline dirty status; no
unexpected product-file changes. C1–C9 and the accounting/docs checks pass:

- official immutable `is-6_7_3` URL and SHA-256 `9C73C3…B732` set;
- SHA-256 mismatch and invalid/wrong-signer Authenticode throw before
  `Start-Process`, with no bypass;
- `INNO_VERSION` and the post-install `ISCC.exe` FileVersion check remain
  `6.7.3`;
- runner/TLS/permissions/dispatch/upload guards intact;
- YAML and actionlint logs exit 0; no-execution proof correct=0 / wrong-hash=1;
- eight protected files unchanged; smoke/test/workflow dirt preserved.

The only finding is **CI-URL-N1 (NIT)** on C9: the standalone
`review-packet/docs.diff` export contains mojibake Cyrillic when read as UTF-8,
while the actual `windows.md` and canonical `worker.diff` are correct. No
correction or re-review is required; future standalone diff exports should
preserve UTF-8.

## Accounting

- This consumes the **one additional A1 full-review slot** authorized by
  `APPROVALS.md` §`CI_CLOUD_01_URL_CORRECTION_AND_RETRY_AUTHORIZED_20261104`.
- Preserved: prior C1 FAIL / C2 PASS, previous full reviews 2, failed-review
  count 1, C3 diagnosis, no A2/counter reset.
- Full reviews for this logical TASK now: **3** total (2 original + this
  explicitly authorized additional one); CI Codex calls **3/4**; failed
  reviews **1**.
- Allowed next actions only: one scoped commit, one non-force push, one
  `workflow_dispatch` run; no rerun on failure. Cloud/full
  Windows/UAC/lifecycle remain unverified; conditional runner-shell risk
  CI-C4-01 is unchanged.
