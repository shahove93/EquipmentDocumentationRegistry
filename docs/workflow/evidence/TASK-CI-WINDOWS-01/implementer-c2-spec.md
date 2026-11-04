# Implementer C2 correction spec — TASK-CI-WINDOWS-01 A1/C2

You are the separate OpenCode implementer continuing the same logical TASK
TASK-CI-WINDOWS-01 (approach A1, cycle C2). You are not the coordinator and do
not assign project PASS. Do not use native subagents. Work in the existing
worktree `D:/Antigravity/EquipmentDocumentationRegistry`, branch `main`, HEAD
`dccb14554cca3f688f20153f1f3eb41195740319`.

Read first:
- `docs/workflow/reviews/TASK-CI-WINDOWS-01-C1.md` (the FAIL verdict)
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/frozen-checklist.md`
- `docs/workflow/evidence/TASK-CI-WINDOWS-01/review-packet/review-spec.md`
- your own `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/report.md`
  and `checks.md`
- the actual files you changed.

## Required fix (MAJOR CI-C2-01)

`.github/workflows/windows-installer.yml` frontend step currently runs:

```yaml
      - name: Build frontend
        working-directory: frontend
        run: |
          npm ci
          npm run build
```

This can pass when `npm ci` fails and `npm run build` succeeds. Change the step
to fail closed on the first nonzero native exit. Use `shell: pwsh` and explicit
checks, e.g.:

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

Equivalent reliable native-error semantics are acceptable, but the step must
stop on the first nonzero `npm` exit. Keep the rest of the job unchanged.

## Optional closures (same allowlist, low risk)

- CI-C2-02 (MINOR, docs): adjust the CI section of `docs/installation/windows.md`
  so Inno Setup is described as version-verified (`ISCC.exe` FileVersion
  `6.7.3`), not as byte-pinned/byte-reproducible. Optionally note that a pinned
  Inno SHA-256 is not recorded. Do not invent a hash.
- CI-C3-01 (NIT): remove the unused `-BuildWorkDirectory` parameter from
  `ci-installer.ps1` and its argument in the workflow, or genuinely use it.
  If removed, keep the workflow's own freshness check of the build directory.
- CI-C12-01 (MINOR evidence): make every command in `checks.md` fully
  reproducible — no ellipses, no placeholders. Record exact commands, CWD and
  exit codes, including the corrected frontend step semantics.

## Required local evidence for C2 (no product install on this host)

Add to `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/`:
- `c2-correction.md` — what changed, exact commands/CWD/exit codes, closure of
  each finding.
- `check-c2-frontend-exit.txt` — a reproducible local proof that the corrected
  step fails closed. Simulate the pattern under `pwsh` with the same explicit
  exit handling: a failing native command (e.g. `cmd /c exit 7`) followed by a
  succeeding native command (`cmd /c exit 0`) must make the snippet exit
  non-zero. Also statically show the explicit `$LASTEXITCODE` checks after both
  npm commands in the workflow. Use `pwsh -NoProfile -NonInteractive` and make
  the command fully quoted/reproducible.
- Updated `checks.md` with exact reproducible commands (fix CI-C12-01).
- `worker-c2.diff` — exact diff of the C2 change.
- `git-status.txt` after the change.

Also re-run and record (exit 0 each): `python -m py_compile
packaging/windows/ci-installer.py`, the PowerShell 5.1 parser check of
`ci-installer.ps1`, and the workflow YAML parse. If you touched `ci-installer.py`
(only if needed), re-run py_compile.

## Constraints

- Same allowlist: `.github/workflows/windows-installer.yml`,
  `packaging/windows/ci-installer.ps1`, `packaging/windows/ci-installer.py`,
  `docs/installation/windows.md`, plus implementer evidence. Do NOT edit
  `app/`, `frontend/`, `edr.iss`, `build.ps1`, `smoke.ps1`, `smoke.py`, old
  tests, lockfiles, `.env`, `ci.yml`, or prior evidence. Preserve all unrelated
  dirty/untracked files.
- No installer/app/lifecycle execution on this host; no commit/push/run; no
  database, UAC or VM change; no remote network mutation.
- Do not claim project/cloud PASS. Cloud run remains NOT_RUN.

## Return protocol

Send Orca `worker_done` from your dispatch with `--outcome succeeded` only if
the correction and local evidence are complete; otherwise `--outcome failed`.
Three sentences: what you changed, what you verified, what remains (the repeat
full review and cloud NOT_RUN). Include `--files-modified` with real paths and
`--report-path` → `docs/workflow/evidence/TASK-CI-WINDOWS-01/implementer/c2-correction.md`.
