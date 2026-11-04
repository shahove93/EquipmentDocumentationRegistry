# TASK-CI-WINDOWS-01 A1/C2 — implementer correction report

- Worktree: `D:/Antigravity/EquipmentDocumentationRegistry`
- Branch: `main`, HEAD: `dccb14554cca3f688f20153f1f3eb41195740319`
- Role: separate implementer for C2 (not coordinator; no project PASS assigned)
- Input: C1 FAIL review `docs/workflow/reviews/TASK-CI-WINDOWS-01-C1.md`
- Result: corrections and local evidence complete; actual GitHub run **NOT_RUN**.
- Host: Windows; Windows PowerShell 5.1.26100.9711; Python 3.12.4; PyYAML
  6.0.3. `pwsh` (PowerShell 7) is not installed on this host.
- No installer/app/lifecycle/product install was run. `%ProgramData%\EDR` was
  not created. No commit/push/tag, no database/UAC/VM/remote network change.

## Files changed in C2 (same allowlist)

| Change | Path | SHA-256 after C2 |
|--------|------|------------------|
| EDIT | `.github/workflows/windows-installer.yml` | `7A256F572EC97760DF255EAE6E6E9E99989D7A00D68C456D15362FD27AD8DA21` |
| EDIT | `packaging/windows/ci-installer.ps1` | `764AB73A1C3BAD3AD49FC774AF61891AC690A3566C8B7E4F349D9583098D2F05` |
| EDIT | `docs/installation/windows.md` | `E68366289EDA94264DFEA815CB817BD3293218F1A87BAD727B80D9AEEFD4881E` |
| UNCHANGED | `packaging/windows/ci-installer.py` | `5EC794D5BC39ABD5772639BE1F9B28BA08CF772F92EF1F049442F75DE51B9FA5` |
| CREATE | `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/c2-correction.md` | this file |
| CREATE | `.../implementer/check-c2-frontend-exit.txt` | local fail-closed proof |
| CREATE | `.../implementer/check-c2-pycompile.txt` | py_compile log (exit 0, no output) |
| CREATE | `.../implementer/check-c2-ps-parser.txt` | parser log |
| CREATE | `.../implementer/check-c2-yaml.txt` | YAML/invariant log |
| CREATE | `.../implementer/check-c2-negative-guard.txt` | guard re-check |
| CREATE | `.../implementer/check-frontend-exit.ps1` | reproducible probe |
| CREATE | `.../implementer/parse-ci-installer.ps1` | reproducible parser probe |
| CREATE | `.../implementer/check-yaml.py` | reproducible YAML probe |
| EDIT | `.../implementer/checks.md` | exact reproducible commands (C12) |
| CREATE | `.../implementer/worker-c2.diff` | exact C2 diff |
| EDIT | `.../implementer/git-status.txt` | status after C2 |

No other file was written by this worker. Prior C1 evidence files were not
edited except `checks.md` (the coordinator explicitly requested the updated
reproducible command list) and `git-status.txt`.

## Changes made

### CI-C2-01 (MAJOR, required) — frontend step now fails closed

`.github/workflows/windows-installer.yml` `Build frontend` step changed from a
plain two-line `run:` to:

```yaml
      - name: Build frontend
        working-directory: frontend
        shell: pwsh
        run: |
          $ErrorActionPreference = 'Stop'
          npm ci
          if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
          npm run build
          if ($LASTEXITCODE -ne 0) { throw "npm run build failed with exit code $LASTEXITCODE" }
```

Each native `npm` call is immediately followed by an explicit `$LASTEXITCODE`
check that throws, so the step stops on the first nonzero npm exit. The rest of
the job is unchanged.

Local proof (`check-c2-frontend-exit.txt`): the same pattern with
`cmd /c exit 7` followed by `cmd /c exit 0` exits **1**, and a control with no
checks exits **0**, reproducing the C1 defect and showing the fix. Because
`pwsh` is absent on this host the probe ran under Windows PowerShell 5.1 (same
native exit-code semantics); the workflow uses `shell: pwsh` on the runner.

