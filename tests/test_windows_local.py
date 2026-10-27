"""Portable safety checks; real native lifecycle is exercised by smoke.ps1."""
import io
import json
from pathlib import Path
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.local_web import LocalWeb
from app.windows_local import (
    API_PORT, Busy, Runtime, atomic_json, checked_data, digest, exclusive,
    restore, unpack_backup,
    postgres_path,
)


def archive(tmp_path, name="attachments/documents/1/test.pdf", data=b"%PDF-test", sha=None):
    import hashlib
    result = tmp_path / "backup.zip"
    files = {"database.dump": b"PGDMP-test", name: data}
    manifest = {"format": 1, "postgres_major": "18", "revision": "head", "files": {
        key: {"size": len(value), "sha256": hashlib.sha256(value).hexdigest()}
        for key, value in files.items()
    }}
    if sha:
        manifest["files"][name]["sha256"] = sha
    with zipfile.ZipFile(result, "w") as output:
        for key, value in files.items():
            output.writestr(key, value)
        output.writestr("manifest.json", json.dumps(manifest))
    return result


def test_lock_excludes_start_and_maintenance(tmp_path):
    data = tmp_path / "data"
    with exclusive(data):
        with pytest.raises(Busy):
            with exclusive(data):
                pytest.fail("two owners")
    assert not data.exists()
    with exclusive(data):
        pass


@pytest.mark.parametrize("relative", ["install", "install/data", "."])
def test_data_cannot_overlap_installation(tmp_path, relative):
    with pytest.raises(ValueError):
        checked_data(tmp_path / relative, tmp_path / "install")


def test_archive_roundtrip_validates_dump_and_files(tmp_path):
    source = archive(tmp_path)
    stage = tmp_path / "stage"
    manifest = unpack_backup(source, stage)
    assert (stage / "database.dump").read_bytes() == b"PGDMP-test"
    assert (stage / "attachments/documents/1/test.pdf").read_bytes() == b"%PDF-test"
    assert manifest["files"]["database.dump"]["sha256"] == digest(stage / "database.dump")


@pytest.mark.parametrize("path", ["attachments/../../outside", "attachments/C:/x", "attachments/a\\b",
                                    "/attachments/x", "attachments/x.", "attachments//x", "attachments/CON"])
def test_restore_rejects_unsafe_paths(tmp_path, path):
    with pytest.raises(ValueError):
        unpack_backup(archive(tmp_path, path), tmp_path / "stage")
    assert not (tmp_path / "outside").exists()


def test_restore_rejects_corruption(tmp_path):
    with pytest.raises(ValueError, match="checksum"):
        unpack_backup(archive(tmp_path, sha="0" * 64), tmp_path / "stage")


def test_restore_never_overwrites_existing_data(tmp_path):
    target = tmp_path / "data"
    target.mkdir()
    original = target / "important.txt"
    original.write_bytes(b"must survive")
    with pytest.raises(ValueError, match="empty/new"):
        restore(tmp_path / "nonexistent.zip", target)
    assert original.read_bytes() == b"must survive"


