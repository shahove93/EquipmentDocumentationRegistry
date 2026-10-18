"""HTTP tests for `GET /documents/{document_id}/files/{file_id}/content`.

The route has four jobs and no others: find the row only if it belongs to the
document, open the blob before a status code is committed to, hand the bytes
back untouched, and build a header from a filename a client chose. These tests
pin each of those down against the real database, the real local backend and a
temporary storage root, and check the negative space around the route as well —
no commit, no lock, no history, no changed row.
"""

import asyncio
import contextlib
import hashlib
import io
import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate
from app.api.files.download import (
    CHUNK_SIZE,
    DEFAULT_FILENAME,
    ClosingStreamingResponse,
    content_disposition,
    iter_blob,
)
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.dependencies import get_storage
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService
from app.services.local_storage import LocalStorageBackend
from app.services.storage import StorageError

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
MAX_BYTES = 4096
_MISSING = object()

PDF_BYTES = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
)
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
)
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x00IEND\xaeB`\x82"
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def settings(storage) -> Settings:
    """Settings rooted in the per-test storage directory."""
    return Settings(
        DATABASE_URL=DATABASE_URL,
        STORAGE_ROOT=str(storage.root_path),
        MAX_UPLOAD_SIZE_BYTES=MAX_BYTES,
    )


@pytest.fixture
def client(db, settings):
    """TestClient over the isolated schema and the temporary storage root.

    `raise_server_exceptions=False` lets the failure tests observe the response
    a client would actually get. The route answers storage failures with an
    explicit `500`, so no test relies on the framework turning an exception into
    a response.
    """
    previous_db = app.dependency_overrides.get(get_db, _MISSING)
    previous_settings = app.dependency_overrides.get(get_settings, _MISSING)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        if previous_db is _MISSING:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_db
        if previous_settings is _MISSING:
            app.dependency_overrides.pop(get_settings, None)
        else:
            app.dependency_overrides[get_settings] = previous_settings


@pytest.fixture
def make_document(db):
    """Create a document and return its id, with the session left idle."""

    def _make(status: str | None = None) -> int:
        document_type = DocumentTypeService.create(
            db, DocumentTypeCreate(name=f"Type {uuid.uuid4().hex[:12]}")
        )
        document = DocumentService.create(
            db,
            DocumentCreate(
                document_type_id=document_type.id,
                number=f"DOC-{uuid.uuid4().hex[:8]}",
            ),
        )
        if status is not None:
            document.verification_status = status
            db.commit()
        document_id = document.id
        db.rollback()
        return document_id

    return _make


@pytest.fixture
def upload(client, db):
    """POST a file as multipart, from the state a fresh request finds."""

    def _upload(
        document_id: int,
        content: bytes = PDF_BYTES,
        filename: str = "scan.pdf",
        content_type: str = "application/pdf",
    ):
        db.rollback()
        return client.post(
            f"/documents/{document_id}/files",
            files={"file": (filename, content, content_type)},
        )

    return _upload


@pytest.fixture
def download(client, db):
    """GET the content route, from the state a fresh request finds."""

    def _download(document_id: int, file_id: int):
        db.rollback()
        return client.get(f"/documents/{document_id}/files/{file_id}/content")

    return _download


@pytest.fixture
def override_storage(client):
    """Replace the download route's backend, then put the override back."""

    def _override(backend: LocalStorageBackend) -> None:
        app.dependency_overrides[get_storage] = lambda: backend

    yield _override
    app.dependency_overrides.pop(get_storage, None)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def seed_file(
    db,
    storage: LocalStorageBackend,
    document_id: int,
    *,
    data: bytes = PDF_BYTES,
    filename: str = "scan.pdf",
    mime_type: str = "application/pdf",
    size_bytes: int | None = None,
) -> int:
    """Write a blob and the row that points at it, bypassing the upload route.

    Used where the upload route cannot produce the input under test: a name with
    CR/LF, a row whose blob has been removed, a size that no longer matches the
    bytes, a blob larger than the upload limit.
    """
    storage_key = f"documents/{document_id}/{uuid.uuid4().hex}"
    storage.save(storage_key, io.BytesIO(data))
    row = File(
        document_id=document_id,
        original_filename=filename,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=len(data) if size_bytes is None else size_bytes,
        sha256=hashlib.sha256(data).hexdigest(),
        uploaded_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    file_id = row.id
    db.commit()
    db.rollback()
    return file_id


def snapshot(row: File) -> dict:
    """Copy a row's columns into plain values so later access cannot refresh them."""
    return {
        "id": row.id,
        "document_id": row.document_id,
        "original_filename": row.original_filename,
        "storage_key": row.storage_key,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "uploaded_at": row.uploaded_at,
    }


def status_of(db, document_id: int) -> str:
    document = db.get(Document, document_id)
    assert document is not None
    return document.verification_status


def events_of(db, document_id: int) -> list[DocumentVerificationEvent]:
    return list(
        db.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(DocumentVerificationEvent.id)
        )
    )


def events_snapshot(events) -> list[tuple]:
    return [
        (e.id, e.from_status, e.to_status, e.event_type, e.reason)
        for e in events
    ]


class RecordingStream:
    """A readable blob that remembers how it was read and whether it was closed."""

    def __init__(self, data: bytes) -> None:
        self._buffer = io.BytesIO(data)
        self.read_sizes: list[int] = []
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return self._buffer.read(size)

    def close(self) -> None:
        self.closed = True
        self._buffer.close()


class RecordingStorage(LocalStorageBackend):
    """A backend that serves fixed bytes and records every read request."""

    def __init__(self, root_path, data: bytes) -> None:
        super().__init__(root_path)
        self._data = data
        self.opened_keys: list[str] = []
        self.stream: RecordingStream | None = None

    def open(self, storage_key: str) -> RecordingStream:
        self.opened_keys.append(storage_key)
        self.stream = RecordingStream(self._data)
        return self.stream


class FailingStorage(LocalStorageBackend):
    """A backend whose `open` fails the way a broken store would."""

    def __init__(self, root_path, error: Exception) -> None:
        super().__init__(root_path)
        self._error = error
        self.failures = 0

    def open(self, storage_key: str):
        self.failures += 1
        raise self._error


# --------------------------------------------------------------------------- #
# 1-6: the bytes, the type, the name, the length
# --------------------------------------------------------------------------- #


class TestStoredBytes:
    @pytest.mark.parametrize(
        ("content", "filename", "declared"),
        [
            (PDF_BYTES, "passport.pdf", "application/pdf"),
            (JPEG_BYTES, "photo.jpg", "image/jpeg"),
            (PNG_BYTES, "scan.png", "image/png"),
        ],
    )
    def test_the_stored_bytes_come_back_unchanged(
        self, make_document, upload, download, content, filename, declared
    ):
        document_id = make_document()
        attached = upload(document_id, content, filename, declared)
        assert attached.status_code == 201

        response = download(document_id, attached.json()["id"])

        assert response.status_code == 200
        assert response.content == content

    @pytest.mark.parametrize(
        ("content", "filename", "declared", "expected_mime"),
        [
            (PDF_BYTES, "passport.pdf", "application/pdf", "application/pdf"),
            (JPEG_BYTES, "photo.jpg", "image/jpeg", "image/jpeg"),
            (PNG_BYTES, "scan.png", "image/png", "image/png"),
        ],
    )
    def test_content_type_is_the_mime_recorded_at_upload(
        self, make_document, upload, download, content, filename, declared,
        expected_mime,
    ):
        document_id = make_document()
        file_id = upload(document_id, content, filename, declared).json()["id"]

        response = download(document_id, file_id)

        assert response.headers["content-type"] == expected_mime

    @pytest.mark.parametrize(
        ("filename", "expected_header"),
        [
            (
                "passport.pdf",
                'attachment; filename="passport.pdf"; '
                "filename*=UTF-8''passport.pdf",
            ),
            (
                "photo.jpg",
                'attachment; filename="photo.jpg"; '
                "filename*=UTF-8''photo.jpg",
            ),
            (
                "scan.png",
                'attachment; filename="scan.png"; '
                "filename*=UTF-8''scan.png",
            ),
        ],
    )
    def test_content_disposition_is_an_attachment_with_the_name(
        self, make_document, upload, download, filename, expected_header
    ):
        document_id = make_document()
        file_id = upload(document_id, PDF_BYTES, filename).json()["id"]

        response = download(document_id, file_id)

        assert response.headers["content-disposition"] == expected_header

    def test_the_body_is_exactly_as_long_as_the_file(
        self, make_document, upload, download
    ):
        document_id = make_document()
        file_id = upload(document_id, PDF_BYTES, "passport.pdf").json()["id"]

        response = download(document_id, file_id)

        assert len(response.content) == len(PDF_BYTES)

    def test_content_length_is_not_taken_from_the_database_row(
        self, make_document, db, storage, download
    ):
        """ADR-009 leaves the header out, and a stale `size_bytes` must not lie.

        The row claims a megabyte; the blob has a few dozen bytes. If the route
        used the row, a client would either wait for bytes that never come or
        treat a complete body as truncated.
        """
        document_id = make_document()
        file_id = seed_file(db, storage, document_id, size_bytes=999_999)

        response = download(document_id, file_id)

        assert response.status_code == 200
        assert response.content == PDF_BYTES
        assert "content-length" not in response.headers

    def test_the_storage_key_never_reaches_a_header(
        self, make_document, db, storage, download
    ):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id)
        storage_key = db.get(File, file_id).storage_key
        db.rollback()

        response = download(document_id, file_id)

        assert response.status_code == 200
        assert all(storage_key not in value for value in response.headers.values())


# --------------------------------------------------------------------------- #
# 7-9: every miss is the same 404
# --------------------------------------------------------------------------- #


class TestNotFound:
    def test_an_unknown_document_is_not_found(self, client):
        response = client.get("/documents/999999/files/1/content")

        assert response.status_code == 404
        assert response.json() == {"detail": "File 1 not found for document 999999"}

    def test_an_unknown_file_is_not_found(self, client, make_document):
        document_id = make_document()

        response = client.get(f"/documents/{document_id}/files/999999/content")

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"File 999999 not found for document {document_id}"
        }

    def test_another_documents_file_is_not_found_without_naming_the_owner(
        self, make_document, upload, download
    ):
        owner_id = make_document()
        other_id = make_document()
        file_id = upload(owner_id, PDF_BYTES, "passport.pdf").json()["id"]

        response = download(other_id, file_id)

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"File {file_id} not found for document {other_id}"
        }
        assert f"document {owner_id}" not in response.text
        assert "passport.pdf" not in response.text
        assert response.headers["content-type"].startswith("application/json")

    def test_the_owner_is_not_mentioned_in_any_header(
        self, make_document, upload, download
    ):
        owner_id = make_document()
        other_id = make_document()
        file_id = upload(owner_id, PDF_BYTES, "passport.pdf").json()["id"]

        response = download(other_id, file_id)

        assert all(str(owner_id) not in value for value in response.headers.values())


# --------------------------------------------------------------------------- #
# 10-11: a row that outlived its blob
# --------------------------------------------------------------------------- #


class TestBrokenStorage:
    def test_a_missing_blob_is_a_controlled_500_not_a_404(
        self, make_document, db, storage, download, caplog
    ):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id, filename="gone.pdf")
        storage_key = db.get(File, file_id).storage_key
        db.rollback()
        storage.delete(storage_key)

        caplog.set_level(logging.ERROR, logger="app.api.files.router")
        response = download(document_id, file_id)

        assert response.status_code == 500
        assert response.json() == {"detail": "Stored file content is unavailable"}
        assert storage_key not in response.text
        assert str(storage.root_path) not in response.text
        assert "select" not in response.text.lower()

        records = [
            record
            for record in caplog.records
            if getattr(record, "operation", None) == "file.download"
        ]
        assert len(records) == 1
        assert records[0].levelno == logging.ERROR
        assert records[0].document_id == document_id
        assert records[0].file_id == file_id
        assert records[0].error_type == "StoredFileNotFoundError"

    def test_the_metadata_route_still_answers_when_only_the_blob_is_gone(
        self, make_document, db, storage, client
    ):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id)
        storage_key = db.get(File, file_id).storage_key
        db.rollback()
        storage.delete(storage_key)
        db.rollback()

        response = client.get(f"/documents/{document_id}/files/{file_id}")

        assert response.status_code == 200
        assert response.json()["id"] == file_id

    @pytest.mark.parametrize(
        ("error", "expected_type"),
        [
            (StorageError("no such key: documents/1/secret"), "StorageError"),
            (OSError("cannot read /srv/storage/documents/1/secret"), "OSError"),
        ],
    )
    def test_a_failing_open_is_a_safe_500(
        self, make_document, db, storage, download, override_storage, caplog,
        error, expected_type,
    ):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id)
        failing = FailingStorage(storage.root_path, error)
        override_storage(failing)

        caplog.set_level(logging.ERROR, logger="app.api.files.router")
        response = download(document_id, file_id)

        assert response.status_code == 500
        assert response.json() == {"detail": "Stored file content is unavailable"}
        assert failing.failures == 1
        assert "secret" not in response.text
        assert "/srv/storage" not in response.text
        records = [
            record
            for record in caplog.records
            if getattr(record, "operation", None) == "file.download"
        ]
        assert [record.error_type for record in records] == [expected_type]


# --------------------------------------------------------------------------- #
# 12-14: the filename
# --------------------------------------------------------------------------- #


class TestContentDispositionUnit:
    def test_an_ascii_name_keeps_both_forms(self):
        header = content_disposition("passport.pdf")

        assert header == (
            'attachment; filename="passport.pdf"; '
            "filename*=UTF-8''passport.pdf"
        )

    def test_a_russian_name_survives_in_filename_star(self):
        header = content_disposition("паспорт.pdf")

        assert 'filename="???????.pdf"' in header
        encoded = header.split("filename*=UTF-8''", 1)[1]
        assert encoded == "%D0%BF%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82.pdf"
        assert unquote(encoded) == "паспорт.pdf"

    def test_spaces_survive_in_both_forms(self):
        header = content_disposition("my scan.pdf")

        assert 'filename="my scan.pdf"' in header
        assert header.endswith("filename*=UTF-8''my%20scan.pdf")

    def test_quotes_are_escaped_and_encoded(self):
        header = content_disposition('report "final".pdf')

        assert 'filename="report \\"final\\".pdf"' in header
        assert header.endswith("filename*=UTF-8''report%20%22final%22.pdf")
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == (
            'report "final".pdf'
        )

    @pytest.mark.parametrize(
        "filename",
        [
            "evil\r\nX-Injected: yes.pdf",
            "line\nbreak.pdf",
            "carriage\rreturn.pdf",
            "nul\x00byte.pdf",
            "del\x7fchar.pdf",
            "c1\x85char.pdf",
        ],
    )
    def test_control_characters_never_reach_either_form(self, filename):
        header = content_disposition(filename)

        assert "\r" not in header
        assert "\n" not in header
        assert "\x00" not in header
        assert "\x7f" not in header
        assert "\x85" not in header

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("../../etc/passwd.pdf", "passwd.pdf"),
            ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
            ("/absolute/path/report.pdf", "report.pdf"),
            ("a/b/c/scan.pdf", "scan.pdf"),
        ],
    )
    def test_path_separators_are_not_part_of_the_name(self, filename, expected):
        header = content_disposition(filename)

        assert f'filename="{expected}"' in header
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == expected

    def test_a_traversal_only_name_falls_back(self):
        assert 'filename="download"' in content_disposition("../..")
        assert 'filename="download"' in content_disposition("..\\")

    @pytest.mark.parametrize(
        "filename", ["", "   ", ".", "..", "\r\n", "\x00", None, 42]
    )
    def test_an_unusable_name_falls_back(self, filename):
        header = content_disposition(filename)

        assert f'filename="{DEFAULT_FILENAME}"' in header
        assert header.endswith(f"filename*=UTF-8''{DEFAULT_FILENAME}")

    @pytest.mark.parametrize(
        "filename",
        [
            "passport.pdf",
            "паспорт.pdf",
            "my scan.pdf",
            'report "final".pdf',
            "a;b=c%d*e.pdf",
            "evil\r\nX-Injected: yes.pdf",
            "..\\..\\windows\\cmd.exe",
            "",
        ],
    )
    def test_every_header_is_ascii_because_starlette_encodes_latin_1(
        self, filename
    ):
        assert content_disposition(filename).isascii()

    def test_semicolons_and_equals_stay_inside_the_quoted_value(self):
        header = content_disposition("a;b=c.pdf")

        assert 'filename="a;b=c.pdf"' in header
        assert header.startswith("attachment; filename=")


class TestContentDispositionOverHttp:
    def test_a_russian_name_arrives_intact(self, make_document, upload, download):
        document_id = make_document()
        attached = upload(document_id, PDF_BYTES, "паспорт.pdf")
        assert attached.status_code == 201
        assert attached.json()["original_filename"] == "паспорт.pdf"

        response = download(document_id, attached.json()["id"])

        header = response.headers["content-disposition"]
        assert header.startswith("attachment; ")
        assert 'filename="???????.pdf"' in header
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == "паспорт.pdf"
        assert header.isascii()

    def test_spaces_in_the_name_survive(self, make_document, upload, download):
        document_id = make_document()
        file_id = upload(document_id, PDF_BYTES, "my scan.pdf").json()["id"]

        response = download(document_id, file_id)

        header = response.headers["content-disposition"]
        assert 'filename="my scan.pdf"' in header
        assert header.endswith("filename*=UTF-8''my%20scan.pdf")

    def test_a_stored_quote_is_escaped(self, make_document, db, storage, download):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id, filename='report "final".pdf')

        response = download(document_id, file_id)

        header = response.headers["content-disposition"]
        assert 'filename="report \\"final\\".pdf"' in header
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == (
            'report "final".pdf'
        )

    def test_crlf_in_the_stored_name_cannot_inject_a_header(
        self, make_document, db, storage, download
    ):
        document_id = make_document()
        file_id = seed_file(
            db,
            storage,
            document_id,
            filename="evil\r\nX-Injected: yes.pdf",
        )

        response = download(document_id, file_id)

        header = response.headers["content-disposition"]
        assert "\r" not in header
        assert "\n" not in header
        assert "x-injected" not in {name.lower() for name in response.headers}
        assert header.endswith("filename*=UTF-8''evilX-Injected%3A%20yes.pdf")
        assert response.status_code == 200
        assert response.content == PDF_BYTES

    @pytest.mark.parametrize(
        ("stored_name", "expected"),
        [
            ("../../etc/passwd.pdf", "passwd.pdf"),
            ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
        ],
    )
    def test_path_traversal_in_the_stored_name_is_flattened(
        self, make_document, db, storage, download, stored_name, expected
    ):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id, filename=stored_name)

        response = download(document_id, file_id)

        header = response.headers["content-disposition"]
        assert f'filename="{expected}"' in header
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == expected
        assert "/etc/" not in header
        assert "system32" not in header

    def test_special_characters_stay_in_one_header_value(
        self, make_document, db, storage, download
    ):
        document_id = make_document()
        file_id = seed_file(db, storage, document_id, filename="a;b=c%d*e.pdf")

        response = download(document_id, file_id)

        header = response.headers["content-disposition"]
        assert 'filename="a;b=c%d*e.pdf"' in header
        assert unquote(header.split("filename*=UTF-8''", 1)[1]) == "a;b=c%d*e.pdf"


# --------------------------------------------------------------------------- #
# 15-19: the download changes nothing
# --------------------------------------------------------------------------- #


class TestNoSideEffects:
    def test_status_events_and_metadata_are_unchanged(
        self, db, make_document, upload, download
    ):
        document_id = make_document(status="verified")
        file_id = upload(document_id, PDF_BYTES, "passport.pdf").json()["id"]
        db.rollback()

        before_status = status_of(db, document_id)
        before_events = events_snapshot(events_of(db, document_id))
        before_row = snapshot(db.get(File, file_id))
        assert before_events  # the upload itself reopened the document
        db.rollback()

        response = download(document_id, file_id)

        assert response.status_code == 200
        assert status_of(db, document_id) == before_status
        assert events_snapshot(events_of(db, document_id)) == before_events
        assert snapshot(db.get(File, file_id)) == before_row

    def test_other_attachments_and_their_blobs_are_untouched(
        self, db, storage, make_document, upload, download
    ):
        document_id = make_document()
        first = upload(document_id, PDF_BYTES, "first.pdf").json()
        second = upload(document_id, JPEG_BYTES, "second.jpg").json()
        db.rollback()

        second_row = snapshot(db.get(File, second["id"]))
        first_key = db.get(File, first["id"]).storage_key
        second_key = second_row["storage_key"]
        db.rollback()
        with storage.open(second_key) as handle:
            second_bytes_before = handle.read()

        assert download(document_id, first["id"]).status_code == 200

        assert snapshot(db.get(File, second["id"])) == second_row
        with storage.open(second_key) as handle:
            assert handle.read() == second_bytes_before
        assert storage.exists(first_key)

    def test_the_route_issues_one_select_without_a_lock_or_a_write(
        self, client, db, engine, make_document, upload
    ):
        document_id = make_document()
        file_id = upload(document_id, PDF_BYTES, "passport.pdf").json()["id"]
        db.rollback()

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            response = client.get(
                f"/documents/{document_id}/files/{file_id}/content"
            )
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert response.status_code == 200
        upper = [statement.upper() for statement in statements]
        selects = [statement for statement in upper if "FROM FILES" in statement]
        assert len(selects) == 1
        assert not any("FOR UPDATE" in statement for statement in upper)
        assert not any(
            statement.lstrip().startswith(
                ("INSERT", "UPDATE", "DELETE", "COMMIT", "ROLLBACK")
            )
            for statement in upper
        )

    def test_the_route_neither_commits_nor_rolls_back(
        self, client, db, make_document, upload, monkeypatch
    ):
        document_id = make_document()
        file_id = upload(document_id, PDF_BYTES, "passport.pdf").json()["id"]
        db.rollback()

        def forbidden(*args, **kwargs):
            raise AssertionError("the download route must not end the transaction")

        monkeypatch.setattr(Session, "commit", forbidden)
        monkeypatch.setattr(Session, "rollback", forbidden)

        response = client.get(f"/documents/{document_id}/files/{file_id}/content")

        assert response.status_code == 200
        assert response.content == PDF_BYTES


# --------------------------------------------------------------------------- #
# 23: streaming
# --------------------------------------------------------------------------- #


class TestStreaming:
    def test_the_blob_is_read_in_bounded_chunks_and_then_closed(
        self, client, db, storage, make_document, override_storage
    ):
        document_id = make_document()
        data = PDF_BYTES + b"x" * (3 * CHUNK_SIZE + 17)
        file_id = seed_file(db, storage, document_id, data=data)
        recorder = RecordingStorage(storage.root_path, data)
        override_storage(recorder)
        db.rollback()

        response = client.get(
            f"/documents/{document_id}/files/{file_id}/content"
        )

        assert response.status_code == 200
        assert response.content == data
        stream = recorder.stream
        assert stream is not None
        assert len(stream.read_sizes) >= 4
        assert all(size == CHUNK_SIZE for size in stream.read_sizes)
        assert stream.closed is True
        assert len(recorder.opened_keys) == 1

    def test_iter_blob_reads_one_bounded_chunk_per_call(self):
        data = b"a" * (2 * CHUNK_SIZE + 5)
        source = RecordingStream(data)

        chunks = list(iter_blob(source))

        assert b"".join(chunks) == data
        assert source.read_sizes == [CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE]
        assert source.closed is True

    def test_iter_blob_closes_the_stream_when_a_read_fails(self):
        class Broken:
            def __init__(self) -> None:
                self.closed = False
                self.calls = 0

            def read(self, size: int = -1) -> bytes:
                self.calls += 1
                if self.calls == 1:
                    return b"first"
                raise OSError("read failed")

            def close(self) -> None:
                self.closed = True

        source = Broken()
        seen: list[bytes] = []

        with pytest.raises(OSError, match="read failed"):
            for chunk in iter_blob(source):
                seen.append(chunk)

        assert seen == [b"first"]
        assert source.closed is True

    def test_iter_blob_closes_an_empty_stream(self):
        source = RecordingStream(b"")

        assert list(iter_blob(source)) == []
        assert source.read_sizes == [CHUNK_SIZE]
        assert source.closed is True


def http_scope(spec_version: str = "2.4") -> dict:
    """The minimum ASGI scope a `StreamingResponse` reads."""
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": spec_version},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/documents/1/files/1/content",
        "raw_path": b"/documents/1/files/1/content",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }


class TestStreamRelease:
    """The descriptor is released on every way a response can end.

    A `TestClient` reads the whole body and therefore only exercises the normal
    path, where the generator's `finally` already ran. These tests drive the
    ASGI call directly — a failing `send`, a `http.disconnect` signal and a
    cancelled task — which is where Starlette leaves a synchronous iterator
    suspended and only the response wrapper can still close it.
    """

    def test_a_finished_response_closes_the_stream(self):
        source = RecordingStream(PDF_BYTES)
        response = ClosingStreamingResponse(source, media_type="application/pdf")

        async def send(message):
            return None

        async def receive():
            return {"type": "http.disconnect"}

        asyncio.run(response(http_scope(), receive, send))

        assert source.closed is True

    def test_a_read_error_closes_the_stream(self):
        class BrokenStream(RecordingStream):
            def __init__(self) -> None:
                super().__init__(b"")
                self.calls = 0

            def read(self, size: int = -1) -> bytes:
                self.calls += 1
                if self.calls == 1:
                    return b"first"
                raise OSError("read failed")

        source = BrokenStream()
        response = ClosingStreamingResponse(source, media_type="application/pdf")

        async def send(message):
            return None

        async def receive():
            return {"type": "http.disconnect"}

        # Starlette turns an OSError raised by `send` or the iterator into
        # `ClientDisconnect`; the read error takes that path too.
        with pytest.raises(ClientDisconnect):
            asyncio.run(response(http_scope(), receive, send))

        assert source.closed is True

    def test_a_disconnect_while_sending_closes_the_stream(self):
        source = RecordingStream(PDF_BYTES * 100)
        response = ClosingStreamingResponse(source, media_type="application/pdf")

        async def send(message):
            if message["type"] == "http.response.body":
                raise OSError("client went away")

        async def receive():
            await asyncio.sleep(60)

        with pytest.raises(ClientDisconnect):
            asyncio.run(response(http_scope("2.4"), receive, send))

        assert source.closed is True

    def test_a_disconnect_signal_on_asgi_2_0_closes_the_stream(self):
        source = RecordingStream(b"x" * (3 * CHUNK_SIZE))
        response = ClosingStreamingResponse(source, media_type="application/pdf")

        async def send(message):
            await asyncio.sleep(0.01)

        async def receive():
            return {"type": "http.disconnect"}

        asyncio.run(response(http_scope("2.0"), receive, send))

        assert source.closed is True

    def test_a_cancelled_request_closes_the_stream(self):
        source = RecordingStream(PDF_BYTES * 1000)
        response = ClosingStreamingResponse(source, media_type="application/pdf")

        async def scenario() -> None:
            started = asyncio.Event()

            async def send(message):
                if message["type"] == "http.response.body" and message.get(
                    "body"
                ):
                    started.set()
                    await asyncio.sleep(60)

            async def receive():
                await asyncio.sleep(60)

            task = asyncio.create_task(
                response(http_scope("2.4"), receive, send)
            )
            await asyncio.wait_for(started.wait(), timeout=5)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        asyncio.run(scenario())

        assert source.closed is True


# --------------------------------------------------------------------------- #
# 20-22: OpenAPI and the neighbouring routes
# --------------------------------------------------------------------------- #


class TestOpenApiAndNeighbours:
    def test_openapi_documents_the_content_route(self):
        schema = app.openapi()
        path = "/documents/{document_id}/files/{file_id}/content"

        assert path in schema["paths"]
        assert set(schema["paths"][path]) == {"get"}
        operation = schema["paths"][path]["get"]
        assert operation["responses"]["200"]["content"] == {
            "application/pdf": {},
            "image/jpeg": {},
            "image/png": {},
        }
        assert "application/json" not in operation["responses"]["200"]["content"]

    def test_the_documented_surface_grew_by_one_route_and_one_operation(self):
        schema = app.openapi()

        assert len(schema["paths"]) == 18
        assert sum(len(item) for item in schema["paths"].values()) == 32
        assert set(
            schema["paths"]["/documents/{document_id}/files/{file_id}"]
        ) == {"get", "delete"}

    def test_list_metadata_and_upload_still_work(
        self, client, db, make_document, upload, download
    ):
        document_id = make_document()
        first = upload(document_id, PDF_BYTES, "one.pdf").json()
        second = upload(document_id, JPEG_BYTES, "two.jpg").json()
        db.rollback()

        listing = client.get(f"/documents/{document_id}/files")
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()] == [
            first["id"],
            second["id"],
        ]

        metadata = client.get(f"/documents/{document_id}/files/{first['id']}")
        assert metadata.status_code == 200
        assert metadata.json()["original_filename"] == "one.pdf"

        content = download(document_id, first["id"])
        assert content.status_code == 200
        assert content.content == PDF_BYTES

    def test_delete_is_served_on_the_metadata_path_only(
        self, client, make_document
    ):
        # TASK-DOC-005T added `DELETE .../{file_id}`, so the method is routed:
        # a missing file gets a 404 rather than the old 405. `/content` stays
        # read-only, so deleting it is still Not Allowed.
        document_id = make_document()

        assert client.delete(
            f"/documents/{document_id}/files/999999"
        ).status_code == 404
        assert client.delete(
            f"/documents/{document_id}/files/1/content"
        ).status_code == 405
