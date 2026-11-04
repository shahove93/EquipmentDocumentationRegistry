# CI-CLOUD-01 — C3 diagnosis (RCA, verified sources, bounded plan)

Status: **diagnosis only**. No code change, commit, push, workflow run, acceptance
review, product-prerequisite change or host install was performed. Downloaded
installers/tools were kept only in `%TEMP%` for read-only inspection.

- Logical TASK: TASK-CI-WINDOWS-01 (approach A1, C3 diagnosis).
- Trigger: cloud run `41881330228` failed at `Install Inno Setup 6.7.3`.
- Accounting preserved: full reviews 2/2 (C1 FAIL, C2 PASS), failed review 1,
  CI Codex calls 2/4. This C3 is diagnostic; it is not a third A1 review and
  does not start A2 or a new run.
- Current published HEAD: `11d66b1c8a86dd59b7b1d7e693f8c27f43796196`.

## 1. Root cause

The workflow pinned an obsolete direct-download URL:

```text
https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe   -> HTTP 404
```

The official Inno Setup site moved installer binaries to **immutable GitHub
releases** in March 2026. `https://files.jrsoftware.org/is/6/` now lists only
`.issig` signature files plus `readme.txt`; it no longer serves `.exe` files.
`readme.txt` states:

> In March 2026 Inno Setup download links were updated to use immutable releases
> on GitHub. See https://github.com/jrsoftware/issrc/releases

So the failure is an **acquisition-URL defect in the CI implementation**, not a
missing release and not a product prerequisite/packaging defect. Build never
started; no guard was involved.

## 2. Verified official sources and HTTP results

All checks were read-only (`curl -L`, `Get-AuthenticodeSignature`,
`gh release verify-asset`, Python ECDSA verification).

| Source | HTTP | Result |
|--------|------|--------|
| `https://files.jrsoftware.org/is/6/` | 200 | directory listing: only `.issig` files + `readme.txt`; no `.exe` |
| `https://files.jrsoftware.org/is/6/readme.txt` | 200 | confirms March 2026 move to immutable GitHub releases |
| `https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe` | **404** | the URL used by the failed workflow |
| `https://jrsoftware.org/isdl.php` | 200 | official page: Inno 7.1.1 recommended; Inno 6.7.4 listed for 6.x; downloads via GitHub |
| `https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe` | **200** | 10,592,232 bytes; official immutable release |
| `https://files.jrsoftware.org/is/6/innosetup-6.7.3.exe.issig` | 200 | 376 bytes; official signature metadata |
| `https://files.jrsoftware.org/is/misc/def02.ispublickey` | 200 | official ECDSA P-256 public key |
| `https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe` | 200 | 10,604,576 bytes; current 6.x |

### 6.7.3 artifact verification

- SHA-256: `9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`
- `Get-AuthenticodeSignature`: **Valid**, signer
  `CN=Pyrsys B.V., O=Pyrsys B.V., S=Noord-Holland, C=NL`,
  thumbprint `E0AB19C8D38CBF9C44709925122A7A02F8C70CB7`.
- GitHub Release Attestation:
  `gh release verify-asset is-6_7_3 innosetup-6.7.3.exe --repo jrsoftware/issrc`
  exit **0**; the signed statement subject contains
  `sha256:9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732`.
- Official `.issig` (format `issig-v2`): `file-size` and `file-hash` match;
  ECDSA P-256 verification with the official `def02` key and
  `key-id def020ed…e7a28` returned **signature valid** (independent Python
  verification of the `.issig` `r`/`s` values). `.issig` SHA-256:
  `18DA06B0F8CA6021A42E023EBD02FE10D37A30A43639C08CC8B15363243663A0`.

### 6.7.4 availability (alternative only)

- SHA-256: `A549929319F9120716677C685535CA4671E4B937B5FDC87E2585F32D8EB30E8C`
- Authenticode **Valid**, same `Pyrsys B.V.` signer.
- `gh release verify-asset is-6_7_4 … --repo jrsoftware/issrc` exit **0**.

