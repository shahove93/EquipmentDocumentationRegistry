"""HTTP tests for `POST /documents/{document_id}/files`.

The route is a thin adapter: every rule about what may be attached, how the
document's verdict is withdrawn and what happens when storage or the commit
fails lives in `FileService`. These tests therefore check the adapter's own
responsibilities — status codes, the response body, and the fact that it adds
no transaction, no SQL and no file handling of its own — against the real
service and a temporary storage root.
"""

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

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
from app.services.file_service import FileService
from app.services.local_storage import LocalStorageBackend
from app.services.storage import StorageError

DATABASE_URL = "postgresql+psycopg://edr@127.0.0.1:5432/postgres"
MAX_BYTES = 4096
_MISSING = object()

# Minimal but genuine files: the service decides the type from these signatures,
# so random bytes would be refused before reaching any of the logic under test.
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
UNSUPPORTED_BYTES = b"PK\x03\x04 this is a zip, not an allowed type"

PUBLIC_FIELDS = {
    "id",
    "document_id",
    "original_filename",
    "mime_type",
    "size_bytes",
    "sha256",
    "uploaded_at",
}


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def settings(storage) -> Settings:
    """Settings rooted in the per-test storage directory.

    The size limit is deliberately small so the "too large" case stays cheap.
    """
    return Settings(
        DATABASE_URL=DATABASE_URL,
        STORAGE_ROOT=str(storage.root_path),
        MAX_UPLOAD_SIZE_BYTES=MAX_BYTES,
    )


