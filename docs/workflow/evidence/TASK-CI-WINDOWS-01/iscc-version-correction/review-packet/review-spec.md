# Independent R2 review spec — CI-CLOUD-02 ISCC version-check correction

You are the independent Codex reviewer for the **single additionally approved**
full review of the CI-CLOUD-02 correction under TASK-CI-WINDOWS-01 / A1.
You are read-only: do not edit files, run shell edits, install/execute the
installer or app, or touch DB/VM/remote Git/network services. Inspect the actual
files/evidence and return one verdict.

Repository: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`,
HEAD `44d7b65bd387b3ab0b670efcb2686c05d11290ae`.

## Authority and accounting

- Approval: `docs/workflow/APPROVALS.md`
  §`CI_CLOUD_02_ISCC_VERSION_CHECK_CORRECTION_AUTHORIZED_20261104`
  (user: «разрешаю»). This is an extension of the current logical TASK/A1,
  adding **one** full review (4th total for A1); **not A2**.
- Preserved: prior 3 full reviews (C1 FAIL, C2 PASS, URL-correction PASS),
  failed reviews 1, C3 diagnoses, CI Codex calls 3/4, and the reserved Windows
  calls. This review is the 4th (final) CI Codex call.
- **If this review FAILs, stop**: no further fix, review, commit, push or run
  under this approval.
- On PASS only: one scoped commit, one non-force push, exactly one
  `workflow_dispatch` run on the published headSha. No rerun on cloud failure.
- Cloud smoke success is not full UAC/lifecycle acceptance.

## Trigger and correction

Cloud run `41884655362` failed after the retained
`VersionInfo.FileVersion` check returned `0.0.0.0`. The source-backed diagnosis
(`docs/workflow/evidence/TASK-CI-WINDOWS-01/CI-CLOUD-02-diagnosis.md`) proved
the official 6.7.3 `ISCC.versionandicon.res` has FileVersion/ProductVersion
`0.0.0.0` by design; the real exact signal is the non-quiet build-log line
`Compiler engine version: Inno Setup 6.7.3`.

Correction under review:
- `.github/workflows/windows-installer.yml`:
  - removed only the invalid `VersionInfo.FileVersion` check; kept ISCC
    existence, official immutable URL, `INNO_SETUP_SHA256`
    `9C73C3…B732`, and Valid Authenticode `CN=Pyrsys B.V.` checks;
  - after a successful `build.ps1`/`Tee-Object` (and after the try/catch
    rethrow), added a fresh-log existence guard and
    `Select-String -LiteralPath $buildLog -Pattern '^Compiler engine version: Inno Setup 6\.7\.3$' -Quiet`, throwing if false.
- `docs/installation/windows.md`: only CI item 3 updated to the build-log
  compiler-engine version check.
- Frozen checklist:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/frozen-checklist.md`.
- Implementer evidence:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/implementer/`.
- Scoped diffs:
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/iscc-version-correction/review-packet/`
  (`worker.diff`, `workflow.diff`, `docs.diff`).

## Checklist

Verify by reading the actual files and evidence:

1. **Scope (C1):** only the workflow and the targeted docs CI item changed.
   Confirm `build.ps1`, `edr.iss`, `provision.ps1`, `ci-installer.ps1/.py`,
   `app/`, `frontend/`, lockfiles, tests and product dependencies are unchanged
   from baseline. Report any unexpected changed file.
2. **FileVersion check (C2):** the invalid `VersionInfo.FileVersion` check and
   its old throw/output are gone; ISCC existence check remains.
3. **Acquisition checks (C3):** official URL, SHA-256 pin and Authenticode
   `Valid`/`CN=Pyrsys B.V.` checks are unchanged and still before
   `Start-Process`.
4. **Exact version check (C4):** after successful build, the fresh `build.log`
   must contain exactly `Compiler engine version: Inno Setup 6.7.3`; the regex
   matches only 6.7.3, not 6.7.4/missing; failure throws.
5. **Control flow (C5/C6):** the check is after the successful try/catch; a
   failed build rethrows before it; the `$logDir` freshness guard remains, so a
   stale log cannot satisfy it; no `/Q`/`/Qp`; native exit codes are not
   swallowed or replaced.
6. **Evidence (C7):** positive real 6.7.3 log → True; synthetic 6.7.4 →
   False; missing → False; failed-build control exits non-zero with version
   markers unreached; stale-log control exits non-zero with the guard. Check
   the actual logs/scripts.
7. **Static (C8):** YAML parse/18 assertions and actionlint exit 0; scoped
   `git diff --check` 0; docs note accurately describes the build-log check.
8. **No weakening (C9):** no version/toolchain/prerequisite/runner-guard
   changes; no host install; no new secret.
9. **Accounting:** confirm this is the 4th A1 full review, not A2 or a counter
   reset; prior 3 reviews/C3 are preserved.

C4–C9 cloud execution remains NOT_RUN; static correctness and control-flow
evidence are what can be accepted locally.

## Verdict

- **PASS** — correction is correct, scoped and fail-closed; coordinator may
  proceed to the approved commit/push/run. List MINOR/NIT only.
- **FAIL** — any BLOCKER/MAJOR. List stable finding IDs, criterion, location,
  observed result, reproduction/evidence, expectation, severity. No further
  fix/review/run follows.

Do not write files. End after the verdict with Orca `worker_done`
(outcome succeeded for PASS, failed for FAIL), a three-sentence summary,
findings and evidence paths.
