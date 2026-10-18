"""HTTP tests for `DELETE /documents/{document_id}/files/{file_id}`.

The route is an adapter over `FileService.detach`: it adds no SQL, no session
and no transaction of its own, and turns four domain errors into status codes.
These tests therefore pin the adapter's responsibilities — the `204`, the empty
body, the error mapping, and the absence of any work the service already does —
while checking the service's own guarantees (status, history, blob timing)
through the HTTP surface.
"""

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.dependencies import get_file_service
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService
from app.services.file_service import (
    FileService,
    PendingDocumentChangesError,
    TransactionAlreadyOpenError,
)
from app.services.local_storage import LocalStorageBackend

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
MAX_BYTES = 4096
_MISSING = object()

PDF_BYTES = (
    b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
)
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def settings(storage) -> Settings:
    return Settings(
        DATABASE_URL=DATABASE_URL,
        STORAGE_ROOT=str(storage.root_path),
        MAX_UPLOAD_SIZE_BYTES=MAX_BYTES,
    )


@pytest.fixture
def client(db, settings):
    """TestClient over the isolated schema and the temporary storage root.

    `raise_server_exceptions=False` is required by the failure tests: an
    uncaught commit error must be observed as the framework's `500`, which is
    what a client would see.
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
    def _download(document_id: int, file_id: int):
        db.rollback()
        return client.get(f"/documents/{document_id}/files/{file_id}/content")

    return _download


@pytest.fixture
def delete(client, db):
    """DELETE an attachment from the session state a fresh request finds.

    `reset=False` is for the mid-transaction test, which needs the session to
    still be in the transaction it opened.
    """

    def _delete(document_id: int, file_id: int, *, reset: bool = True):
        if reset:
            db.rollback()
        return client.delete(f"/documents/{document_id}/files/{file_id}")

    return _delete


@pytest.fixture
def override_service(client):
    """Replace the assembled service, then put the override back."""

    def _override(service) -> None:
        app.dependency_overrides[get_file_service] = lambda: service

    yield _override
    app.dependency_overrides.pop(get_file_service, None)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def set_status(db, document_id: int, value: str) -> None:
    """Set a verdict without producing a history event of its own.

    Used to build "a verified document with a file" without the upload that
    would otherwise leave a `reopened(file_added)` behind and make a later
    `file_deleted` indistinguishable from it.
    """
    document = db.get(Document, document_id)
    assert document is not None
    document.verification_status = value
    db.commit()
    db.rollback()


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


def event_tuples(events) -> list[tuple]:
    return [
        (e.from_status, e.to_status, e.event_type, e.reason) for e in events
    ]


def snapshot(row: File) -> dict:
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


def key_of(db, file_id: int) -> str:
    row = db.get(File, file_id)
    assert row is not None
    key = row.storage_key
    db.rollback()
    return key


class RecordingService:
    """A service stand-in that records the call and touches nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def detach(self, document_id: int, file_id: int) -> None:
        self.calls.append((document_id, file_id))


