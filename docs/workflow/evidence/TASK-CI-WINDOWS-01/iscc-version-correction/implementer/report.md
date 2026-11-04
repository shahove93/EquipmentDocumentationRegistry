# TASK-CI-WINDOWS-01 / A1 — ISCC version-check correction: implementer report

- Task: bounded A1 correction under
  `CI_CLOUD_02_ISCC_VERSION_CHECK_CORRECTION_AUTHORIZED_20261104`.
- Branch `main`, baseline HEAD `44d7b65bd387b3ab0b670efcb2686c05d11290ae`.
- Implementer: OpenCode worker (dispatched), effective model
  `deepseek/deepseek-flash`.
- No commit, push, workflow run, host install, VM, working DB or release action.
- No project/cloud PASS is claimed.

## Changes (strict allowlist)

1. `.github/workflows/windows-installer.yml` — required:
   - In `Install Inno Setup 6.7.3`: removed only the invalid
     `(Get-Item $iscc).VersionInfo.FileVersion` + `^6\.7\.3` check and its
     `Write-Output "ISCC: $iscc ($version)"`. The ISCC existence check,
     official immutable URL, SHA-256 check and Authenticode
     (`Status -eq 'Valid'` / `CN=Pyrsys B.V.`) checks are unchanged. Replaced
     with `Write-Output "ISCC: $iscc"`.
   - In `Build installer`: after the successful `try { build.ps1 } catch
     { …; throw }` block and before locating the EXE, added the fresh-log
     existence guard and the `Select-String` check for exactly
     `^Compiler engine version: Inno Setup 6\.7\.3$`, followed by
     `Write-Output "ISCC compiler engine version verified from build log"`.
   - `build.ps1`, `edr.iss`, `provision.ps1`, `ci-installer.*` and the
     version/toolchain are untouched.
2. `docs/installation/windows.md` — optional targeted CI note: CI item 3 now
   states the compiler-engine version is verified from the successful build-log
   line `Compiler engine version: Inno Setup 6.7.3`, not from the installed
   `ISCC.exe` `FileVersion`. No other documentation changed.

Exact diff: `worker.diff`.

## Commands / CWD / exit codes

See `checks.md` for full command lines and logs. Summary (all CWD
`D:\Antigravity\EquipmentDocumentationRegistry`):

| Check | Exit | Log |
|-------|------|-----|
| YAML parse + 18 structural assertions (`python check_static.py`) | 0 | `01-static.txt` |
| `actionlint` 1.7.12 on workflow | 0 | `02-actionlint.txt` |
| Positive/negative version signal (real 6.7.3 / synthetic 6.7.4 / missing) | 0 | `03-version-signal.txt` |
| Failed-build control (marker unreached, step non-zero) | 1 (expected) | `04-failed-build-control.txt` |
| Stale-log control (`$logDir` freshness guard) | 1 (expected) | `05-stale-log-control.txt` |
| `git diff --check` scoped to allowlist | 0 | `06-diff-check-scoped.txt` |
| `git diff --check` full tree | 2 (pre-existing HISTORY.md blank line at EOF only) | `07-diff-check-full.txt` |
| `git status --porcelain` | 0 | `git-status.txt` |
| Protected-file hashes vs `baseline-hashes.txt` | 0 | `08-hashes.txt` |

Only `.github/workflows/windows-installer.yml` and
`docs/installation/windows.md` differ from the baseline hashes; all protected
files (`build.ps1`, `edr.iss`, `ci-installer.ps1/.py`, `app/windows_local.py`,
`app/windows_layout.py`) are byte-identical. Pre-existing dirty/untracked files
in `git status` were preserved and not staged.

## Checklist closure (frozen-checklist.md)

- **C1** — only the two allowlisted files changed (hashes + `git status`).
- **C2** — invalid `VersionInfo.FileVersion` check removed; ISCC existence
  check retained (static assertions).
- **C3** — official immutable URL, `INNO_SETUP_SHA256`
  `9C73C3…B732`, Valid Authenticode `CN=Pyrsys B.V.` unchanged (diff/static).
- **C4** — fresh `build.log` must contain exactly
  `Compiler engine version: Inno Setup 6.7.3`; 6.7.4 and missing-line logs
  return False (positive/negative proof).
- **C5** — check sits after the successful try/catch; failed build rethrows
  before it (control shows markers unreached, step exit 1); fresh `$logDir`
  guard retained and stale log rejected.
- **C6** — native exit handling unchanged; no `/Q`/`/Qp`; no swallowing.
- **C7** — positive/negative/failed-build evidence recorded with exits.
- **C8** — YAML parses, actionlint 0, scoped `git diff --check` 0; doc note
  updated accurately.
- **C9** — no version/toolchain/prerequisite/runner-guard changes; no host
  install; no new secret.
- **C10** — report, checks, raw logs, `worker.diff`, `git-status.txt`, hashes
  present. No commit/push/run performed by the implementer.

## Residual risks / NOT_RUN

- The correction was not executed in GitHub Actions. Cloud acquisition,
  non-quiet build log emission and the new check are proven only statically and
  by local signal/control harnesses.
- `Compiler engine version` formatting depends on the pinned official ISCC
  6.7.3; it is emitted only in non-quiet builds (the workflow does not pass
  `/Q`/`/Qp`). If upstream changes wording, the check fails closed (safe).
- Full Windows/UAC/lifecycle PASS and installed-app behavior remain unproven by
  this A1 correction.

## Remaining

1. One independent routed review (the single additional A1 review slot).
2. Separately approved scoped commit/push and exactly one `workflow_dispatch`
   run on the published headSha.