### Actual `ISCC.exe` version

The installer's own `ProductVersion` metadata is `6.7.3` and its provenance is
verified above. The extracted `ISCC.exe` FileVersion could **not** be read
locally without installing or using a compatible extractor: portable
`innoextract 1.9` supports only Inno Setup up to 6.0.5 and failed on 6.7.3
(“Unexpected setup loader revision: 2”). No host install was performed. The
existing CI step already verifies `ISCC.exe` FileVersion matches `6.7.3` after
installation; that runtime check remains the authoritative binary-version check
and should be retained.

## 3. Why the local review missed it

- The frozen checklist C2 required pinned URLs/SHA-256 for CPython and
  PostgreSQL, but for Inno only a **version** check. The repository had no
  recorded Inno SHA-256, so the implementer derived a plausible old-pattern
  URL and reviewers validated only static YAML/script content and the version
  string.
- Local evidence was explicitly static (py_compile, PowerShell parser, YAML,
  negative guard) and no installer/network execution was allowed on the host.
  A 404 cannot be detected by those checks.
- Reviewer finding `CI-C2-02` (MINOR) already noted “Inno has no recorded
  SHA-256; URL availability is verified only at cloud run time” and accepted it
  as a documented risk. The cloud run then exposed exactly that gap.
- The new verification method removes the cause by making acquisition
  **deterministic and preflight-checked**: official immutable release URL +
  pinned SHA-256 + Authenticode signer (and optionally `.issig`/GitHub
  attestation), verified before build. A wrong URL/hash then fails at preflight
  with a concrete mismatch, not halfway through the job.

## 4. Recommended minimal plan (for user approval; not executed)

**Recommendation: keep build contract 6.7.3 and correct only acquisition.**

Allowlist for the correction:
- `.github/workflows/windows-installer.yml` (only file required), plus optional
  `docs/installation/windows.md` CI-section note.
- Not allowed/touched: `build.ps1`, `edr.iss`, `provision.ps1`, `app/`,
  `frontend/`, `ci-installer.ps1/.py`, product prerequisites, tests, lockfiles.

Minimal change:
1. `INNO_SETUP_URL` → `https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe`
2. Add `INNO_SETUP_SHA256` = `9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732`.
3. After `Invoke-WebRequest`, verify `Get-FileHash -Algorithm SHA256` equals the
   pin; verify `Get-AuthenticodeSignature` is `Valid` and signer subject
   contains `Pyrsys B.V.`; fail closed otherwise.
4. Keep the existing post-install `ISCC.exe` FileVersion == `6.7.3` check.
5. Optionally pin the `.issig` hash and/or use `gh release verify-asset` if the
   runner has `gh`; SHA-256 + Authenticode is sufficient for the minimal plan.

Alternative (needs a build-contract/scope decision, not recommended first):
pin `6.7.4` instead, SHA-256
`A549929319F9120716677C685535CA4671E4B937B5FDC87E2585F32D8EB30E8C`, and update
the version in the workflow/docs. This changes the tool version, not just the
URL, so it needs explicit approval.

**Process/accounting:** A1 has already used both full reviews; this is C3, not a
third A1 review. A URL/hash acquisition fix is not a materially new approach
(no behavior change to build/install/runtime), so it should stay under A1 as a
bounded correction. Because the earlier review slots are exhausted, a scoped
re-verification decision is required from the user (targeted evidence check,
then one new explicit run approval). If the user instead wants a fresh
independent full review, that is a new approach A2 with fresh C1/C2 accounting.
No automatic A2, new run, commit or push is performed here.

## 5. Non-actions / non-claims

- No code, commit, push, workflow run, third A1 review, A2, new approach or
  product-prerequisite change.
- No EDR host install, no VM, no working-DB change.
- Only temporary read-only downloads of the official Inno Setup installers,
  official `.issig`/public key and portable `innoextract` in `%TEMP%`.
- Cloud C4–C9, UAC and full lifecycle remain NOT_RUN; no full Windows PASS.
