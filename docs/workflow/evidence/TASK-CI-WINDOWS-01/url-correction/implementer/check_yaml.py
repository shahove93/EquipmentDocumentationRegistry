"""Static YAML/structural assertions for the CI-CLOUD-01 correction.

Read-only: parses the workflow and asserts the frozen checklist items.
"""

import sys
from pathlib import Path

import yaml

WF = Path(r"D:\Antigravity\EquipmentDocumentationRegistry\.github\workflows\windows-installer.yml")
EXPECTED_URL = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
EXPECTED_SHA = "9C73C3BAE7ED48D44112A0F48E66742C00090BDB5BEF71D9D3C056C66E97B732"

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" :: {detail}" if detail else ""))
    if not condition:
        failures.append(label)


raw = WF.read_text(encoding="utf-8")
doc = yaml.safe_load(raw)

# workflow_dispatch only
on_key = doc.get(True, doc.get("on"))
check("trigger is workflow_dispatch only",
      isinstance(on_key, dict) and set(on_key.keys()) == {"workflow_dispatch"},
      repr(on_key))

# permissions contents: read
check("permissions.contents == read",
      doc.get("permissions", {}).get("contents") == "read",
      repr(doc.get("permissions")))

jobs = doc.get("jobs", {})
check("exactly one job named windows-installer",
      list(jobs.keys()) == ["windows-installer"], repr(list(jobs.keys())))

job = jobs.get("windows-installer", {})
env = job.get("env", {})
check("INNO_VERSION remains 6.7.3", env.get("INNO_VERSION") == "6.7.3", repr(env.get("INNO_VERSION")))
check("INNO_SETUP_URL is official immutable release", env.get("INNO_SETUP_URL") == EXPECTED_URL,
      repr(env.get("INNO_SETUP_URL")))
check("INNO_SETUP_SHA256 pinned", env.get("INNO_SETUP_SHA256") == EXPECTED_SHA,
      repr(env.get("INNO_SETUP_SHA256")))

steps = job.get("steps", [])
names = [s.get("name", "") for s in steps]

# upload step with if: always()
uploads = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
check("one upload-artifact step", len(uploads) == 1, repr(len(uploads)))
check("upload step uses if: always()",
      len(uploads) == 1 and str(uploads[0].get("if", "")).strip() == "always()",
      repr(uploads[0].get("if")) if uploads else "none")

# Inno install step content
inno_steps = [s for s in steps if "Install Inno Setup" in s.get("name", "")]
check("single Inno Setup install step", len(inno_steps) == 1, repr(len(inno_steps)))
inno_run = inno_steps[0].get("run", "") if inno_steps else ""

check("hash compare precedes Start-Process",
      inno_run.find("Get-FileHash") != -1
      and inno_run.find("Get-FileHash") < inno_run.find("Start-Process"),
      "Get-FileHash before Start-Process")
check("hash mismatch throws", "SHA-256 mismatch" in inno_run and "throw" in inno_run)
check("Authenticode status Valid checked", "Get-AuthenticodeSignature" in inno_run
      and "Status -ne 'Valid'" in inno_run)
check("Authenticode signer CN=Pyrsys B.V. checked", "CN=Pyrsys B\\.V\\." in inno_run
      or "CN=Pyrsys B.V." in inno_run)
check("signature check precedes Start-Process",
      inno_run.find("Get-AuthenticodeSignature") != -1
      and inno_run.find("Get-AuthenticodeSignature") < inno_run.find("Start-Process"))
check("ISCC FileVersion 6.7.3 check retained",
      "VersionInfo.FileVersion" in inno_run and "^6\\.7\\.3" in inno_run,
      "FileVersion regex present")
check("ISCC check still after installation", "ISCC.exe" in inno_run)

print()
if failures:
    print(f"FAILED {len(failures)} assertion(s): {failures}")
    sys.exit(1)
print("ALL STRUCTURAL ASSERTIONS PASSED")
sys.exit(0)
