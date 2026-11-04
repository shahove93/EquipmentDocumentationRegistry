"""Static structure checks for the ISCC version-check correction (read-only)."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[6]
wf_path = ROOT / ".github" / "workflows" / "windows-installer.yml"
text = wf_path.read_text(encoding="utf-8")

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))


# YAML parse
try:
    doc = yaml.safe_load(text)
    parsed = isinstance(doc, dict)
    err = ""
except Exception as exc:  # noqa: BLE001
    doc = None
    parsed = False
    err = repr(exc)
check("yaml parses to a mapping", parsed, err)

# 1. FileVersion check absent
check("VersionInfo.FileVersion absent", "VersionInfo.FileVersion" not in text)
check("old version throw absent", "Installed ISCC version is not 6.7.3" not in text)

# 2. new compiler-version check present after build.ps1 / Tee-Object
tee_idx = text.find("Tee-Object -FilePath $buildLog")
check_idx = text.find("Compiler engine version: Inno Setup 6")
check(
    "compiler-version check after Tee-Object",
    tee_idx != -1 and check_idx != -1 and check_idx > tee_idx,
    f"tee={tee_idx} check={check_idx}",
)
check(
    "exact regex pattern present",
    r"-Pattern '^Compiler engine version: Inno Setup 6\.7\.3$' -Quiet" in text,
)
check("Select-String used", "Select-String -LiteralPath $buildLog" in text)
check(
    "build log existence guard present",
    "Build log missing: $buildLog" in text,
)

# 3. retained controls
check(
    "official immutable URL retained",
    "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
    in text,
)
check(
    "INNO_SETUP_SHA256 retained",
    "9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732" in text,
)
check(
    "Authenticode Status Valid retained",
    "if ($signature.Status -ne 'Valid')" in text,
)
check(
    "signer CN=Pyrsys B.V. retained",
    r"CN=Pyrsys B\.V\." in text,
)
check(
    "ISCC existence check retained",
    "ISCC.exe not found after Inno Setup installation" in text,
)
check(
    "ISCC line simplified",
    'Write-Output "ISCC: $iscc"' in text and "$iscc ($version)" not in text,
)
check("INNO_VERSION is 6.7.3", "INNO_VERSION: '6.7.3'" in text)

# 4. no quiet switches
check("no /Q or /Qp compiler flags", "/Qp" not in text and " /Q" not in text)

# 5. fresh $logDir guard retained
check(
    "fresh $logDir guard retained",
    "Build log directory must be fresh: $logDir" in text,
)
check(
    "buildLog created in same step",
    "$buildLog = Join-Path $logDir 'build.log'" in text,
)

# 6. try/catch rethrow shape preserved
check(
    "try/catch rethrow preserved",
    "} catch {" in text and "throw" in text and "Tee-Object -FilePath $buildLog" in text,
)

failed = [r for r in results if not r[1]]
for name, ok, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))

print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
