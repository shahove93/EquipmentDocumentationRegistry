import json
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_type import DocumentType
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.local_storage import LocalStorageBackend, StorageInventoryError, StoredFileInfo
from app.services.storage_reconciliation import (
    is_canonical_storage_key,
    reconcile_storage,
)


def blob_key(document_id: int, extension: str = "pdf") -> str:
    return f"documents/{document_id}/{uuid.uuid4()}.{extension}"


@pytest.fixture
def document_id(engine):
    creator = Session(engine, future=True, expire_on_commit=False)
    try:
        document = Document(
            document_type=DocumentType(name=f"type-{uuid.uuid4()}"),
            number=f"number-{uuid.uuid4()}",
        )
        creator.add(document)
        creator.commit()
        return document.id
    finally:
        creator.close()


def add_file_row(engine, document_id: int, storage_key: str, size_bytes: int = 1):
    session = Session(engine, future=True)
    try:
        session.add(
            File(
                document_id=document_id,
                original_filename="scan.pdf",
                storage_key=storage_key,
                mime_type="application/pdf",
                size_bytes=size_bytes,
                sha256="0" * 64,
                uploaded_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()


@pytest.fixture
def log_file(tmp_path):
    return tmp_path / "logs" / "app.log"


def run(storage, engine, log_file):
    return reconcile_storage(engine, storage, log_file=log_file)


class TestCanonicalKey:
    @pytest.mark.parametrize(
        "key",
        [
            f"documents/0/{uuid.uuid4()}.pdf",
            f"documents/1/{uuid.uuid4()}.jpg",
            f"documents/42/{uuid.uuid4()}.png",
            f"documents/999999/{uuid.uuid4()}.pdf",
        ],
    )
    def test_accepts_canonical_keys(self, key):
        assert is_canonical_storage_key(key) is True

    @pytest.mark.parametrize(
        "key",
        [
            f"documents/01/{uuid.uuid4()}.pdf",
            f"documents/-1/{uuid.uuid4()}.pdf",
            f"documents/+1/{uuid.uuid4()}.pdf",
            f"documents/one/{uuid.uuid4()}.pdf",
            f"documents/1/{str(uuid.uuid4()).upper()}.pdf",
            f"documents/1/{uuid.uuid4().hex}.pdf",
            f"documents/1/{{{uuid.uuid4()}}}.pdf",
            f"documents/1/{uuid.uuid4()}.PDF",
            f"documents/1/{uuid.uuid4()}.jpeg",
            f"documents/1/{uuid.uuid4()}.pdf.tmp",
            f"documents/1/{uuid.uuid4()}.pdf.part",
            f"documents/1/nested/{uuid.uuid4()}.pdf",
            f"documents/{uuid.uuid4()}.pdf",
            f"other/1/{uuid.uuid4()}.pdf",
            f"/documents/1/{uuid.uuid4()}.pdf",
            f"documents\\1\\{uuid.uuid4()}.pdf",
            "",
            42,
        ],
    )
    def test_rejects_non_canonical_keys(self, key):
        assert is_canonical_storage_key(key) is False


class TestReportContract:
    def test_empty_storage_is_a_successful_empty_report(
        self, storage, engine, log_file
    ):
        storage.root_path.mkdir(parents=True)

        report = run(storage, engine, log_file)

        assert report["schema_version"] == 1
        assert report["mode"] == "report_only"
        assert report["scope"] == "documents"
        assert report["status"] == "ok"
        assert report["complete"] is True
        assert report["summary"] == {
            "scanned_blobs": 0,
            "matched_blobs": 0,
            "orphan_count": 0,
            "orphan_bytes": 0,
            "ignored_regular_files": 0,
        }
        assert report["orphans"] == []
        assert "error" not in report
        datetime.fromisoformat(report["started_at"])
        datetime.fromisoformat(report["finished_at"])

    def test_missing_documents_namespace_after_successful_select(
        self, storage, engine, log_file
    ):
        storage.root_path.mkdir(parents=True)
        statements = []

        def record(conn, cursor, statement, params, context, executemany):
            statements.append(statement)

        sa_event.listen(engine, "before_cursor_execute", record)
        try:
            report = run(storage, engine, log_file)
        finally:
            sa_event.remove(engine, "before_cursor_execute", record)

        assert report["status"] == "ok"
        assert report["summary"]["scanned_blobs"] == 0
        assert len([s for s in statements if "FROM files" in s]) == 1

    def test_matches_by_full_key_and_reports_orphans(
        self, storage, engine, log_file, document_id
    ):
        matched_key = blob_key(document_id)
        orphan_key = blob_key(document_id)
        zero_key = blob_key(document_id, "png")
        storage.save(matched_key, io_bytes(b"matched"))
        storage.save(orphan_key, io_bytes(b"orphan!"))
        storage.save(zero_key, io_bytes(b""))
        storage.save(f"documents/{document_id}/notes.tmp", io_bytes(b"ignored"))
        add_file_row(engine, document_id, matched_key)

        report = run(storage, engine, log_file)

        assert report["status"] == "ok"
        assert report["summary"] == {
            "scanned_blobs": 3,
            "matched_blobs": 1,
            "orphan_count": 2,
            "orphan_bytes": 7,
            "ignored_regular_files": 1,
        }
        assert [orphan["storage_key"] for orphan in report["orphans"]] == sorted(
            [orphan_key, zero_key]
        )
        assert set(report["orphans"][0]) == {
            "storage_key",
            "size_bytes",
            "modified_at",
        }
        for orphan in report["orphans"]:
            datetime.fromisoformat(orphan["modified_at"])

    def test_same_basename_in_another_document_is_not_matched(
        self, storage, engine, log_file, document_id
    ):
        name = f"{uuid.uuid4()}.pdf"
        listed_key = f"documents/{document_id}/{name}"
        other_key = f"documents/{document_id + 1}/{name}"
        storage.save(listed_key, io_bytes(b"listed"))
        storage.save(other_key, io_bytes(b"other"))
        add_file_row(engine, document_id, listed_key)

        report = run(storage, engine, log_file)

        assert report["summary"]["matched_blobs"] == 1
        assert report["summary"]["orphan_count"] == 1
        assert report["orphans"][0]["storage_key"] == other_key

    def test_zero_byte_canonical_blob_is_a_candidate(
        self, storage, engine, log_file
    ):
        key = blob_key(1)
        storage.save(key, io_bytes(b""))

        report = run(storage, engine, log_file)

        assert report["summary"]["scanned_blobs"] == 1
        assert report["summary"]["matched_blobs"] == 0
        assert report["summary"]["orphan_count"] == 1
        assert report["summary"]["orphan_bytes"] == 0
        assert report["orphans"] == [
            {
                "storage_key": key,
                "size_bytes": 0,
                "modified_at": report["orphans"][0]["modified_at"],
            }
        ]

    def test_log_file_is_excluded_even_when_it_looks_canonical(
        self, storage, engine, tmp_path
    ):
        log_path = storage.root_path / "documents" / "1" / f"{uuid.uuid4()}.pdf"
        storage.save(f"documents/1/{uuid.uuid4()}.pdf", io_bytes(b"real"))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_bytes(b"journal")

        report = run(storage, engine, log_path)

        assert report["summary"]["scanned_blobs"] == 1
        assert report["summary"]["ignored_regular_files"] == 0
        assert len(report["orphans"]) == 1
        assert report["orphans"][0]["storage_key"] != log_path.relative_to(
            storage.root_path
        ).as_posix()

    def test_classifies_ignored_regular_files(
        self, storage, engine, log_file, document_id
    ):
        good = blob_key(document_id)
        storage.save(good, io_bytes(b""))
        storage.save(f"documents/{document_id}/notes.txt", io_bytes(b"1"))
        storage.save(f"documents/{document_id}/{uuid.uuid4()}.PDF", io_bytes(b"2"))
        storage.save(f"documents/0{document_id}/{uuid.uuid4()}.pdf", io_bytes(b"3"))
        storage.save(
            f"documents/{document_id}/{str(uuid.uuid4()).upper()}.pdf",
            io_bytes(b"4"),
        )
        storage.save(
            f"documents/{document_id}/nested/{uuid.uuid4()}.pdf", io_bytes(b"5")
        )
        storage.save(f"documents/{document_id}/app.log.tmp", io_bytes(b"6"))
        storage.save(f"documents/{document_id}/{uuid.uuid4()}.pdf.part", io_bytes(b"7"))
        (storage.root_path / "documents" / str(document_id) / "sub").mkdir()
        os.symlink(
            storage.root_path / "documents" / str(document_id) / "notes.txt",
            storage.root_path / "documents" / str(document_id) / "link.pdf",
        )

        report = run(storage, engine, log_file)

        assert report["summary"] == {
            "scanned_blobs": 1,
            "matched_blobs": 0,
            "orphan_count": 1,
            "orphan_bytes": 0,
            "ignored_regular_files": 7,
        }
        assert report["orphans"][0]["storage_key"] == good

    def test_orphans_are_sorted_by_storage_key(self, storage, engine, log_file):
        keys = [blob_key(3), blob_key(1), blob_key(2)]
        for key in keys:
            storage.save(key, io_bytes(key.encode()))

        report = run(storage, engine, log_file)

        assert [orphan["storage_key"] for orphan in report["orphans"]] == sorted(keys)


class TestDatabaseInteraction:
    def test_inventory_finishes_before_one_select_in_its_own_connection(
        self, storage, engine, log_file, monkeypatch
    ):
        storage.save(blob_key(1), io_bytes(b"one"))
        storage.save(blob_key(2), io_bytes(b"two"))
        inventory_finished = {"value": False}
        original = storage.iter_files

        def wrapped_iter_files(prefix):
            yield from original(prefix)
            inventory_finished["value"] = True

        monkeypatch.setattr(storage, "iter_files", wrapped_iter_files)

        statements = []
        checkouts = []

        def before_cursor(conn, cursor, statement, params, context, executemany):
            assert inventory_finished["value"] is True
            statements.append(statement)

        def on_checkout(*args, **kwargs):
            checkouts.append(1)

        sa_event.listen(engine, "before_cursor_execute", before_cursor)
        sa_event.listen(engine, "checkout", on_checkout)
        try:
            report = run(storage, engine, log_file)
        finally:
            sa_event.remove(engine, "before_cursor_execute", before_cursor)
            sa_event.remove(engine, "checkout", on_checkout)

        assert report["status"] == "ok"
        assert len(checkouts) == 1
        assert len(statements) == 1
        assert statements[0].lstrip().upper().startswith("SELECT")
        assert "FILES" in statements[0].upper()
        assert not any(
            word in statements[0].upper()
            for word in ("INSERT", "UPDATE", "DELETE", "FOR UPDATE")
        )

    def test_select_runs_even_with_empty_inventory(
        self, storage, engine, log_file
    ):
        storage.root_path.mkdir(parents=True)
        statements = []

        def before_cursor(conn, cursor, statement, params, context, executemany):
            statements.append(statement)

        sa_event.listen(engine, "before_cursor_execute", before_cursor)
        try:
            report = run(storage, engine, log_file)
        finally:
            sa_event.remove(engine, "before_cursor_execute", before_cursor)

        assert report["status"] == "ok"
        assert len(statements) == 1
        assert "FROM files" in statements[0]

    def test_database_failure_is_a_safe_failed_report(self, storage, engine, log_file):
        storage.root_path.mkdir(parents=True)

        class FailingEngine:
            def connect(self):
                raise OperationalError(
                    "SELECT storage_key FROM files",
                    {"password": "secret"},
                    Exception("secret connection details"),
                )

        report = reconcile_storage(FailingEngine(), storage, log_file=log_file)
        serialized = json.dumps(report)

        assert report["status"] == "failed"
        assert report["complete"] is False
        assert report["summary"] is None
        assert report["orphans"] is None
        assert report["error"] == {
            "code": "database_error",
            "stage": "database",
            "type": "OperationalError",
        }
        assert "secret" not in serialized
        assert "SELECT" not in serialized

    def test_partial_inventory_never_returns_partial_orphans(
        self, storage, engine, log_file, monkeypatch
    ):
        leaked = "/absolute/secret/path"

        def broken_iter_files(prefix):
            yield StoredFileInfo(
                storage_key=blob_key(1),
                size_bytes=1,
                modified_at=datetime.now(timezone.utc),
            )
            raise StorageInventoryError("storage_walk_failed", leaked)

        monkeypatch.setattr(storage, "iter_files", broken_iter_files)
        statements = []

        def before_cursor(conn, cursor, statement, params, context, executemany):
            statements.append(statement)

        sa_event.listen(engine, "before_cursor_execute", before_cursor)
        try:
            report = run(storage, engine, log_file)
        finally:
            sa_event.remove(engine, "before_cursor_execute", before_cursor)

        assert report["status"] == "failed"
        assert report["summary"] is None
        assert report["orphans"] is None
        assert report["error"]["code"] == "storage_walk_failed"
        assert report["error"]["stage"] == "inventory"
        assert statements == []
        assert leaked not in json.dumps(report)


class TestReadOnlyBehaviour:
    def test_files_database_blobs_and_journal_are_unchanged(
        self, storage, engine, log_file, document_id
    ):
        matched_key = blob_key(document_id)
        orphan_key = blob_key(document_id)
        storage.save(matched_key, io_bytes(b"matched"))
        storage.save(orphan_key, io_bytes(b"orphan"))
        add_file_row(engine, document_id, matched_key)
        log_file.parent.mkdir(parents=True)
        log_file.write_text("journal-before\n", encoding="utf-8")

        with Session(engine, future=True) as session:
            files_before = session.execute(
                select(File.id, File.storage_key, File.size_bytes, File.sha256)
                .order_by(File.id)
            ).all()
            documents_before = session.execute(
                select(Document.id, Document.verification_status).order_by(Document.id)
            ).all()
            events_before = session.scalar(
                select(func.count()).select_from(DocumentVerificationEvent)
            )

        blob_path = storage.root_path / orphan_key
        blob_before = blob_path.read_bytes()
        mtime_before = blob_path.stat().st_mtime_ns
        journal_before = log_file.read_bytes()

        first = run(storage, engine, log_file)
        second = run(storage, engine, log_file)

        assert first["summary"] == second["summary"]
        assert first["orphans"] == second["orphans"]
        assert blob_path.read_bytes() == blob_before
        assert blob_path.stat().st_mtime_ns == mtime_before
        assert log_file.read_bytes() == journal_before

        with Session(engine, future=True) as session:
            files_after = session.execute(
                select(File.id, File.storage_key, File.size_bytes, File.sha256)
                .order_by(File.id)
            ).all()
            documents_after = session.execute(
                select(Document.id, Document.verification_status).order_by(Document.id)
            ).all()
            events_after = session.scalar(
                select(func.count()).select_from(DocumentVerificationEvent)
            )

        assert files_after == files_before
        assert documents_after == documents_before
        assert events_after == events_before

    def test_does_not_create_root_or_journal(self, tmp_path, engine):
        root = tmp_path / "storage"
        storage = LocalStorageBackend(root_path=root)
        log_file = tmp_path / "logs" / "app.log"

        report = run(storage, engine, log_file)

        assert report["status"] == "failed"
        assert not root.exists()
        assert not log_file.exists()
        assert report["error"]["code"] == "storage_root_missing"


def io_bytes(payload: bytes):
    import io

    return io.BytesIO(payload)
