"""Synthetic native Windows lifecycle; run from smoke.ps1 using bundled Python."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--install", type=Path, required=True)
parser.add_argument("--work", type=Path, required=True)
parser.add_argument("--installer", type=Path, required=True)
args = parser.parse_args()
install, work = args.install, args.work
python = install / "python/python.exe"
data = Path(os.environ["LOCALAPPDATA"]) / "EDR/data"
base = "http://127.0.0.1:18765"
events = []


def record(name, **values):
    events.append(dict(check=name, **values))
    (work / "results.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(name, values, flush=True)


def run(*command, expected=0):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True)
    record("command", argv=list(map(str, command)), cwd=os.getcwd(), exit=result.returncode,
           stdout=result.stdout, stderr=result.stderr)
    assert result.returncode == expected, (command, result.returncode, result.stderr)
    return result


def cli(command, *rest, root=data, expected=0):
    return run(python, "-B", "-m", "app.windows_local", command, *rest, "--data-dir", root, expected=expected)


def request(path, payload=None, headers=None):
    headers = headers or {"Accept": "application/json"}
    if isinstance(payload, dict):
        headers = dict(headers, **{"Content-Type": "application/json"})
        payload = json.dumps(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(base + path, data=payload, headers=headers), timeout=10) as response:
        raw = response.read()
        return json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw


def start(root=data):
    global running_root
    running_root = root
    log = (work / ("supervisor-" + str(time.time_ns()) + ".log")).open("wb")
    process = subprocess.Popen([str(python), "-B", "-m", "app.windows_local", "start", "--no-browser",
                               "--data-dir", str(root)], cwd=install, stdout=log, stderr=log)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        assert process.poll() is None, "Supervisor failed; inspect supervisor log"
        try:
            if request("/health") == {"status": "ok"}:
                record("start", pid=process.pid, data=str(root))
                return process, log
        except (OSError, urllib.error.URLError):
            time.sleep(.3)
    raise AssertionError("Startup timeout")


def stop(process, log, root=data):
    cli("stop", root=root)
    assert process.wait(timeout=90) == 0
    log.close()
    record("stop", data=str(root))


os.chdir(work)
running = None
try:
    running = start()
    assert b'<div id="root">' in request("/", headers={"Accept": "text/html"})
    document_type = request("/document-types", {"name": "Windows synthetic smoke"})
    doc = request("/documents", {"document_type_id": document_type["id"], "number": "WINDOWS-SMOKE"})
    pdf = b"%PDF-1.4\nsynthetic EDR Windows smoke\n%%EOF\n"
    multipart = (b"--edr-boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"smoke.pdf\"\r\n"
                 b"Content-Type: application/pdf\r\n\r\n" + pdf + b"\r\n--edr-boundary--\r\n")
    uploaded = request(f"/documents/{doc['id']}/files", multipart,
                       {"Content-Type": "multipart/form-data; boundary=edr-boundary"})
    file_url = f"/documents/{doc['id']}/files/{uploaded['id']}/content"
    assert request(file_url) == pdf
    record("create_upload_download", document=doc["id"], file=uploaded["id"], sha256=hashlib.sha256(pdf).hexdigest())
    # Inspect every TCP listener owned by these two runtime processes.
    running_info = json.loads((data / "running.json").read_text())
    pg_pid = int((data / "postgres/postmaster.pid").read_text().splitlines()[0])
    listener = run("powershell.exe", "-NoProfile", "-Command",
                  f"Get-NetTCPConnection -State Listen | Where-Object {{ $_.OwningProcess -in @({running_info['pid']},{pg_pid}) }} | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json")
    listeners = json.loads(listener.stdout)
    if isinstance(listeners, dict):
        listeners = [listeners]
    assert {row["LocalPort"] for row in listeners} == {18765, 55432}
    assert all(row["LocalAddress"] == "127.0.0.1" for row in listeners)
    record("loopback_only", listeners=listeners)
    # Backup while active must refuse; no inconsistent archive is produced.
    cli("backup", work / "busy.zip", expected=1)
    assert not (work / "busy.zip").exists()
    stop(*running)
    running = start()
    assert request(f"/documents/{doc['id']}")["number"] == "WINDOWS-SMOKE"
    assert request(file_url) == pdf
    stop(*running)
    running = None
    backup = work / "backup.zip"
    cli("backup", backup)
    cli("backup", backup, expected=1)
    cli("restore", backup, expected=1)
    recovered = work / "recovered"
    cli("restore", backup, root=recovered)
    running = start(recovered)
    assert request(f"/documents/{doc['id']}")["number"] == "WINDOWS-SMOKE"
    assert request(file_url) == pdf
    stop(*running, root=recovered)
    running = None
    record("restart_backup_restore", archive=str(backup), recovered=str(recovered))
    # A real Alembic failure against the clone must leave pointer and original rows untouched.
    before = (data / "runtime.json").read_bytes()
    marker = data / "attachments/smoke-preserve.txt"
    marker.write_bytes(b"preserve")
    migration = install / "alembic/versions/ffffffffffff_smoke_failure.py"
    migration.write_text("revision='ffffffffffff'\ndown_revision='e4b8c2d16a70'\n"
                         "def upgrade():\n    from alembic import op\n    op.execute('CREATE TABLE smoke_rollback (id int)')\n"
                         "    raise RuntimeError('synthetic migration failure')\n"
                         "def downgrade():\n    pass\n", encoding="utf-8")
    try:
        cli("start", "--no-browser", expected=1)
        assert (data / "runtime.json").read_bytes() == before
        assert marker.read_bytes() == b"preserve"
    finally:
        migration.unlink()  # generated synthetic test migration only
    running = start()
    assert request(file_url) == pdf
    stop(*running)
    running = None
    record("failed_migration_preserves_original")
    # Exercise the same setup over this isolated install, then normal uninstaller.
    run(args.installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/DIR={install}", "/NOICONS", "/TASKS=", f"/LOG={work / 'update.log'}")
    assert (data / "runtime.json").read_bytes() == before
    running = start()
    assert request(file_url) == pdf
    stop(*running)
    running = None
    run(install / "unins000.exe", "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
    assert (data / "runtime.json").read_bytes() == before
    assert marker.read_bytes() == b"preserve"
    assert (data / "postgres/PG_VERSION").exists()
    record("update_uninstall_preserve_data", data=str(data))
    record("HOST_NATIVE_SMOKE_SUCCEEDED", clean_vm="NOT_RUN")
finally:
    if running is not None:
        # Preserve all test directories even on failure; only stop owned processes.
        cli("stop", root=running_root)
