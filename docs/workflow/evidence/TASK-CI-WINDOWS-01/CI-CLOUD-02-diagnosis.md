# CI-CLOUD-02 — read-only diagnosis and minimal patch proposal

Status: **diagnosis only**. No code edit, commit, push, workflow run, host
install, VM/DB change or new Codex review was performed. Current logical
TASK/A1 and all counters are preserved: full reviews **3**, failed reviews
**1**, CI Codex calls **3/4**, additional A1 review slot already consumed,
C3 diagnoses preserved; no reserved Windows calls spent.

- Published HEAD/remote: `44d7b65bd387b3ab0b670efcb2686c05d11290ae`.
- Failed retry: run `41884655362`, head `44d7b65`, step
  `Install Inno Setup 6.7.3`.
- Evidence: `cloud-run-41884655362/run.log`.

## 1. Observed failure

The retry proved the acquisition correction works:

```text
Inno Setup installer verified: D:\a\_temp\innosetup-6.7.3.exe
sha256=9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732
signer=CN=Pyrsys B.V., O=Pyrsys B.V., S=Noord-Holland, C=NL
```

Then the **pre-existing retained** check failed:

```text
Installed ISCC version is not 6.7.3: 0.0.0.0
```

The build/runtime steps were skipped; no artifacts were produced. The installer
was downloaded, hash/signature-verified and executed; `ISCC.exe` exists.

## 2. Source-backed RCA (why 0.0.0.0 is expected)

Official tag `is-6_7_3` (`https://github.com/jrsoftware/issrc/tree/is-6_7_3`):

- `Projects/ISCC.dpr` links the prebuilt resource
  `{$R Res\ISCC.versionandicon.res}` (lines 44–45).
- `Projects/ISCC.dproj` has no Delphi `VerInfo_*` properties; the `.res` is the
  version source.
- The downloaded official `Projects/Res/ISCC.versionandicon.res`
  (SHA-256 `F05492F22C056951A5F3A0FBB5A2F947DEDF6ECA413406D9137526699D6CAC7C`)
  contains `VS_VERSION_INFO` whose **fixed** and **string** values are:

```text
FileDescription = 'Inno Setup Command-Line Compiler'
FileVersion     = '0.0.0.0'
ProductName     = 'Inno Setup'
ProductVersion  = '0.0.0.0'
FIXED FileVersion 0.0.0.0 / ProductVersion 0.0.0.0
```

Therefore `(Get-Item ISCC.exe).VersionInfo.FileVersion` returning `0.0.0.0`
is **by design**, not evidence of a wrong compiler or wrong installer. The
check is invalid for ISCC and was never a valid 6.7.3 test.

## 3. Real deterministic version signal

From `Projects/ISCC.dpr` (tag `is-6_7_3`):

- `ShowBanner` prints only `Inno Setup 6 Command-Line Compiler` (line 388) —
  **no patch version**.
- `ISCC.exe /?` calls `ShowBanner`, `ShowUsage`, then `Halt(1)` (lines
  482–485). It exits **1** and prints only the major version; unsuitable as a
  version query.
- `/Q`/`/Qp` sets quiet mode and suppresses the exact version line; do not use
  them for a version check.
- A normal compile (not quiet) prints to stdout (line 600):

```text
Compiler engine version: <Ver.Title> <Ver.Version>
```

Real repo evidence from previous successful builds using the same ISCC 6.7.3:

```text
Compiler engine version: Inno Setup 6.7.3
```

(source: `docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01/build.log:96`;
the same line appears in `TASK-WINDOWS-PROGRAMDATA-01-*` build/compile logs).

The engine version is the exact compiler binary version and is emitted **before
compilation**, on stdout. Success exit is `0` (`Halt(ExitCode)` with
`ExitCode=0`); failure is non-zero (`Halt(ExitCode)`/`Halt(2)`).

## 4. Minimal patch proposal (text only; not applied)

**Do not call this A2.** It is a bounded correction of the existing A1 CI
workflow, like the previous URL fix.