### CI-C2-02 (MINOR, optional) — Inno wording corrected

`docs/installation/windows.md` CI item 3 now says Inno Setup `6.7.3` is
installed from the official URL and verified by `ISCC.exe` `FileVersion`, not
by bytes; it explicitly states that no pinned Inno Setup SHA-256 is recorded
and byte reproducibility is not guaranteed. No hash was invented.

### CI-C3-01 (NIT, optional) — unused parameter removed

`packaging/windows/ci-installer.ps1` no longer declares
`-BuildWorkDirectory`; the workflow no longer passes it. The workflow's own
freshness check of `$RUNNER_TEMP\edr-build` in the `Build installer` step is
retained, and the silent-install step still reads `installer-exe.json` from
`$buildWork`.

### CI-C12-01 (MINOR, optional) — reproducible evidence

`checks.md` was rewritten with literal commands, fixed CWD and recorded exit
codes; no `<temp>`, `<missing>`, `<fresh>` or `...` placeholders remain. New
helper scripts under the implementer evidence directory make every check
re-runnable verbatim.

## Local checks — exact commands, CWD, exit codes

All commands run from CWD `D:\Antigravity\EquipmentDocumentationRegistry`.

| Check | Exact command | Exit | Log |
|-------|---------------|------|-----|
| Python syntax | `python -m py_compile packaging/windows/ci-installer.py` | `0` | `check-c2-pycompile.txt` |
| PowerShell 5.1 parser | `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/parse-ci-installer.ps1` | `0` | `check-c2-ps-parser.txt` |
| YAML parse + structure | `python docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/check-yaml.py` | `0` | `check-c2-yaml.txt` |
| Frontend fail-closed proof | `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/check-frontend-exit.ps1` | `1` (expected non-zero) | `check-c2-frontend-exit.txt` |
| Negative guard | see `check-c2-negative-guard.txt` (exact two-command preparation/invocation) | script `2` (expected non-zero) | `check-c2-negative-guard.txt` |
| Status | `git status --porcelain` | `0` | `git-status.txt` |

Observed outputs:

- `PARSER_OK errors=0`
- `YAML_OK jobs=windows-installer trigger=workflow_dispatch upload_artifact_if_always=true frontend_shell=pwsh last_exitcode_checks=2 buildworkdirectory_arg=absent`
- Frontend probe: `OUTER_EXIT=1`; control `CONTROL_OUTER_EXIT=0`
- Negative guard: exit `2`, `INSTALL_DIR_CREATED=False`, `WORK_DIR_CREATED=False`

## Closure of findings

| Finding | Severity | Status | Evidence |
|---------|----------|--------|----------|
| CI-C2-01 | MAJOR | CLOSED: explicit `$LASTEXITCODE` throw after each npm command; local fail-closed proof and fail-open control | workflow lines 45–53; `check-c2-frontend-exit.txt` |
| CI-C2-02 | MINOR | CLOSED: docs describe version verification, state no pinned Inno SHA-256 | `docs/installation/windows.md` item 3; `worker-c2.diff` |
| CI-C3-01 | NIT | CLOSED: unused `-BuildWorkDirectory` removed; workflow freshness check kept | `worker-c2.diff`; `check-c2-yaml.txt` |
| CI-C12-01 | MINOR | CLOSED: literal reproducible commands in `checks.md` | `checks.md`, helper scripts, check logs |
| CI-C4-01 | MINOR (cloud) | Not addressed by design: documented NOT_RUN cloud risk; no packaging guard weakened | unchanged |

## Diff and status

- `worker-c2.diff` — exact C2 diff relative to the C1-reviewed state for the
  three allowlisted changed paths.
- `git-status.txt` — `git status --porcelain` after C2.

## Explicit non-claims

- No project or cloud PASS is claimed. Actual GitHub Actions run: **NOT_RUN**.
- Real interactive UAC, clean end-user PC install and full lifecycle remain out
  of scope and unverified.
- No commit, push, tag or remote state change was made.