class RaisingService:
    """A service stand-in that raises one chosen domain error."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls: list[tuple[int, int]] = []

    def detach(self, document_id: int, file_id: int) -> None:
        self.calls.append((document_id, file_id))
        raise self.error


class FailingDeleteStorage(LocalStorageBackend):
    """A backend that reads and writes normally but cannot delete."""

    def delete(self, storage_key: str) -> None:
        raise OSError("cannot remove the blob")


# --------------------------------------------------------------------------- #
# 1-7: the successful delete
# --------------------------------------------------------------------------- #


class TestSuccessfulDelete:
    def test_delete_returns_204(self, make_document, upload, delete):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]

        response = delete(document_id, file_id)

        assert response.status_code == 204

    def test_the_response_has_no_body(self, make_document, upload, delete):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]

        response = delete(document_id, file_id)

        assert response.content == b""
        assert "content-type" not in response.headers
        assert response.text == ""

    def test_the_file_disappears_from_the_list(
        self, client, make_document, upload, delete
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]

        assert delete(document_id, file_id).status_code == 204

        listing = client.get(f"/documents/{document_id}/files")
        assert listing.status_code == 200
        assert listing.json() == []

    def test_the_metadata_is_gone(self, client, make_document, upload, delete):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]

        assert delete(document_id, file_id).status_code == 204

        response = client.get(f"/documents/{document_id}/files/{file_id}")
        assert response.status_code == 404
        assert response.json() == {
            "detail": f"File {file_id} not found for document {document_id}"
        }

    def test_the_content_is_gone(self, make_document, upload, delete, download):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]

        assert delete(document_id, file_id).status_code == 204

        response = download(document_id, file_id)
        assert response.status_code == 404

    def test_the_blob_is_removed_after_the_commit(
        self, db, storage, make_document, upload, delete
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        storage_key = key_of(db, file_id)
        assert storage.exists(storage_key)

        assert delete(document_id, file_id).status_code == 204

        assert not storage.exists(storage_key)
        assert db.get(File, file_id) is None

    def test_the_last_file_can_be_deleted(
        self, client, db, make_document, upload, delete
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]

        assert delete(document_id, file_id).status_code == 204

        assert client.get(f"/documents/{document_id}/files").json() == []
        assert status_of(db, document_id) == "pending"


# --------------------------------------------------------------------------- #
# 8-11: every miss is the same 404
# --------------------------------------------------------------------------- #


class TestNotFound:
    def test_an_unknown_document_is_not_found(self, client):
        response = client.delete("/documents/999999/files/1")

        assert response.status_code == 404
        assert response.json() == {"detail": "Document 999999 not found"}

    def test_an_unknown_file_is_not_found(self, client, make_document):
        document_id = make_document()

        response = client.delete(f"/documents/{document_id}/files/999999")

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"File 999999 not found for document {document_id}"
        }

    def test_another_documents_file_is_not_found(
        self, db, storage, make_document, upload, delete
    ):
        owner_id = make_document()
        other_id = make_document()
        file_id = upload(owner_id, PDF_BYTES, "passport.pdf").json()["id"]
        storage_key = key_of(db, file_id)
        owner_before = snapshot(db.get(File, file_id))
        db.rollback()

        response = delete(other_id, file_id)

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"File {file_id} not found for document {other_id}"
        }
        assert f"document {owner_id}" not in response.text
        assert "passport.pdf" not in response.text
        assert snapshot(db.get(File, file_id)) == owner_before
        assert storage.exists(storage_key)

    def test_a_second_delete_is_not_found(self, make_document, upload, delete):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        assert delete(document_id, file_id).status_code == 204

        response = delete(document_id, file_id)

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"File {file_id} not found for document {document_id}"
        }


# --------------------------------------------------------------------------- #
# 12-15: status and history
# --------------------------------------------------------------------------- #


class TestStatusAndHistory:
    def test_a_pending_document_gets_no_event(
        self, db, make_document, upload, delete
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        assert status_of(db, document_id) == "pending"
        assert events_of(db, document_id) == []

        assert delete(document_id, file_id).status_code == 204

        assert status_of(db, document_id) == "pending"
        assert events_of(db, document_id) == []

    @pytest.mark.parametrize("verdict", ["verified", "rejected"])
    def test_a_decided_document_reopens_once(
        self, db, make_document, upload, delete, verdict
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        set_status(db, document_id, verdict)

        assert delete(document_id, file_id).status_code == 204

        assert status_of(db, document_id) == "pending"
        assert event_tuples(events_of(db, document_id)) == [
            (verdict, "pending", "reopened", "file_deleted")
        ]

    def test_deleting_several_files_does_not_repeat_the_event(
        self, db, make_document, upload, delete
    ):
        document_id = make_document()
        first = upload(document_id, PDF_BYTES, "first.pdf").json()["id"]
        second = upload(document_id, JPEG_BYTES, "second.jpg").json()["id"]
        set_status(db, document_id, "verified")

        assert delete(document_id, first).status_code == 204
        assert status_of(db, document_id) == "pending"
        assert len(events_of(db, document_id)) == 1

        assert delete(document_id, second).status_code == 204
        assert status_of(db, document_id) == "pending"
        assert event_tuples(events_of(db, document_id)) == [
            ("verified", "pending", "reopened", "file_deleted")
        ]


# --------------------------------------------------------------------------- #
# 16: nothing else moves
# --------------------------------------------------------------------------- #


class TestIsolation:
    def test_another_document_and_its_file_are_untouched(
        self, db, storage, make_document, upload, delete
    ):
        target_id = make_document()
        other_id = make_document()
        target_file = upload(target_id, PDF_BYTES, "target.pdf").json()["id"]
        other_file = upload(other_id, JPEG_BYTES, "other.jpg").json()["id"]
        set_status(db, other_id, "verified")

        other_row = snapshot(db.get(File, other_file))
        other_key = other_row["storage_key"]
        other_status = status_of(db, other_id)
        other_events = event_tuples(events_of(db, other_id))
        db.rollback()

        assert delete(target_id, target_file).status_code == 204

        assert snapshot(db.get(File, other_file)) == other_row
        assert storage.exists(other_key)
        assert status_of(db, other_id) == other_status
        assert event_tuples(events_of(db, other_id)) == other_events
        assert db.get(Document, target_id) is not None


# --------------------------------------------------------------------------- #
# 17: mid-transaction refusals
# --------------------------------------------------------------------------- #


class TestConflicts:
    def test_an_open_transaction_is_a_409(
        self, client, db, make_document, upload
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        db.execute(select(Document.id).limit(1))  # leave a transaction open

        response = client.delete(f"/documents/{document_id}/files/{file_id}")

        assert response.status_code == 409
        assert response.json() == {
            "detail": "The request conflicts with the current transaction state"
        }
        db.rollback()
        assert db.get(File, file_id) is not None

    @pytest.mark.parametrize(
        ("error", "detail"),
        [
            (
                TransactionAlreadyOpenError("open"),
                "The request conflicts with the current transaction state",
            ),
            (
                PendingDocumentChangesError(1),
                "The document has uncommitted changes",
            ),
        ],
    )
    def test_both_conflict_errors_map_to_409(
        self, client, override_service, error, detail
    ):
        service = RaisingService(error)
        override_service(service)

        response = client.delete("/documents/1/files/2")

        assert response.status_code == 409
        assert response.json() == {"detail": detail}
        assert service.calls == [(1, 2)]


# --------------------------------------------------------------------------- #
# 18-20: transaction outcomes and the physical delete
# --------------------------------------------------------------------------- #


class TestTransactionOutcomes:
    def test_a_refused_commit_keeps_the_row_and_the_blob(
        self, db, storage, make_document, upload, delete, monkeypatch
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        storage_key = key_of(db, file_id)
        set_status(db, document_id, "verified")

        def refuse(*args, **kwargs):
            raise OperationalError("COMMIT", {}, Exception("connection lost"))

        monkeypatch.setattr(Session, "commit", refuse)

        response = delete(document_id, file_id)

        assert response.status_code == 500
        assert db.get(File, file_id) is not None
        assert storage.exists(storage_key)
        assert status_of(db, document_id) == "verified"
        assert events_of(db, document_id) == []

    def test_an_unknown_commit_outcome_keeps_the_blob(
        self, db, storage, make_document, upload, delete, monkeypatch, caplog
    ):
        """The commit lands, then the driver reports failure.

        The row is gone, so the operation did happen, but the caller cannot know
        that. The response is `500` and the blob is deliberately kept: deleting
        it for a row that might still exist is the unrecoverable direction.
        """
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        storage_key = key_of(db, file_id)
        set_status(db, document_id, "verified")

        original = Session.commit

        def commit_then_fail(self):
            original(self)
            raise OperationalError("COMMIT", {}, Exception("connection lost"))

        monkeypatch.setattr(Session, "commit", commit_then_fail)
        caplog.set_level(logging.ERROR, logger="app.services.file_service")

        response = delete(document_id, file_id)

        assert response.status_code == 500
        assert db.get(File, file_id) is None
        assert storage.exists(storage_key)
        categories = [
            getattr(record, "failure_category", None)
            for record in caplog.records
            if getattr(record, "operation", None) == "file.detach"
        ]
        assert "unknown_commit_outcome" in categories

    def test_a_failed_blob_removal_still_answers_204(
        self, db, storage, make_document, upload, delete, override_service, caplog
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        storage_key = key_of(db, file_id)

        service = FileService(
            db,
            FailingDeleteStorage(storage.root_path),
            max_upload_size_bytes=MAX_BYTES,
        )
        override_service(service)
        caplog.set_level(logging.ERROR, logger="app.services.file_service")

        response = delete(document_id, file_id)

        assert response.status_code == 204
        assert response.content == b""
        assert db.get(File, file_id) is None
        assert storage.exists(storage_key)
        categories = [
            getattr(record, "failure_category", None)
            for record in caplog.records
            if getattr(record, "operation", None) == "file.detach"
        ]
        assert categories == ["blob_removal_failed"]


# --------------------------------------------------------------------------- #
# 21: what a failure response may not say
# --------------------------------------------------------------------------- #


class TestResponseHygiene:
    def test_a_500_reveals_no_storage_path_or_traceback(
        self, db, storage, make_document, upload, delete, monkeypatch
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        storage_key = key_of(db, file_id)

        def refuse(*args, **kwargs):
            raise OperationalError(
                "COMMIT", {}, Exception("connection lost at /srv/pg/data")
            )

        monkeypatch.setattr(Session, "commit", refuse)

        response = delete(document_id, file_id)

        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert storage_key not in response.text
        assert str(storage.root_path) not in response.text
        assert "/srv/pg/data" not in response.text
        assert "SELECT" not in response.text.upper()
        assert "Traceback" not in response.text

    def test_a_404_carries_only_the_detail(
        self, make_document, upload, delete
    ):
        owner_id = make_document()
        file_id = upload(owner_id, PDF_BYTES, "passport.pdf").json()["id"]

        response = delete(owner_id, file_id + 1)

        assert response.status_code == 404
        assert set(response.json()) == {"detail"}
        assert response.headers["content-type"].startswith("application/json")

    def test_no_response_header_names_the_blob(
        self, make_document, upload, delete, db
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        storage_key = key_of(db, file_id)

        response = delete(document_id, file_id)

        assert all(storage_key not in value for value in response.headers.values())


# --------------------------------------------------------------------------- #
# 22-25: OpenAPI, neighbours, and what the router must not do
# --------------------------------------------------------------------------- #


class TestOpenApiAndNeighbours:
    def test_openapi_documents_the_delete(self):
        schema = app.openapi()
        path = "/documents/{document_id}/files/{file_id}"

        assert set(schema["paths"][path]) == {"get", "delete"}
        delete = schema["paths"][path]["delete"]
        assert "204" in delete["responses"]
        assert "content" not in delete["responses"]["204"]

    def test_the_documented_surface_grew_by_one_operation(self):
        schema = app.openapi()

        assert len(schema["paths"]) == 18
        assert sum(len(item) for item in schema["paths"].values()) == 32
        assert set(
            schema["paths"]["/documents/{document_id}/files/{file_id}/content"]
        ) == {"get"}

    def test_list_metadata_upload_and_download_still_work(
        self, client, db, make_document, upload, download, delete
    ):
        document_id = make_document()
        first = upload(document_id, PDF_BYTES, "one.pdf").json()
        second = upload(document_id, JPEG_BYTES, "two.jpg").json()
        db.rollback()

        listing = client.get(f"/documents/{document_id}/files")
        assert [item["id"] for item in listing.json()] == [
            first["id"],
            second["id"],
        ]
        assert client.get(
            f"/documents/{document_id}/files/{first['id']}"
        ).json()["original_filename"] == "one.pdf"
        assert download(document_id, first["id"]).content == PDF_BYTES

        assert delete(document_id, first["id"]).status_code == 204

        assert [
            item["id"] for item in client.get(
                f"/documents/{document_id}/files"
            ).json()
        ] == [second["id"]]

    def test_the_whole_lifecycle_in_one_sequence(
        self, client, db, make_document, upload, download, delete
    ):
        document_id = make_document()

        created = upload(document_id, PDF_BYTES, "passport.pdf")
        assert created.status_code == 201
        file_id = created.json()["id"]

        listing = client.get(f"/documents/{document_id}/files")
        assert [item["id"] for item in listing.json()] == [file_id]

        metadata = client.get(f"/documents/{document_id}/files/{file_id}")
        assert metadata.status_code == 200
        assert metadata.json()["original_filename"] == "passport.pdf"

        content = download(document_id, file_id)
        assert content.status_code == 200
        assert content.content == PDF_BYTES

        removed = delete(document_id, file_id)
        assert removed.status_code == 204
        assert removed.content == b""

        assert client.get(f"/documents/{document_id}/files").json() == []
        assert client.get(
            f"/documents/{document_id}/files/{file_id}"
        ).status_code == 404
        assert download(document_id, file_id).status_code == 404

    def test_the_router_runs_no_sql_of_its_own(
        self, client, db, engine, override_service
    ):
        service = RecordingService()
        override_service(service)
        db.rollback()

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            response = client.delete("/documents/1/files/2")
        finally:
            event.remove(engine, "before_cursor_execute", record)

        assert response.status_code == 204
        assert service.calls == [(1, 2)]
        assert statements == []

    def test_the_router_neither_commits_nor_rolls_back(
        self, client, db, override_service, monkeypatch
    ):
        service = RecordingService()
        override_service(service)
        db.rollback()

        def forbidden(*args, **kwargs):
            raise AssertionError("the delete route must not end a transaction")

        monkeypatch.setattr(Session, "commit", forbidden)
        monkeypatch.setattr(Session, "rollback", forbidden)

        response = client.delete("/documents/1/files/2")

        assert response.status_code == 204
        assert service.calls == [(1, 2)]
