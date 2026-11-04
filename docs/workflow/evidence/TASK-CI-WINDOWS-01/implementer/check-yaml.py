"""Reproducible YAML parse + structural assertions for the CI workflow."""
from pathlib import Path
import sys

import yaml

repo = Path(__file__).resolve().parents[5]
workflow_path = repo / ".github" / "workflows" / "windows-installer.yml"
data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

# PyYAML (YAML 1.1) decodes the unquoted `on:` key as boolean True.
trigger = data.get(True, data.get("on"))
jobs = data.get("jobs", {})
assert list(jobs) == ["windows-installer"], list(jobs)
job = jobs["windows-installer"]
assert job["runs-on"] == "windows-latest", job["runs-on"]
assert data["permissions"] == {"contents": "read"}, data["permissions"]
assert trigger == {"workflow_dispatch": None} or trigger == {"workflow_dispatch": {}}, trigger

steps = job["steps"]
upload = [s for s in steps if s.get("uses", "").startswith("actions/upload-artifact")]
assert upload, "no upload-artifact step"
assert upload[0].get("if") == "always()", upload[0].get("if")

frontend = [s for s in steps if s.get("name") == "Build frontend"]
assert len(frontend) == 1, frontend
fe = frontend[0]
assert fe.get("shell") == "pwsh", fe.get("shell")
run_text = fe["run"]
assert run_text.count("$LASTEXITCODE -ne 0") == 2, run_text
assert run_text.index("$LASTEXITCODE -ne 0") < run_text.index("npm run build"), run_text

install_step = [s for s in steps if s.get("name") == "Silent install and installed-runtime checks"][0]
assert "-BuildWorkDirectory" not in install_step["run"], install_step["run"]

print("YAML_OK jobs=windows-installer trigger=workflow_dispatch "
      "upload_artifact_if_always=true frontend_shell=pwsh "
      "last_exitcode_checks=2 buildworkdirectory_arg=absent")
sys.exit(0)
