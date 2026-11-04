# TASK-CI-WINDOWS-01 — A1/C1 independent R2 review record

- Reviewer: Codex `gpt-6.1-sol`, effort `high`, read-only.
- Orca Task `task_80bc9b40fd78`, Dispatch `ctx_6c79fb638ac9`,
  Run `run_b556ddaf13c3`, terminal `term_6d86490f-d884-49f9-8545-8743a672ac4b`.
- Worker result: `worker_done` msg_8baee080df05, outcome `failed` (verdict FAIL).
- Revision reviewed: `main` HEAD
  `dccb14554cca3f688f20153f1f3eb41195740319`; approved TASK SHA-256
  `DE3B5B2D12C1F76DBA775BC82C391DF85EFAC1FCDB67291BF20371BB72ECB950`.
- Codes inspected: `.github/workflows/windows-installer.yml`
  (`3C69EBD5…D3DE15C`), `packaging/windows/ci-installer.ps1`
  (`B1D34ECE…CBCBAB8A`), `packaging/windows/ci-installer.py`
  (`5EC794D5…51B9FA5`), appended CI section of `docs/installation/windows.md`.
- Review packet: `docs/workflow/evidence/TASK-CI-WINDOWS-01/review-packet/`.
- Acceptance accounting: **full review 1 of 2** used; **failed review count 1**
  (BLOCKER/MAJOR present). Approach A1, cycle C1. Next allowed step: one bounded
  C2 correction and the single repeat full review. If C2 also FAILs, only C3
  diagnosis remains.
- Codex usage for this logical CI TASK: **call 1** used (separate from the two
  reserved ProgramData/lifecycle Windows calls). Token usage was not exposed in
  the worker_done payload; not fabricated.

## Verdict

**FAIL — READY_FOR_CLOUD_TESTING not granted.** C1/C3/C10/C11 locally satisfied;
C2 partially failed; C4–C9 statically implemented but cloud NOT_RUN; C12
supported plus reviewer supplements.

## Findings

| ID | Severity | Criterion | Location | Finding | Required closure |
|----|----------|-----------|----------|---------|------------------|
| CI-C2-01 | **MAJOR** | C2 | `.github/workflows/windows-installer.yml:45-49` | `npm ci` and `npm run build` run consecutively without checking the first native exit code, so a failed install followed by a successful build can make the step pass. Reviewer reproduced the semantics on PowerShell 7.6.5: first native exit 7 then an exit-0 command gives outer exit 0. | Fail the step immediately on nonzero `npm ci` (and `npm run build`) with explicit exit handling or equivalent reliable native-error semantics; bounded reproducible evidence. Affected cloud chain stays stopped until corrected. |
| CI-C2-02 | MINOR | C2/C11 | workflow:75-99; windows.md CI item 3 | Inno Setup is version-pinned and `ISCC.exe` FileVersion checked, but its installer is not SHA-256-pinned; documentation wording overstates byte reproducibility. Meets the frozen version requirement; optional hardening. | Optional: clarify documentation as version-verified, not byte-reproducible; optional SHA pin. No stop. |
| CI-C3-01 | NIT | C3 | `ci-installer.ps1:12` | `BuildWorkDirectory` accepted but never referenced; the workflow freshness-checks it separately and it must exist during install. No contract failure. | Optional cleanup. No stop. |
| CI-C4-01 | MINOR (conditional cloud risk) | C4 | `provision.ps1:23-28`, `edr.iss:124-134` (context only) | Absence of a same-session interactive shell definitely causes install refusal, but the packet does not establish that the hosted runner lacks that shell. Acceptable documented NOT_RUN compatibility risk, not a proven packaging defect. | If a cloud run observes shell/session refusal, stop the affected install path and route it separately without weakening packaging guards. |
| CI-C12-01 | MINOR (evidence clarity) | C12 | `implementer/checks.md`, `check-yaml.txt`, `check-negative-guard.txt` | Original YAML command contained an ellipsis and negative-test arguments contained placeholders. Reviewer used the review-policy exception once per actual check to supply reproducible read-only results. | Preserve reviewer transcripts; implementer must publish exact reproducible commands in C2. |

Reviewer explicitly found no exit-code propagation problem at workflow:148-153
and no installed-runtime fail-open (driver and both launches use the installed
`python/python.exe`; failures throw).

## Reviewer-executed check evidence (review-policy exception)

- CWD `D:/Antigravity/EquipmentDocumentationRegistry`; branch/HEAD as above.
- YAML `safe_load` + assertions: exit 0.
- Negative-guard actual invocation: `powershell.exe -NoProfile -NonInteractive
  -ExecutionPolicy Bypass -File packaging/windows/ci-installer.ps1 -Exe
  C:/Users/user/AppData/Local/Temp/edr-ci-review-<id>-missing.exe -WorkDirectory
  C:/Users/user/AppData/Local/Temp/edr-ci-review-<id>-work -InstallDirectory
  C:/Users/user/AppData/Local/Temp/edr-ci-review-<id>-install` with the four CI
  markers removed: script exit 2, harness exit 0; work/install/missing-EXE and
  `%ProgramData%\EDR` absent before and after.
- Original `py_compile` exit 0 and PowerShell 5.1 parser exit 0 reused.
- All 345 baseline hashes matched except allowed documentation and
  coordinator-owned HISTORY/STATE. `ci.yml` byte-equal to HEAD. Original 23326
  documentation bytes unchanged; one blank CRLF appended before the CI section.
- No repository file, product process, database, VM, remote Git or network
  service was modified or started.
- Reviewer noted two non-counted harness hiccups (missing ProgramData in parent
  env; a quoting error in a native-exit probe); neither was counted as evidence.

## Coordinator action

FAIL permits exactly one bounded C2 correction and one repeat full review.
C2 correction will address CI-C2-01 (required), and optionally CI-C2-02/CI-C3-01/
CI-C12-01. CI-C4-01 remains a documented NOT_RUN cloud risk; no packaging guard
is to be weakened. Cloud run, UAC/manual clean-PC and full lifecycle remain
NOT_RUN; no project PASS.
