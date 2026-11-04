"""Installed-runtime checks for the ephemeral GitHub-hosted Windows CI job.

Run by the *installed* bundled interpreter (``<install>/python/python.exe -B``).
Only synthetic data is created; the module uses the standard library alone.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:18765"
DOCUMENT_NUMBER = "CI-SYNTHETIC-0001"
PDF_BYTES = b"%PDF-1.4\nsynthetic EDR Windows CI attachment\n%%EOF\n"
EXPECTED_SHA256 = hashlib.sha256(PDF_BYTES).hexdigest()

parser = argparse.ArgumentParser()
parser.add_argument("--install", type=Path, required=True)
parser.add_argument("--work", type=Path, required=True)
args = parser.parse_args()

install = args.install.resolve()
work = args.work.resolve()
work.mkdir(parents=True, exist_ok=True)
python = install / "python" / "python.exe"
results_path = work / "results.json"
events = []
running = None
running_log = None
document_id = None
file_id = None


def save_results():
    results_path.write_text(json.dumps(events, indent=2), encoding="utf-8")


def record(name, **values):
    events.append(dict(check=name, **values))
    save_results()
    print(name, json.dumps(values, sort_keys=True), flush=True)


def tail(path, limit=8192):
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-limit:]
    except OSError:
        return ""


def run(argv, cwd, expected=0, **extra):
    result = subprocess.run(
        [str(item) for item in argv], cwd=str(cwd), capture_output=True, text=True
    )
    record(
        "command",
        argv=[str(item) for item in argv],
        cwd=str(cwd),
        exit=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        **extra,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"command exited {result.returncode}, expected {expected}: {argv}: {result.stderr}"
        )
    return result


def request(path, payload=None, headers=None, expect_json=True):
    request_headers = dict(headers or {"Accept": "application/json"})
    if isinstance(payload, dict):
        request_headers["Content-Type"] = "application/json"
        payload = json.dumps(payload).encode("utf-8")
    url = BASE_URL + path
    req = urllib.request.Request(url, data=payload, headers=request_headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        if expect_json and "application/json" in content_type:
            return json.loads(raw)
        return raw


def stop_app():
    result = run([python, "-B", "-m", "app.windows_local", "stop"], install)
    return result


def start_app():
    global running, running_log
    log_path = work / ("supervisor-" + str(time.time_ns()) + ".log")
    running_log = log_path.open("wb")
    running = subprocess.Popen(
        [str(python), "-B", "-m", "app.windows_local", "start", "--no-browser"],
        cwd=str(install),
        stdout=running_log,
        stderr=subprocess.STDOUT,
    )
    record("start", pid=running.pid, cwd=str(install), log=str(log_path))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if running.poll() is not None:
            record("start_failure", exit=running.returncode, supervisor_log=tail(log_path))
            raise AssertionError(f"supervisor exited during startup with {running.returncode}")
        try:
            health = request("/health")
        except (OSError, ValueError, urllib.error.URLError):
            time.sleep(0.5)
            continue
        if health == {"status": "ok"}:
            record("health", body=health, timeout_seconds=120)
            return
        time.sleep(0.5)
    record("start_timeout", supervisor_log=tail(log_path))
    raise AssertionError("startup timeout while waiting for /health")


def wait_for_stop():
    global running, running_log
    if running is None:
        return
    code = running.wait(timeout=90)
    if running_log is not None:
        running_log.close()
        running_log = None
    running = None
    if code != 0:
        raise AssertionError(f"supervisor did not stop cleanly: exit {code}")
    record("stop", exit=code)


try:
    start_app()

    ui = request("/", headers={"Accept": "text/html"}, expect_json=False)
    if not isinstance(ui, (bytes, bytearray)) or b'<div id="root">' not in ui:
        raise AssertionError("GET / did not return the React root element")
    record("ui", contains_root=True, bytes=len(ui))

    document_type = request(
        "/document-types", {"name": "CI synthetic document type"}
    )
    document = request(
        "/documents",
        {"document_type_id": document_type["id"], "number": DOCUMENT_NUMBER},
    )
    document_id = document["id"]
    record(
        "create_document",
        document_type_id=document_type["id"],
        document_id=document_id,
        number=document["number"],
    )

    boundary = "edr-ci-boundary"
    multipart = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="ci-synthetic.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("ascii")
        + PDF_BYTES
        + f"\r\n--{boundary}--\r\n".encode("ascii")
    )
    uploaded = request(
        f"/documents/{document_id}/files",
        multipart,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    file_id = uploaded["id"]
    download_url = f"/documents/{document_id}/files/{file_id}/content"
    downloaded = request(download_url, expect_json=False)
    downloaded_sha256 = hashlib.sha256(downloaded).hexdigest()
    record(
        "upload_download",
        document_id=document_id,
        file_id=file_id,
        uploaded_bytes=len(PDF_BYTES),
        uploaded_sha256=EXPECTED_SHA256,
        downloaded_sha256=downloaded_sha256,
        sha256_match=downloaded_sha256 == EXPECTED_SHA256,
    )
    if downloaded_sha256 != EXPECTED_SHA256:
        raise AssertionError(
            f"downloaded attachment SHA-256 mismatch: {downloaded_sha256} != {EXPECTED_SHA256}"
        )

    stop_app()
    wait_for_stop()

    start_app()
    persisted = request(f"/documents/{document_id}")
    if persisted.get("number") != DOCUMENT_NUMBER:
        raise AssertionError(f"document did not persist across restart: {persisted}")
    again = request(download_url, expect_json=False)
    again_sha256 = hashlib.sha256(again).hexdigest()
    record(
        "restart_persistence",
        document_id=document_id,
        file_id=file_id,
        number=persisted.get("number"),
        downloaded_sha256=again_sha256,
        sha256_unchanged=again_sha256 == EXPECTED_SHA256,
    )
    if again_sha256 != EXPECTED_SHA256:
        raise AssertionError(
            f"attachment SHA-256 changed after restart: {again_sha256} != {EXPECTED_SHA256}"
        )

    stop_app()
    wait_for_stop()
    record("CI_INSTALLER_SUCCEEDED", document_id=document_id, file_id=file_id)
except Exception as error:  # noqa: BLE001 - partial evidence must be retained
    events.append(
        {
            "check": "FAILED",
            "error": f"{type(error).__name__}: {error}",
            "document_id": document_id,
            "file_id": file_id,
        }
    )
    save_results()
    print(f"ci-installer failed: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
    exit_code = 1
else:
    exit_code = 0
finally:
    if running is not None and running.poll() is None:
        try:
            stop_app()
            running.wait(timeout=90)
        except Exception:  # noqa: BLE001 - best-effort cleanup only
            running.kill()
    if running_log is not None:
        running_log.close()

sys.exit(exit_code)