Allowlist: only `.github/workflows/windows-installer.yml` (and optionally the
targeted CI note in `docs/installation/windows.md`). No product prerequisites,
scripts, version, dependencies or lockfiles change.

1. Remove the invalid pre-build `VersionInfo.FileVersion` check
   (currently lines 112–115 in the workflow):

```powershell
$version = (Get-Item -LiteralPath $iscc).VersionInfo.FileVersion
if ($version -notmatch '^6\.7\.3(\D|$)') {
    throw "Installed ISCC version is not 6.7.3: $version"
}
Write-Output "ISCC: $iscc ($version)"
```

Replace with an existence-only line, e.g.
`Write-Output "ISCC: $iscc"`.

2. In the existing **Build installer** step, after `build.ps1` has completed
successfully (and therefore after `Tee-Object` has written `build.log`), add:

```powershell
$compilerVersionLine = Select-String -LiteralPath $buildLog `
    -Pattern '^Compiler engine version: Inno Setup 6\.7\.3$' -Quiet
if (-not $compilerVersionLine) {
    throw "ISCC compiler engine version line 'Inno Setup 6.7.3' not found in $buildLog"
}
Write-Output "ISCC compiler engine version verified from build log"
```

3. Keep unchanged:
   - official immutable URL + `INNO_SETUP_SHA256` + Authenticode
     (`Valid`, `CN=Pyrsys B.V.`) before execution;
   - ISCC existence check;
   - `build.ps1`'s own native exit check
     (`if ($LASTEXITCODE) { throw "Inno Setup failed: ..." }`);
   - `INNO_VERSION=6.7.3` and docs.

### Why this preserves native exit codes

- `build.ps1` already throws on any non-zero ISCC exit. The new check runs only
  after a successful build; it does not replace or swallow that exit code.
- The new check is an explicit `throw` on a missing/wrong line. A missing line
  or a different compiler version fails closed.
- No `2>&1`/pipeline change is needed; `Tee-Object` already captures the ISCC
  stdout line into `build.log`.

### Alternatives considered

- `ISCC.exe /?`: prints only “Inno Setup 6” and exits 1 → not exact, not a
  success query.
- `VersionInfo.ProductVersion`/`FileVersion`: both `0.0.0.0` by design → invalid.
- Separate tiny compile probe: works, but adds an extra compile; the real build
  log already contains the same line, so it is unnecessary.
- Accept installer SHA/Authenticode alone as provenance: strongest
  acquisition guarantee, but does not independently confirm the compiler engine
  version; keep the banner check if the contract requires an ISCC version check.

## 5. Verification before any new cloud run

No host install is needed. The patch can be pre-verified with:

1. Static: YAML parse + actionlint; assert the FileVersion check is gone and the
   `Compiler engine version: Inno Setup 6.7.3` check exists after `build.log`.
2. Positive parser test against an existing real build log:
   `Select-String -LiteralPath docs/workflow/evidence/TASK-WINDOWS-CRT-OFFLINE-01/build.log -Pattern '^Compiler engine version: Inno Setup 6\.7\.3$' -Quiet`
   → `True`.
3. Negative parser test against a synthetic log line
   `Compiler engine version: Inno Setup 6.7.4` → `False` and the step throws.
4. Re-run `git diff --check` scoped to the allowlisted files.
5. Then request a new explicit user approval for the bounded correction, any
   needed review slot, and one new cloud run. Do not run automatically.

## 6. Non-actions / evidence

- No code or docs were changed by this diagnosis; only this report under
  `docs/workflow/evidence/TASK-CI-WINDOWS-01/`.
- No commit/push/run, no new review, no Codex call, no host install.
- Official source artifacts downloaded read-only to `%TEMP%`:
  `ISCC.dpr` SHA-256 `F357EF19…A1001977`, `ISCC.dproj`
  `8691A175…5363CCB2`, `ISCC.versionandicon.res`
  `F05492F2…699D6CAC7C`, `Setup.version.rc` `5AB779E6…3DFB9341`.
- Cloud run `41884655362` failure log and report remain
  `cloud-run-41884655362/{run.log,report.md}`.
- No full Windows/UAC/lifecycle PASS is claimed.
