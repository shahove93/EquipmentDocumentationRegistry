import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import DEFAULT_LOG_FILE, Settings
from app.logging_config import (
    AUDIT_FIELDS,
    configure_logging,
    shutdown_logging,
)

DATABASE_URL = "postgresql+psycopg://user:secret@example.invalid:5432/dbname"
REPO_ROOT = Path(__file__).resolve().parents[1]
APP_LOGGER = logging.getLogger("app")

RESTART_SCRIPT = """
import logging
import sys

from app.logging_config import configure_logging, shutdown_logging

configure_logging(sys.argv[1])
logging.getLogger("app.subprocess").info("process %s", sys.argv[2])
shutdown_logging()
"""


@pytest.fixture(autouse=True)
def isolated_journal():
    shutdown_logging()
    yield
    shutdown_logging()


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in read_lines(path)]


def journal_handlers() -> list[logging.Handler]:
    return [
        handler
        for handler in APP_LOGGER.handlers
        if getattr(handler, "_app_journal_handler", False)
    ]


class TestLogFileSetting:
    def test_default_is_storage_logs_app_log(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
        monkeypatch.delenv("LOG_FILE", raising=False)
        assert DEFAULT_LOG_FILE == "storage/logs/app.log"
        assert Settings(_env_file=None).LOG_FILE == "storage/logs/app.log"

    def test_override_is_applied(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
        monkeypatch.setenv("LOG_FILE", "/var/log/edr/app.log")
        assert Settings(_env_file=None).LOG_FILE == "/var/log/edr/app.log"

    @pytest.mark.parametrize("value", ["", "   ", "\t"])
    def test_empty_value_is_rejected(self, monkeypatch, value):
        monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
        monkeypatch.setenv("LOG_FILE", value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_surrounding_whitespace_is_trimmed(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
        monkeypatch.setenv("LOG_FILE", "  storage/logs/app.log  ")
        assert Settings(_env_file=None).LOG_FILE == "storage/logs/app.log"

    @pytest.mark.parametrize("value", ["", "   "])
    def test_configure_rejects_empty_path(self, value):
        with pytest.raises(ValueError):
            configure_logging(value)


class TestJsonLinesFormat:
    def test_one_object_per_line_with_required_fields(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logging.getLogger("app.journal").info("first record")
        shutdown_logging()

        raw = path.read_text(encoding="utf-8")
        assert raw.endswith("\n")
        lines = raw.splitlines()
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert set(record) == {"timestamp", "level", "logger", "message"}
        assert record["level"] == "INFO"
        assert record["logger"] == "app.journal"
        assert record["message"] == "first record"

        stamp = datetime.fromisoformat(record["timestamp"])
        assert stamp.tzinfo is not None
        assert stamp.utcoffset() is not None
        assert stamp.utcoffset().total_seconds() == 0

    def test_utf8_text_is_preserved(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logging.getLogger("app.journal").error("журнал компенсаций")
        shutdown_logging()

        raw = path.read_text(encoding="utf-8")
        assert "журнал компенсаций" in raw
        assert read_records(path)[0]["message"] == "журнал компенсаций"

    def test_message_with_newline_stays_on_one_line(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logging.getLogger("app.journal").warning("first\nsecond")
        shutdown_logging()

        lines = read_lines(path)
        assert len(lines) == 1
        assert json.loads(lines[0])["message"] == "first\nsecond"

    def test_file_is_opened_in_append_mode(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        path.parent.mkdir(parents=True)
        path.write_text('{"already":"there"}\n', encoding="utf-8")

        configure_logging(path)
        logging.getLogger("app.journal").info("appended")
        shutdown_logging()

        lines = read_lines(path)
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"already": "there"}
        assert json.loads(lines[1])["message"] == "appended"

    def test_info_and_above_are_written_below_info_is_not(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logger = logging.getLogger("app.journal")
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        shutdown_logging()

        messages = [record["message"] for record in read_records(path)]
        assert messages == ["info", "warning", "error"]


class TestAuditFields:
    def test_all_audit_fields_are_written_when_present(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        values = {
            "operation": "file.attach",
            "document_id": 42,
            "storage_key": "documents/42/blob.pdf",
            "failure_category": "unknown_commit_outcome",
            "error_type": "OperationalError",
            "file_id": 7,
        }
        configure_logging(path)
        logging.getLogger("app.audit").error("audit record", extra=values)
        shutdown_logging()

        record = read_records(path)[0]
        assert {field: record[field] for field in AUDIT_FIELDS} == values

    def test_absent_audit_fields_are_not_added(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logging.getLogger("app.audit").info("plain record")
        shutdown_logging()

        record = read_records(path)[0]
        assert not set(AUDIT_FIELDS) & set(record)
        assert None not in record.values()

    def test_none_audit_fields_are_omitted(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logging.getLogger("app.audit").error(
            "partial record",
            extra={
                "operation": "file.attach",
                "document_id": None,
                "storage_key": None,
                "error_type": None,
                "file_id": None,
            },
        )
        shutdown_logging()

        record = read_records(path)[0]
        assert record["operation"] == "file.attach"
        for field in ("document_id", "storage_key", "error_type", "file_id"):
            assert field not in record


class TestNoSensitiveData:
    def test_unknown_extra_keys_are_never_written(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logging.getLogger("app.audit").error(
            "operation failed",
            extra={
                "secret": "s3cr3t-token",
                "error_text": "driver said s3cr3t-token",
                "raw_error": RuntimeError("s3cr3t-token"),
                "file_id": 3,
            },
        )
        shutdown_logging()

        raw = path.read_text(encoding="utf-8")
        record = json.loads(raw)
        assert "s3cr3t-token" not in raw
        assert "secret" not in record
        assert "error_text" not in record
        assert "raw_error" not in record
        assert record["file_id"] == 3

    def test_exception_text_and_traceback_are_not_written(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        logger = logging.getLogger("app.audit")
        try:
            raise RuntimeError("password=hunter2 in driver message")
        except RuntimeError:
            logger.error(
                "file operation failed",
                extra={"error_type": "RuntimeError"},
                exc_info=True,
            )
        shutdown_logging()

        raw = path.read_text(encoding="utf-8")
        assert "hunter2" not in raw
        assert "Traceback" not in raw
        record = json.loads(raw)
        assert record["message"] == "file operation failed"
        assert record["error_type"] == "RuntimeError"


class TestHandlerLifecycle:
    def test_repeated_configure_reuses_one_handler(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        assert len(journal_handlers()) == 1
        first = journal_handlers()[0]

        configure_logging(path)
        assert journal_handlers() == [first]

        logger = logging.getLogger("app.journal")
        logger.info("one")
        logger.info("two")
        shutdown_logging()

        assert len(read_lines(path)) == 2

    def test_reconfigure_to_another_path_replaces_the_handler(self, tmp_path):
        first_path = tmp_path / "first.log"
        second_path = tmp_path / "second.log"
        logger = logging.getLogger("app.journal")

        configure_logging(first_path)
        logger.info("first")
        configure_logging(second_path)
        logger.info("second")
        assert len(journal_handlers()) == 1
        shutdown_logging()

        assert [record["message"] for record in read_records(first_path)] == ["first"]
        assert [record["message"] for record in read_records(second_path)] == ["second"]

    def test_shutdown_closes_and_detaches_the_handler(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        configure_logging(path)
        handler = journal_handlers()[0]
        logging.getLogger("app.journal").info("before shutdown")

        shutdown_logging()
        assert journal_handlers() == []
        assert handler.stream is None

        logging.getLogger("app.journal").info("after shutdown")
        shutdown_logging()
        assert [record["message"] for record in read_records(path)] == [
            "before shutdown"
        ]


class TestRestart:
    def test_two_independent_processes_append_to_one_file(self, tmp_path):
        path = tmp_path / "logs" / "app.log"
        for marker in ("first", "second"):
            completed = subprocess.run(
                [sys.executable, "-c", RESTART_SCRIPT, str(path), marker],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            assert completed.returncode == 0, completed.stderr

        records = read_records(path)
        assert [record["message"] for record in records] == [
            "process first",
            "process second",
        ]
        assert {record["logger"] for record in records} == {"app.subprocess"}


class TestApplicationLifespan:
    def test_startup_configures_and_shutdown_closes_the_journal(
        self, tmp_path, monkeypatch
    ):
        from fastapi.testclient import TestClient

        from app.main import app

        path = tmp_path / "lifespan" / "app.log"
        monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
        monkeypatch.setenv("LOG_FILE", str(path))

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert len(journal_handlers()) == 1
            logging.getLogger("app.lifespan").info("journal is active")
            assert path.exists()

        assert journal_handlers() == []
        assert [record["message"] for record in read_records(path)] == [
            "journal is active"
        ]
