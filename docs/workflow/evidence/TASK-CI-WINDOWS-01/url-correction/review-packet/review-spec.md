# Independent R2 review spec — CI-CLOUD-01 correction (additional A1 review)

You are the independent Codex reviewer for the **single additionally approved**
full review of the CI-CLOUD-01 correction under TASK-CI-WINDOWS-01 / A1.
You are read-only: do not edit files, do not run shell edits, do not install or
execute the installer/app, do not touch the working DB, VM, remote Git or
network services. Inspect the actual files/evidence and return one verdict.

Repository: `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`,
HEAD `11d66b1c8a86dd59b7b1d7e693f8c27f43796196`.

## Authority and accounting

- Approval: `docs/workflow/APPROVALS.md`
  §`CI_CLOUD_01_URL_CORRECTION_AND_RETRY_AUTHORIZED_20261104`
  (user: «Разрешаю»). This is an **extension of the current logical TASK/A1**,
  not a new approach A2.
- Preserved accounting: previous full reviews **2/2** (C1 FAIL, C2 PASS),
  failed reviews **1**, C3 diagnosis done. This review is the **one additional
  review slot** authorized. **If it FAILs, stop**: no further fix or review
  under this approval.
- On PASS only, the coordinator may make one scoped commit, one non-force push,
  and one `workflow_dispatch` cloud run. No rerun on cloud failure.

## Trigger

Cloud run `41881330228` failed at `Install Inno Setup 6.7.3` because
`https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe` returned HTTP 404.
C3 diagnosis: `docs/workflow/evidence/TASK-CI-WINDOWS-01/CI-CLOUD-01-diagnosis.md`;
verified evidence: `inno-6.7.3-verification.json`.

## Correction under review

- `.github/workflows/windows-installer.yml`:
  - `INNO_SETUP_URL` →
    `https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe`
  - new `INNO_SETUP_SHA256` =
    `9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`
  - before `Start-Process`: `Get-FileHash -Algorithm SHA256` must equal the pin
    (throw on mismatch), and `Get-AuthenticodeSignature` must be `Valid` with
    signer subject matching `CN=Pyrsys B.V.` (throw otherwise);
  - `INNO_VERSION` stays `6.7.3`; the post-install `ISCC.exe`
    `VersionInfo.FileVersion` `6.7.3` check stays.
- `docs/installation/windows.md`: only CI section item 3 updated (official URL,
  SHA-256, Authenticode).
- Frozen checklist: `docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/frozen-checklist.md`.
- Implementer evidence: `docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/implementer/`.
- Scoped diffs: `docs/workflow/evidence/TASK-CI-WINDOWS-01/url-correction/review-packet/`
  (`worker.diff`, `workflow.diff`, `docs.diff`).

## Review checklist

Verify by reading the actual files and evidence:

1. **Scope (C1):** only `.github/workflows/windows-installer.yml` and the
   targeted `docs/installation/windows.md` CI item changed. Confirm
   `build.ps1`, `edr.iss`, `provision.ps1`, `ci-installer.ps1/.py`, `app/`,
   `frontend/`, lockfiles, tests and product dependencies are unchanged from
   baseline. Report any unexpected changed file.
2. **URL/version (C2):** exact official immutable release URL; `INNO_VERSION`
   remains `6.7.3`.
3. **SHA-256 (C3):** pin is exact; verification occurs after download and
   before `Start-Process`; mismatch throws/fails closed.
4. **Authenticode (C4):** `Status -eq 'Valid'` and signer subject match
   `CN=Pyrsys B.V.` are both checked before execution; failure throws; the
   check cannot be bypassed/disabled.
5. **ISCC version (C5):** post-install `FileVersion` `6.7.3` check retained.
6. **No weakening (C6):** TLS/signature/runner guards intact; no version change,
   no secret, no prerequisite/dependency change, no host install.
7. **Static checks (C7):** YAML parse and actionlint evidence are real; workflow
   remains one `windows-installer` job on `windows-latest`,
   `workflow_dispatch`, `permissions: contents: read`, `if: always()` upload.
8. **Fail-closed evidence (C8):** reproduce/inspect the local proof: correct
   hash + valid signature passes; wrong expected hash throws; no install.
9. **Docs (C7/C11):** the CI note accurately describes the official URL,
   SHA-256 and Authenticode; no false cloud claim.
10. **Accounting:** confirm this is the one additional review, not a new
    approach or counter reset; previous 2 full reviews/C3 are preserved.

You may inspect the official public sources/hashes read-only if useful; do not
perform product/install/lifecycle execution. With complete evidence, do not
rerun already-proven commands except a missing/ambiguous artifact.

## Verdict

- **PASS** — correction is correct, scoped, fail-closed, and locally evidenced;
  coordinator may proceed to the approved commit/push/run. List any MINOR/NIT.
- **FAIL** — any BLOCKER/MAJOR finding. List stable finding IDs, criterion,
  location, observed result, reproduction/evidence, expectation, severity.
  No further fix/review will be made under this approval.

Do not write any file. End after the verdict with Orca `worker_done`
(outcome succeeded for PASS, failed for FAIL), a three-sentence summary,
findings, and evidence paths.