def test_failed_migration_preserves_active_database(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    data = tmp_path / "data"
    data.mkdir()
    runtime = Runtime(data)
    runtime.config = {"password": "secret", "active": "original", "revision": "old"}
    atomic_json(data / "runtime.json", runtime.config)
    calls = []
    monkeypatch.setattr(runtime, "run", lambda *args, **kwargs: calls.append(args))
    monkeypatch.setattr(runtime, "configure_app", lambda database: None)
    monkeypatch.setattr(ScriptDirectory, "get_current_head", lambda self: "new")
    def fail(*args):
        raise RuntimeError("synthetic migration failure")
    monkeypatch.setattr(command, "upgrade", fail)
    before = (data / "runtime.json").read_bytes()
    with pytest.raises(RuntimeError, match="synthetic"):
        runtime.migrate()
    assert (data / "runtime.json").read_bytes() == before
    assert runtime.config["active"] == "original"
    assert calls[0][:3] == ("createdb", "--template", "original")
    assert not any(call[0] == "dropdb" for call in calls)


def test_successful_migration_activates_only_after_upgrade(tmp_path, monkeypatch):
    from alembic import command
    from alembic.script import ScriptDirectory
    data = tmp_path / "data"
    data.mkdir()
    runtime = Runtime(data)
    runtime.config = {"password": "secret", "active": "original", "revision": "old"}
    atomic_json(data / "runtime.json", runtime.config)
    monkeypatch.setattr(runtime, "run", lambda *args: None)
    monkeypatch.setattr(runtime, "configure_app", lambda database: None)
    monkeypatch.setattr(ScriptDirectory, "get_current_head", lambda self: "new")
    def upgrade(*args):
        assert json.loads((data / "runtime.json").read_text())["active"] == "original"
    monkeypatch.setattr(command, "upgrade", upgrade)
    runtime.migrate()
    assert runtime.config["revision"] == "new"
    assert runtime.config["active"].startswith("edr_")
    assert json.loads((data / "runtime.json").read_text()) == runtime.config


@pytest.fixture
def browser(tmp_path):
    ui = tmp_path / "ui"
    (ui / "assets").mkdir(parents=True)
    (ui / "index.html").write_text("<html>React production shell</html>")
    (ui / "assets/app.js").write_text("// bundled")
    api = FastAPI()
    @api.get("/documents/{document_id}")
    def document(document_id: int):
        return {"id": document_id}
    @api.get("/documents/{document_id}/files/{file_id}/content")
    def download(document_id: int, file_id: int):
        return {"file": file_id}
    with TestClient(LocalWeb(api, ui, API_PORT), base_url=f"http://127.0.0.1:{API_PORT}") as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/materials", "/batches", "/documents/new", "/documents/123"])
def test_direct_browser_navigation_gets_spa(browser, path):
    assert "React production shell" in browser.get(path, headers={"Accept": "text/html"}).text


def test_json_and_download_routes_are_not_swallowed(browser):
    assert browser.get("/documents/123", headers={"Accept": "application/json"}).json() == {"id": 123}
    assert browser.get("/documents/123/files/7/content", headers={"Accept": "text/html"}).json() == {"file": 7}
    assert browser.get("/assets/app.js").text == "// bundled"
    assert browser.get("/assets/absent.js").status_code == 404


@pytest.mark.parametrize("headers", [{"Host": "attacker.test"}, {"Origin": "https://attacker.test"},
                                     {"Sec-Fetch-Site": "cross-site"}])
def test_cross_origin_browser_requests_are_denied(browser, headers):
    assert browser.get("/documents/123", headers=headers).status_code == 403


def test_backup_refuses_existing_or_internal_destination(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    runtime = Runtime(data)
    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"prior backup")
    for path in (existing, data / "bad.zip"):
        with pytest.raises(ValueError):
            runtime.backup(path)
    assert existing.read_bytes() == b"prior backup"


@pytest.mark.parametrize("content,size,sha", [(b"different", 9, "0" * 64), (b"short", 10, "0" * 64)])
def test_backup_pair_validation_refuses_corrupt_content(tmp_path, monkeypatch, content, size, sha):
    data = tmp_path / "data"
    blob = data / "attachments/documents/1/test.pdf"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(content)
    runtime = Runtime(data)
    monkeypatch.setattr(runtime, "query", lambda *args: [("documents/1/test.pdf", size, sha)])
    with pytest.raises(ValueError, match="incomplete or corrupt"):
        runtime.validate_pair("original")
    assert blob.read_bytes() == content


def test_restore_corruption_keeps_target_absent(tmp_path):
    target = tmp_path / "restored"
    with pytest.raises(ValueError, match="checksum"):
        restore(archive(tmp_path, sha="0" * 64), target)
    assert not target.exists()


def test_restore_rejects_unlisted_archive_entries(tmp_path):
    source = archive(tmp_path)
    with zipfile.ZipFile(source, "a") as output:
        output.writestr("extra", b"unlisted")
    with pytest.raises(ValueError, match="Incomplete"):
        unpack_backup(source, tmp_path / "stage")


def test_start_does_not_adopt_unrelated_nonempty_directory(tmp_path):
    data = tmp_path / "foreign"
    data.mkdir()
    original = data / "unrelated.txt"
    original.write_bytes(b"keep")
    with pytest.raises(ValueError, match="nonempty"):
        Runtime(data).initialize()
    assert list(data.iterdir()) == [original]
    assert original.read_bytes() == b"keep"


def test_postgres_paths_preserve_file_identity(tmp_path):
    import os
    source = tmp_path / "Кириллица with spaces"
    source.mkdir()
    existing = source / "existing.txt"
    existing.write_bytes(b"identity")
    try:
        translated = postgres_path(existing)
    except ValueError:
        # An NTFS volume with 8.3 disabled must fail safely, not feed ANSI paths to PG.
        assert os.name == "nt"
        assert existing.read_bytes() == b"identity"
        return
    assert Path(translated).read_bytes() == b"identity"
    future = postgres_path(source / "new-directory" / "file.dump")
    assert Path(future).name == "file.dump"
    if os.name == "nt":
        assert translated.isascii() and future.isascii()
