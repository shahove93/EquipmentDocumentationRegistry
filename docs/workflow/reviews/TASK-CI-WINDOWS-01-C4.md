# TASK-CI-WINDOWS-01 — CI-CLOUD-02 ISCC version correction, A1 review 4

- Reviewer: Codex `gpt-6.1-sol`, effort `high`, read-only.
- Orca Task `task_61c0c61621c1`, Dispatch `ctx_f4955bab43cc`,
  Run `run_b556ddaf13c3`, terminal `term_364e2fc1-2efe-4d1e-887e-4cb081a615e9`.
- Worker result: `worker_done` msg_888910aa38e0, outcome `succeeded` (PASS).
- Revision: `main` HEAD
  `44d7b65bd387b3ab0b670efcb2686c05d11290ae` plus the scoped working-tree
  correction.
- Corrected files:
  - `.github/workflows/windows-installer.yml`
    `34C3BECBCD38768DA1F3A7517F82F0A5E128EF7738DCF36DAC74FBAE71418252`
  - `docs/installation/windows.md`
    `36248CC68C96C9EAC58EC67D7563BFD0889F2D34D61DAED57875B624D7FB41CD`
- Packet: `docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/review-packet/`.

## Verdict

**PASS.** C1–C10 and accounting pass locally:

- only the workflow and the installation guide CI item 3 changed; protected
  hashes match and pre-existing smoke/test dirt matches the original baseline;
- invalid `VersionInfo.FileVersion` logic removed; ISCC existence and unchanged
  official URL / SHA-256 / Valid Authenticode checks remain before
  `Start-Process`;
- the exact anchored compiler-version check follows successful
  build/`Tee-Object` and catch rethrow, with missing-log throw and retained
  freshness guards;
- `build.ps1` retains explicit native-failure throws; no quiet flags; no
  guard/toolchain/secret changes;
- evidence: `01-static.txt` 18/18, `02-actionlint.txt` 0, `03-version-signal`
  real 6.7.3 True / synthetic 6.7.4 and missing False,
  `04-failed-build-control` and `05-stale-log-control` exit 1 with later markers
  unreached, `06-diff-check-scoped.txt` 0, `08-hashes.txt`, `worker.diff`;
- real banner source: `docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01/build.log:96`.

Sole finding **CI-ISCC-N1 (NIT, C10 evidence readability)**: standalone
`review-packet/docs.diff`, `worker.diff` and `implementer/worker.diff` show
mojibake Cyrillic when read as UTF-8, while the actual guide and live Git diff
are correct. No correction or re-review required; future exports should preserve
UTF-8.

## Accounting

- Consumes **A1 full review 4** and the final CI Codex call **4/4**.
- Preserved: prior C1 FAIL, C2 PASS, URL-correction PASS, failed-review count 1,
  C3 diagnoses, reserved Windows calls; no A2 or counter reset.
- Allowed next actions only: one scoped commit, one non-force push, exactly one
  `workflow_dispatch` on the published headSha; stop on cloud failure without
  rerun. Cloud C4–C9 remain NOT_RUN; full UAC/lifecycle acceptance outstanding.
- Reviewer made no file edits and ran no installer/app/DB/VM/remote operation.
