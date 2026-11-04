# TASK-CI-WINDOWS-01 / A1 — frozen checklist for ISCC version-check correction

Frozen 2026-11-04 before implementer dispatch, under
`CI_CLOUD_02_ISCC_VERSION_CHECK_CORRECTION_AUTHORIZED_20261104` (user:
«разрешаю»). Bounded A1 correction, not A2.

## Accounting (preserved)

- Prior full reviews: **3** (C1 FAIL, C2 PASS, URL-correction PASS); failed
  reviews 1; CI Codex calls **3/4**; C3 diagnoses preserved; additional A1
  review slot for the URL correction consumed.
- This approval adds **one** further full review (4th total for A1). If it
  FAILs, stop: no further fix/review.
- After PASS only: one scoped commit, one non-force push, exactly one
  `workflow_dispatch` run on the published headSha. No rerun.
- Reserved Windows calls untouched. Full Windows/UAC/lifecycle PASS is not
  granted by the smoke run.

## Checklist

| ID | Criterion | Proof |
|----|-----------|-------|
| C1 | Only `.github/workflows/windows-installer.yml` and (optionally) a targeted CI note in `docs/installation/windows.md` change. Other product/prerequisite/script/lock files stay byte-identical. | `git diff --name-status` vs baseline; hash comparison. |
| C2 | The invalid `VersionInfo.FileVersion` check is removed. The ISCC existence check remains. | File content + static assertions. |
| C3 | Official immutable URL, `INNO_SETUP_SHA256` `9C73C3…B732`, and Valid Authenticode signer `CN=Pyrsys B.V.` checks remain unchanged. | File content + diff. |
| C4 | After a **successful** `build.ps1`, the step verifies the fresh `build.log` contains exactly `Compiler engine version: Inno Setup 6.7.3`, using a regex that matches only that line/version; missing/wrong/6.7.4 fails closed. | File content + positive/negative logs. |
| C5 | Version check runs only after successful build; a failed build rethrows before it. No stale log can satisfy it (`$logDir` freshness check retained; log created in the same step). | File content + failed-build control evidence. |
| C6 | Native exit codes remain reliable: `build.ps1`/ISCC non-zero fails the step; no `/Q`/`/Qp`; no exit-code swallowing; the new check does not replace native failure handling. | File content + control evidence. |
| C7 | Positive/negative proof: existing real 6.7.3 log → True; synthetic 6.7.4 → False; missing line → False; failed build → version check not reached and step fails. | Reproducible PowerShell/Python logs with CWD/exit. |
| C8 | YAML parses, actionlint exits 0, scoped `git diff --check` exits 0; optional doc note accurately says compiler-engine version is verified from the build log (not FileVersion). | Check logs. |
| C9 | No version/toolchain/prerequisites/runner-guard changes; no host install; no new secret. | Diff inspection. |
| C10 | Evidence complete: report, commands/CWD/exit codes, scoped diff, status, hashes. No commit/push/run by implementer. | Evidence directory. |
