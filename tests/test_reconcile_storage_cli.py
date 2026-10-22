import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.file import File
from app.reconcile_storage import main

REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_SCHEMA = "test_file_service"


def _database_url_with_schema(engine) -> str:
    base = engine.url.render_as_string(hide_password=False)
    options = quote(f"-csearch_path={TEST_SCHEMA}", safe="")
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}options={options}"


def _env(
    tmp_path: Path,
    *,
    database_url: str | None = None,
    storage_root: Path | None = None,
    log_file: Path | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["PYTHONPATH"] = str(REPO_ROOT) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    else:
        env.pop("DATABASE_URL", None)
    env["STORAGE_ROOT"] = str(storage_root or (tmp_path / "storage"))
    env["LOG_FILE"] = str(log_file or (tmp_path / "logs" / "app.log"))
    return env


def _run(args, env, cwd):
    return subprocess.run(
        [sys.executable, "-m", "app.reconcile_storage", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def _create_document_and_file(engine, storage_key: str) -> None:
    session = Session(engine, future=True)
    try:
        document = Document(
            document_type=DocumentType(name=f"cli-type-{uuid.uuid4()}"),
            number=f"cli-number-{uuid.uuid4()}",
        )
        session.add(document)
        session.flush()
        session.add(
            File(
                document_id=document.id,
                original_filename="scan.pdf",
                storage_key=storage_key,
                mime_type="application/pdf",
                size_bytes=1,
                sha256="0" * 64,
                uploaded_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()


def _blob_key(document_id: int, extension: str = "pdf") -> str:
    return f"documents/{document_id}/{uuid.uuid4()}.{extension}"


class TestHelpAndArguments:
    def test_help_works_without_database_or_env_file(self, tmp_path):
        env = _env(tmp_path)
        storage_root = tmp_path / "storage"

        result = _run(["--help"], env, tmp_path)

        assert result.returncode == 0
        assert "usage:" in result.stdout
        assert result.stderr == ""
        assert not storage_root.exists()
        assert not (tmp_path / "logs" / "app.log").exists()

    def test_main_help_returns_zero(self, capsys):
        assert main(["--help"]) == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out
        assert captured.err == ""

    def test_unknown_argument_returns_two(self, tmp_path, capsys):
        assert main(["--unknown-option"]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "usage:" in captured.err

    def test_unknown_argument_exits_two_without_json(self, tmp_path):
        result = _run(["--unknown-option"], _env(tmp_path), tmp_path)

        assert result.returncode == 2
        assert result.stdout == ""
        assert "usage:" in result.stderr


class TestSuccessfulRun:
    def test_prints_one_json_object_and_exits_zero(
        self, engine, storage, tmp_path
    ):
        document_id = 1
        matched_key = _blob_key(document_id)
        orphan_one = _blob_key(document_id, "jpg")
        orphan_two = _blob_key(document_id, "png")
        storage.save(matched_key, io_bytes(b"matched"))
        storage.save(orphan_one, io_bytes(b"one"))
        storage.save(orphan_two, io_bytes(b"two-two"))
        storage.save(f"documents/{document_id}/notes.tmp", io_bytes(b"ignored"))
        _create_document_and_file(engine, matched_key)

        log_file = tmp_path / "logs" / "app.log"
        env = _env(
            tmp_path,
            database_url=_database_url_with_schema(engine),
            storage_root=storage.root_path,
            log_file=log_file,
        )

        result = _run([], env, REPO_ROOT)

        assert result.returncode == 0
        assert result.stderr == ""
        assert str(tmp_path) not in result.stdout
        assert "postgresql" not in result.stdout

        report = json.loads(result.stdout)
        assert report["schema_version"] == 1
        assert report["mode"] == "report_only"
        assert report["scope"] == "documents"
        assert report["status"] == "ok"
        assert report["complete"] is True
        assert report["summary"] == {
            "scanned_blobs": 3,
            "matched_blobs": 1,
            "orphan_count": 2,
            "orphan_bytes": 10,
            "ignored_regular_files": 1,
        }
        assert [orphan["storage_key"] for orphan in report["orphans"]] == sorted(
            [orphan_one, orphan_two]
        )
        assert not log_file.exists()

        with Session(engine, future=True) as session:
            rows = session.execute(
                select(File.storage_key, File.size_bytes).order_by(File.storage_key)
            ).all()
        assert rows == [(matched_key, 1)]

    def test_candidates_are_not_a_failure(self, engine, storage, tmp_path):
        storage.save(_blob_key(1), io_bytes(b"orphan"))
        env = _env(
            tmp_path,
            database_url=_database_url_with_schema(engine),
            storage_root=storage.root_path,
        )

        result = _run([], env, REPO_ROOT)

        assert result.returncode == 0
        assert json.loads(result.stdout)["summary"]["orphan_count"] == 1


class TestFailureReports:
    def test_missing_storage_root_fails_without_creating_it(
        self, engine, tmp_path
    ):
        missing_root = tmp_path / "missing-storage"
        log_file = tmp_path / "logs" / "app.log"
        env = _env(
            tmp_path,
            database_url=_database_url_with_schema(engine),
            storage_root=missing_root,
            log_file=log_file,
        )

        result = _run([], env, REPO_ROOT)

        assert result.returncode == 1
        report = json.loads(result.stdout)
        assert report["status"] == "failed"
        assert report["complete"] is False
        assert report["summary"] is None
        assert report["orphans"] is None
        assert report["error"] == {
            "code": "storage_root_missing",
            "stage": "inventory",
            "type": "StorageInventoryError",
        }
        assert "storage_root_missing" in result.stderr
        assert str(missing_root) not in result.stdout + result.stderr
        assert not missing_root.exists()
        assert not log_file.exists()

    def test_missing_database_configuration_is_a_safe_failure(self, tmp_path):
        env = _env(tmp_path)
        env.pop("DATABASE_URL", None)

        result = _run([], env, tmp_path)

        assert result.returncode == 1
        report = json.loads(result.stdout)
        assert report["status"] == "failed"
        assert report["summary"] is None
        assert report["orphans"] is None
        assert report["error"]["code"] == "configuration_error"
        assert report["error"]["stage"] == "configuration"
        assert report["error"]["type"]
        assert "configuration_error" in result.stderr
        assert str(tmp_path) not in result.stdout + result.stderr
        assert not (tmp_path / "storage").exists()
        assert not (tmp_path / "logs" / "app.log").exists()

    def test_database_connection_failure_is_a_safe_failure(self, tmp_path):
        storage_root = tmp_path / "storage"
        storage_root.mkdir()
        env = _env(
            tmp_path,
            database_url=(
                "postgresql+psycopg://edr@127.0.0.1:1/postgres"
                "?connect_timeout=1"
            ),
            storage_root=storage_root,
        )

        result = _run([], env, REPO_ROOT)

        assert result.returncode == 1
        report = json.loads(result.stdout)
        assert report["status"] == "failed"
        assert report["error"]["code"] == "database_error"
        assert report["error"]["stage"] == "database"
        assert report["error"]["type"].endswith("Error")
        assert "database_error" in result.stderr
        assert str(tmp_path) not in result.stdout + result.stderr
        assert "postgresql" not in result.stdout
        assert not (tmp_path / "logs" / "app.log").exists()

    def test_namespace_file_is_a_safe_failure(self, engine, tmp_path):
        storage_root = tmp_path / "storage"
        storage_root.mkdir()
        (storage_root / "documents").write_bytes(b"not a directory")
        env = _env(
            tmp_path,
            database_url=_database_url_with_schema(engine),
            storage_root=storage_root,
        )

        result = _run([], env, REPO_ROOT)

        assert result.returncode == 1
        report = json.loads(result.stdout)
        assert report["status"] == "failed"
        assert report["error"]["code"] == "storage_namespace_not_directory"
        assert report["error"]["stage"] == "inventory"
        assert str(tmp_path) not in result.stdout + result.stderr
        assert not (tmp_path / "logs" / "app.log").exists()


def io_bytes(payload: bytes):
    import io

    return io.BytesIO(payload)