@pytest.fixture
def client(db, settings):
    """TestClient over the isolated schema and the temporary storage root.

    `raise_server_exceptions=False` is required by the failure tests: an
    uncaught storage or commit error must be observed as the framework's `500`,
    which is exactly what a client would see.
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
    """Create a document and return its id, with the session left idle.

    An id is returned rather than the row on purpose: every upload must start on
    a session with **no** transaction, because `attach` refuses one that already
    has it. `DocumentService.create` refreshes the row after its commit, which
    opens a read transaction, so the fixture ends with a rollback — matching the
    fresh session a real request gets from `get_db`. Reading the id first keeps
    the rollback from expiring the value the test needs.
    """

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
    """POST a file as multipart, after putting the session back into the state
    a fresh request would find it in."""

    def _upload(
        document_id: int,
        content: bytes = PDF_BYTES,
        filename: str = "scan.pdf",
        content_type: str = "application/pdf",
        *,
        reset: bool = True,
    ):
        if reset:
            db.rollback()
        return client.post(
            f"/documents/{document_id}/files",
            files={"file": (filename, content, content_type)},
        )

    return _upload


@pytest.fixture
def override_service(client):
    """Replace the assembled service for failure injection, then put it back."""

    def _override(service: FileService) -> None:
        app.dependency_overrides[get_file_service] = lambda: service

    yield _override
    app.dependency_overrides.pop(get_file_service, None)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def files_on_disk(storage: LocalStorageBackend) -> list:
    root = storage.root_path
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def storage_keys_on_disk(storage: LocalStorageBackend) -> list[str]:
    return [
        path.relative_to(storage.root_path).as_posix()
        for path in files_on_disk(storage)
    ]


def file_rows(db, document_id: int) -> list[File]:
    return list(
        db.scalars(select(File).where(File.document_id == document_id).order_by(File.id))
    )


def events_of(db, document_id: int) -> list[DocumentVerificationEvent]:
    return list(
        db.scalars(
            select(DocumentVerificationEvent)
            .where(DocumentVerificationEvent.document_id == document_id)
            .order_by(DocumentVerificationEvent.id)
        )
    )


def status_of(db, document_id: int) -> str:
    document = db.get(Document, document_id)
    assert document is not None
    return document.verification_status


# --------------------------------------------------------------------------- #
# 1-10: success, shape, storage, hashing
# --------------------------------------------------------------------------- #


class TestAcceptedTypes:
    @pytest.mark.parametrize(
        ("content", "filename", "declared", "expected_mime", "expected_ext"),
        [
            (PDF_BYTES, "passport.pdf", "application/pdf", "application/pdf", "pdf"),
            (JPEG_BYTES, "photo.jpg", "image/jpeg", "image/jpeg", "jpg"),
            (PNG_BYTES, "scan.png", "image/png", "image/png", "png"),
        ],
    )
    def test_pdf_jpeg_and_png_are_accepted(
        self, upload, storage, make_document, content, filename, declared,
        expected_mime, expected_ext,
    ):
        document_id = make_document()

        response = upload(document_id, content, filename, declared)

        assert response.status_code == 201
        body = response.json()
        assert body["mime_type"] == expected_mime
        key = storage_keys_on_disk(storage)[0]
        assert key.endswith(f".{expected_ext}")

    def test_the_type_comes_from_the_signature_not_the_declared_type(
        self, upload, make_document
    ):
        document_id = make_document()

        response = upload(
            document_id, PDF_BYTES, "mislabelled.png", "image/png"
        )

        assert response.status_code == 201
        assert response.json()["mime_type"] == "application/pdf"

    def test_a_pdf_named_like_a_zip_is_still_a_pdf(self, upload, make_document):
        document_id = make_document()

        response = upload(document_id, PDF_BYTES, "archive.zip", "application/zip")

        assert response.status_code == 201
        assert response.json()["mime_type"] == "application/pdf"


class TestResponseShape:
    def test_response_has_exactly_the_seven_public_fields(
        self, upload, make_document
    ):
        document_id = make_document()

        body = upload(document_id).json()

        assert set(body) == PUBLIC_FIELDS

    def test_the_metadata_is_correct(self, upload, make_document):
        document_id = make_document()

        body = upload(
            document_id,
            PDF_BYTES,
            "passport.pdf",
            "application/pdf",
        ).json()

        assert body["document_id"] == document_id
        assert body["original_filename"] == "passport.pdf"
        assert body["mime_type"] == "application/pdf"
        assert body["size_bytes"] == len(PDF_BYTES)
        assert body["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
        assert isinstance(body["id"], int)

    @pytest.mark.parametrize("content", [PDF_BYTES, JPEG_BYTES, PNG_BYTES])
    def test_sha256_is_the_digest_of_the_uploaded_bytes(
        self, upload, make_document, content
    ):
        document_id = make_document()

        body = upload(document_id, content).json()

        assert body["sha256"] == hashlib.sha256(content).hexdigest()

    @pytest.mark.parametrize("content", [PDF_BYTES, JPEG_BYTES, PNG_BYTES])
    def test_size_is_the_length_of_the_uploaded_bytes(
        self, upload, make_document, content
    ):
        document_id = make_document()

        body = upload(document_id, content).json()

        assert body["size_bytes"] == len(content)

    def test_location_points_at_the_metadata_route(self, upload, make_document):
        document_id = make_document()

        response = upload(document_id)

        file_id = response.json()["id"]
        assert response.headers["location"].endswith(
            f"/documents/{document_id}/files/{file_id}"
        )


class TestNoInternalFields:
    def test_no_storage_key_in_the_response(self, upload, storage, make_document):
        document_id = make_document()

        response = upload(document_id)

        text = response.text
        assert "storage_key" not in text
        for key in storage_keys_on_disk(storage):
            assert key not in text

    def test_no_storage_key_in_openapi(self):
        spec = app.openapi()
        assert "storage_key" not in spec["components"]["schemas"]["FileOut"]["properties"]
        assert "storage_key" not in str(spec["paths"]["/documents/{document_id}/files"])


class TestStorage:
    def test_the_blob_is_written_under_the_storage_root(
        self, upload, storage, make_document
    ):
        document_id = make_document()

        response = upload(document_id)

        assert response.status_code == 201
        keys = storage_keys_on_disk(storage)
        assert len(keys) == 1
        assert keys[0].startswith(f"documents/{document_id}/")

    def test_the_stored_bytes_are_the_uploaded_bytes(
        self, upload, storage, make_document
    ):
        document_id = make_document()

        upload(document_id, PDF_BYTES)

        key = storage_keys_on_disk(storage)[0]
        assert (storage.root_path / key).read_bytes() == PDF_BYTES

    def test_the_file_is_closed_after_the_response(
        self, upload, db, make_document, monkeypatch
    ):
        captured = {}
        original = FileService.attach

        def spy(self, document_id, original_filename, source):
            captured["source"] = source
            return original(self, document_id, original_filename, source)

        monkeypatch.setattr(FileService, "attach", spy)
        document_id = make_document()

        response = upload(document_id)

        assert response.status_code == 201
        assert captured["source"].closed is True


class TestVisibleThroughTheReadRoutes:
    def test_the_new_file_appears_in_the_list(
        self, upload, client, db, make_document
    ):
        document_id = make_document()
        created = upload(document_id).json()

        db.rollback()
        response = client.get(f"/documents/{document_id}/files")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [created["id"]]

    def test_the_metadata_route_returns_the_new_file(
        self, upload, client, db, make_document
    ):
        document_id = make_document()
        created = upload(document_id).json()

        db.rollback()
        response = client.get(f"/documents/{document_id}/files/{created['id']}")

        assert response.status_code == 200
        assert response.json() == created


# --------------------------------------------------------------------------- #
# 11-15: request errors
# --------------------------------------------------------------------------- #


class TestMissingDocument:
    def test_returns_404(self, upload):
        response = upload(999999)

        assert response.status_code == 404
        assert response.json() == {"detail": "Document 999999 not found"}

    def test_leaves_no_row_and_no_blob(self, upload, db, storage):
        upload(999999)

        db.rollback()
        assert db.scalar(select(func.count()).select_from(File)) == 0
        assert files_on_disk(storage) == []


class TestTooLarge:
    def test_returns_413(self, upload, make_document):
        document_id = make_document()

        response = upload(document_id, PDF_BYTES + b"x" * (MAX_BYTES + 1))

        assert response.status_code == 413
        assert "maximum upload size" in response.json()["detail"]

    def test_leaves_no_row_no_blob_and_no_event(self, upload, db, storage, make_document):
        document_id = make_document()

        upload(document_id, PDF_BYTES + b"x" * (MAX_BYTES + 1))

        db.rollback()
        assert file_rows(db, document_id) == []
        assert events_of(db, document_id) == []
        assert status_of(db, document_id) == "pending"
        assert files_on_disk(storage) == []

    def test_a_file_at_the_limit_is_accepted(self, upload, make_document):
        document_id = make_document()
        body = b"%PDF-1.4" + b"x" * (MAX_BYTES - len(b"%PDF-1.4"))

        response = upload(document_id, body)

        assert response.status_code == 201
        assert response.json()["size_bytes"] == MAX_BYTES


class TestUnsupported:
    def test_returns_422(self, upload, make_document):
        document_id = make_document()

        response = upload(
            document_id, UNSUPPORTED_BYTES, "a.pdf", "application/pdf"
        )

        assert response.status_code == 422
        assert "unsupported" in response.json()["detail"]

    def test_leaves_nothing(self, upload, db, storage, make_document):
        document_id = make_document()

        upload(document_id, UNSUPPORTED_BYTES, "a.pdf", "application/pdf")

        db.rollback()
        assert file_rows(db, document_id) == []
        assert files_on_disk(storage) == []


class TestEmpty:
    def test_returns_422(self, upload, make_document):
        document_id = make_document()

        response = upload(document_id, b"")

        assert response.status_code == 422
        assert response.json() == {"detail": "file is empty"}

    def test_leaves_nothing(self, upload, db, storage, make_document):
        document_id = make_document()

        upload(document_id, b"")

        db.rollback()
        assert file_rows(db, document_id) == []
        assert files_on_disk(storage) == []


class TestMissingField:
    def test_returns_422_and_names_the_field(self, client, db, make_document):
        document_id = make_document()
        db.rollback()

        response = client.post(f"/documents/{document_id}/files")

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail[0]["loc"] == ["body", "file"]
        assert detail[0]["type"] == "missing"

    def test_leaves_nothing(self, client, db, storage, make_document):
        document_id = make_document()
        db.rollback()

        client.post(f"/documents/{document_id}/files")

        db.rollback()
        assert file_rows(db, document_id) == []
        assert files_on_disk(storage) == []


class TestTransactionConflict:
    def test_an_open_transaction_returns_409(self, client, db, make_document):
        document_id = make_document()
        # Deliberately leave a transaction open, which is what a shared session
        # looks like to `attach`.
        db.execute(select(Document.id).where(Document.id == document_id))

        response = client.post(
            f"/documents/{document_id}/files",
            files={"file": ("scan.pdf", PDF_BYTES, "application/pdf")},
        )

        assert response.status_code == 409
        assert "transaction" in response.json()["detail"].lower()

    def test_a_conflict_leaves_nothing(self, client, db, storage, make_document):
        document_id = make_document()
        db.execute(select(Document.id).where(Document.id == document_id))

        client.post(
            f"/documents/{document_id}/files",
            files={"file": ("scan.pdf", PDF_BYTES, "application/pdf")},
        )

        db.rollback()
        assert file_rows(db, document_id) == []
        assert files_on_disk(storage) == []


# --------------------------------------------------------------------------- #
# 16-19: status and history
# --------------------------------------------------------------------------- #


class TestPendingDocument:
    def test_stays_pending(self, upload, db, make_document):
        document_id = make_document("pending")

        response = upload(document_id)

        assert response.status_code == 201
        db.rollback()
        assert status_of(db, document_id) == "pending"

    def test_gains_no_history_event(self, upload, db, make_document):
        document_id = make_document("pending")

        upload(document_id)

        db.rollback()
        assert events_of(db, document_id) == []


class TestVerifiedDocument:
    def test_returns_to_pending(self, upload, db, make_document):
        document_id = make_document("verified")

        response = upload(document_id)

        assert response.status_code == 201
        db.rollback()
        assert status_of(db, document_id) == "pending"

    def test_records_one_file_added_reopened_event(self, upload, db, make_document):
        document_id = make_document("verified")

        upload(document_id)

        db.rollback()
        events = events_of(db, document_id)
        assert len(events) == 1
        assert events[0].event_type == "reopened"
        assert events[0].reason == "file_added"
        assert events[0].from_status == "verified"
        assert events[0].to_status == "pending"


class TestRejectedDocument:
    def test_returns_to_pending(self, upload, db, make_document):
        document_id = make_document("rejected")

        response = upload(document_id)

        assert response.status_code == 201
        db.rollback()
        assert status_of(db, document_id) == "pending"

    def test_records_one_file_added_reopened_event(self, upload, db, make_document):
        document_id = make_document("rejected")

        upload(document_id)

        db.rollback()
        events = events_of(db, document_id)
        assert len(events) == 1
        assert events[0].event_type == "reopened"
        assert events[0].reason == "file_added"
        assert events[0].from_status == "rejected"
        assert events[0].to_status == "pending"


class TestRepeatedUpload:
    def test_a_second_upload_does_not_add_a_second_event(
        self, upload, db, make_document
    ):
        document_id = make_document("verified")

        first = upload(document_id)
        second = upload(document_id)

        assert first.status_code == 201
        assert second.status_code == 201
        db.rollback()
        events = events_of(db, document_id)
        assert len(events) == 1
        assert [event.reason for event in events] == ["file_added"]
        assert status_of(db, document_id) == "pending"
        assert len(file_rows(db, document_id)) == 2


class TestOtherDocuments:
    def test_an_upload_changes_only_its_own_document(
        self, upload, db, make_document
    ):
        mine = make_document("verified")
        other = make_document("verified")

        upload(mine)

        db.rollback()
        assert status_of(db, mine) == "pending"
        assert status_of(db, other) == "verified"
        assert file_rows(db, other) == []
        assert events_of(db, other) == []


# --------------------------------------------------------------------------- #
# 20-23: infrastructure failures
# --------------------------------------------------------------------------- #


class _SessionProxy:
    """Duck-typed stand-in for the request session.

    The service tests use the same shape: a wrapper that reports no transaction
    on entry and forwards everything to the real session, so the failure being
    simulated is the only thing that differs from a healthy request.
    """

    def __init__(self, inner) -> None:
        self._inner = inner

    def in_transaction(self) -> bool:
        return False

    def get(self, *args, **kwargs):
        return self._inner.get(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return self._inner.execute(*args, **kwargs)

    def scalar(self, *args, **kwargs):
        return self._inner.scalar(*args, **kwargs)

    def add(self, instance) -> None:
        self._inner.add(instance)

    def flush(self) -> None:
        self._inner.flush()

    def rollback(self) -> None:
        self._inner.rollback()


class CommitFails(_SessionProxy):
    def __init__(self, inner, error: Exception) -> None:
        super().__init__(inner)
        self._error = error

    def commit(self) -> None:
        raise self._error


class UnreadableOutcome(CommitFails):
    """The commit failed and the session cannot say whether it landed."""

    def scalar(self, *args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("connection is gone"))


class LandedThenReportedAsFailed(CommitFails):
    """The server accepted the transaction and only then did the client fail."""

    def commit(self) -> None:
        self._inner.commit()
        raise self._error


class ExplodingStorage(LocalStorageBackend):
    def save(self, storage_key, source) -> None:
        raise StorageError("disk is full")


class TestStorageFailure:
    def test_returns_500(self, upload, override_service, db, storage, make_document):
        override_service(
            FileService(
                _SessionProxy(db),
                ExplodingStorage(storage.root_path),
                MAX_BYTES,
            )
        )
        document_id = make_document()

        response = upload(document_id)

        assert response.status_code == 500

    def test_leaves_no_row_no_event_and_no_blob(
        self, upload, override_service, db, storage, make_document
    ):
        override_service(
            FileService(
                _SessionProxy(db),
                ExplodingStorage(storage.root_path),
                MAX_BYTES,
            )
        )
        document_id = make_document("verified")

        upload(document_id)

        db.rollback()
        assert file_rows(db, document_id) == []
        assert events_of(db, document_id) == []
        assert status_of(db, document_id) == "verified"
        assert files_on_disk(storage) == []


class TestCommitOutcomes:
    def test_a_confirmed_rollback_leaves_no_row_and_no_blob(
        self, upload, override_service, db, storage, make_document
    ):
        document_id = make_document()

        override_service(
            FileService(
                CommitFails(db, RuntimeError("commit refused")),
                LocalStorageBackend(storage.root_path),
                MAX_BYTES,
            )
        )
        response = upload(document_id, reset=False)

        assert response.status_code == 500
        db.rollback()
        assert file_rows(db, document_id) == []
        assert files_on_disk(storage) == []

    def test_an_unreadable_outcome_keeps_the_blob(self, upload, override_service, db, storage, make_document, caplog):
        document_id = make_document()

        override_service(
            FileService(
                UnreadableOutcome(db, RuntimeError("commit refused")),
                LocalStorageBackend(storage.root_path),
                MAX_BYTES,
            )
        )
        response = upload(document_id, reset=False)

        assert response.status_code == 500
        assert len(files_on_disk(storage)) == 1, (
            "an unknown commit outcome must never trigger a physical delete"
        )
        categories = [
            getattr(record, "failure_category", None) for record in caplog.records
        ]
        assert "unknown_commit_outcome" in categories

    def test_a_landed_commit_reported_as_failure_keeps_row_and_blob(
        self, upload, override_service, db, storage, make_document, caplog
    ):
        document_id = make_document("verified")

        override_service(
            FileService(
                LandedThenReportedAsFailed(db, RuntimeError("commit refused")),
                LocalStorageBackend(storage.root_path),
                MAX_BYTES,
            )
        )
        response = upload(document_id, reset=False)

        assert response.status_code == 500
        db.rollback()
        assert len(file_rows(db, document_id)) == 1
        assert status_of(db, document_id) == "pending"
        assert len(events_of(db, document_id)) == 1
        assert len(files_on_disk(storage)) == 1, (
            "a commit that landed must not have its blob deleted"
        )
        categories = [
            getattr(record, "failure_category", None) for record in caplog.records
        ]
        assert "commit_landed_despite_failure" in categories


# --------------------------------------------------------------------------- #
# 23: errors reveal nothing internal
# --------------------------------------------------------------------------- #


class TestErrorHygiene:
    @pytest.fixture
    def error_responses(self, upload, override_service, db, storage, make_document):
        document_id = make_document()
        responses = [
            upload(999999),
            upload(document_id, PDF_BYTES + b"x" * (MAX_BYTES + 1)),
            upload(document_id, UNSUPPORTED_BYTES),
            upload(document_id, b""),
        ]
        override_service(
            FileService(_SessionProxy(db), ExplodingStorage(storage.root_path))
        )
        responses.append(upload(document_id, reset=False))
        return responses

    def test_no_sql_or_traceback_in_any_error(self, error_responses):
        for response in error_responses:
            text = response.text.lower()
            assert "traceback" not in text
            assert "sqlalchemy" not in text
            assert "select " not in text
            assert "insert " not in text

    def test_no_storage_path_in_any_error(self, error_responses, storage):
        root = str(storage.root_path)
        for response in error_responses:
            assert root not in response.text
            assert "storage" not in response.text.lower()

    def test_statuses_are_the_documented_ones(self, error_responses):
        assert [response.status_code for response in error_responses] == [
            404,
            413,
            422,
            422,
            500,
        ]


# --------------------------------------------------------------------------- #
# 24-25: compatibility and OpenAPI
# --------------------------------------------------------------------------- #


class TestCompatibility:
    def test_health_is_unchanged(self, client):
        assert client.get("/health").json() == {"status": "ok"}

    def test_previous_collections_are_still_documented(self):
        paths = app.openapi()["paths"]
        for path in ("/issuers", "/manufacturers", "/products", "/document-types"):
            assert path in paths

    def test_the_read_routes_still_answer(self, client, db, make_document):
        document_id = make_document()
        db.rollback()

        assert client.get(f"/documents/{document_id}/files").status_code == 200
        assert client.get(f"/documents/{document_id}/files/999999").status_code == 404


class TestOpenApi:
    def test_there_is_exactly_one_file_post_route(self):
        paths = app.openapi()["paths"]
        posts = [path for path, item in paths.items() if "post" in item and "/files" in path]
        assert posts == ["/documents/{document_id}/files"]

    def test_it_accepts_multipart_with_a_required_file_field(self):
        operation = app.openapi()["paths"]["/documents/{document_id}/files"]["post"]
        content = operation["requestBody"]["content"]
        assert list(content) == ["multipart/form-data"]
        schema = content["multipart/form-data"]["schema"]
        name = schema["$ref"].rsplit("/", 1)[-1]
        component = app.openapi()["components"]["schemas"][name]
        assert component["required"] == ["file"]
        assert "file" in component["properties"]

    def test_it_documents_201(self):
        operation = app.openapi()["paths"]["/documents/{document_id}/files"]["post"]
        assert "201" in operation["responses"]
        schema = operation["responses"]["201"]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/FileOut"}

    def test_operation_count_includes_download_and_delete(self):
        paths = app.openapi()["paths"]
        operations = sum(
            len([m for m in item if m in ("get", "post", "put", "patch", "delete")])
            for item in paths.values()
        )
        assert operations == 38

    def test_the_download_and_delete_routes_are_both_documented(self):
        # TASK-DOC-005S added the download; TASK-DOC-005T added `DELETE
        # .../{file_id}`. The delete lives on the metadata path, so that path
        # carries two methods while `/content` stays read-only.
        paths = app.openapi()["paths"]
        assert set(paths["/documents/{document_id}/files/{file_id}"]) == {
            "get",
            "delete",
        }
        assert set(
            paths["/documents/{document_id}/files/{file_id}/content"]
        ) == {"get"}
