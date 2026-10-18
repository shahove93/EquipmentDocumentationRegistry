"""End-to-end HTTP checks across all five attachment operations.

The per-route modules pin each endpoint's own contract. This module walks the
sequence a client actually performs — upload three formats, list, read metadata,
download, delete one, delete the rest — and checks the cross-route invariants
that only appear when the operations are used together: the list shrinks, the
other blobs stay readable, verdicts reopen exactly once, and no response ever
names a storage key.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.document_types.schemas import DocumentTypeCreate
from app.api.documents.schemas import DocumentCreate
from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app
from app.models.document import Document
from app.models.document_verification_event import DocumentVerificationEvent
from app.models.file import File
from app.services.document_service import DocumentService
from app.services.document_type_service import DocumentTypeService

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
UNSUPPORTED_BYTES = b"PK\x03\x04 this is a zip, not an allowed type"

FORMATS = [
    (PDF_BYTES, "passport.pdf", "application/pdf", "application/pdf"),
    (JPEG_BYTES, "photo.jpg", "image/jpeg", "image/jpeg"),
    (PNG_BYTES, "scan.png", "image/png", "image/png"),
]


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
    def _delete(document_id: int, file_id: int, *, reset: bool = True):
        if reset:
            db.rollback()
        return client.delete(f"/documents/{document_id}/files/{file_id}")

    return _delete


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


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


def set_status(db, document_id: int, value: str) -> None:
    document = db.get(Document, document_id)
    assert document is not None
    document.verification_status = value
    db.commit()
    db.rollback()


# --------------------------------------------------------------------------- #
# the full sequence
# --------------------------------------------------------------------------- #


class TestFiveOperations:
    def test_upload_list_read_download_and_delete_three_formats(
        self, client, db, make_document, upload, download, delete
    ):
        document_id = make_document()
        created = []
        for content, filename, declared, expected_mime in FORMATS:
            response = upload(document_id, content, filename, declared)
            assert response.status_code == 201
            body = response.json()
            assert body["mime_type"] == expected_mime
            assert body["original_filename"] == filename
            assert body["size_bytes"] == len(content)
            assert "storage_key" not in body
            created.append((body, content, expected_mime))

        listing = client.get(f"/documents/{document_id}/files")
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()] == [
            body["id"] for body, _, _ in created
        ]
        assert all("storage_key" not in item for item in listing.json())

        for body, content, expected_mime in created:
            file_id = body["id"]
            metadata = client.get(f"/documents/{document_id}/files/{file_id}")
            assert metadata.status_code == 200
            assert metadata.json() == body
            assert "storage_key" not in metadata.json()

            downloaded = download(document_id, file_id)
            assert downloaded.status_code == 200
            assert downloaded.content == content
            assert downloaded.headers["content-type"] == expected_mime
            assert downloaded.headers["content-disposition"].startswith(
                "attachment; filename="
            )

        # Remove the middle one: the neighbours must stay readable.
        removed, removed_bytes, _ = created[1]
        assert delete(document_id, removed["id"]).status_code == 204

        remaining = client.get(f"/documents/{document_id}/files").json()
        assert [item["id"] for item in remaining] == [
            created[0][0]["id"],
            created[2][0]["id"],
        ]
        assert download(document_id, created[0][0]["id"]).content == PDF_BYTES
        assert download(document_id, created[2][0]["id"]).content == PNG_BYTES
        assert client.get(
            f"/documents/{document_id}/files/{removed['id']}"
        ).status_code == 404
        assert download(document_id, removed["id"]).status_code == 404

        # Remove the last two: the list ends empty, not missing.
        assert delete(document_id, created[0][0]["id"]).status_code == 204
        assert delete(document_id, created[2][0]["id"]).status_code == 204
        assert client.get(f"/documents/{document_id}/files").json() == []

        repeat = delete(document_id, created[0][0]["id"])
        assert repeat.status_code == 404
        assert repeat.json() == {
            "detail": (
                f"File {created[0][0]['id']} not found for document "
                f"{document_id}"
            )
        }

    def test_a_russian_name_is_an_attachment_with_a_utf8_form(
        self, make_document, upload, download
    ):
        document_id = make_document()
        file_id = upload(document_id, PDF_BYTES, "паспорт.pdf").json()["id"]

        response = download(document_id, file_id)

        header = response.headers["content-disposition"]
        assert 'filename="???????.pdf"' in header
        assert "filename*=UTF-8''%D0%BF%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%82.pdf" in header


# --------------------------------------------------------------------------- #
# verdicts across the sequence
# --------------------------------------------------------------------------- #


class TestVerdictsAcrossTheSequence:
    @pytest.mark.parametrize("verdict", ["verified", "rejected"])
    def test_deleting_attachments_reopens_once(
        self, db, make_document, upload, delete, verdict
    ):
        document_id = make_document()
        first = upload(document_id, PDF_BYTES, "one.pdf").json()["id"]
        second = upload(document_id, JPEG_BYTES, "two.jpg").json()["id"]
        third = upload(document_id, PNG_BYTES, "three.png").json()["id"]
        set_status(db, document_id, verdict)

        assert delete(document_id, second).status_code == 204
        assert status_of(db, document_id) == "pending"
        assert event_tuples(events_of(db, document_id)) == [
            (verdict, "pending", "reopened", "file_deleted")
        ]

        assert delete(document_id, first).status_code == 204
        assert delete(document_id, third).status_code == 204
        assert status_of(db, document_id) == "pending"
        assert event_tuples(events_of(db, document_id)) == [
            (verdict, "pending", "reopened", "file_deleted")
        ]

    def test_neighbouring_documents_keep_their_verdict_and_files(
        self, client, db, make_document, upload, download, delete
    ):
        target_id = make_document()
        neighbour_id = make_document()
        target_file = upload(target_id, PDF_BYTES, "target.pdf").json()["id"]
        neighbour_file = upload(
            neighbour_id, JPEG_BYTES, "neighbour.jpg"
        ).json()["id"]
        set_status(db, neighbour_id, "verified")

        assert delete(target_id, target_file).status_code == 204

        assert status_of(db, neighbour_id) == "verified"
        assert events_of(db, neighbour_id) == []
        assert download(neighbour_id, neighbour_file).content == JPEG_BYTES
        assert [
            item["id"]
            for item in client.get(f"/documents/{neighbour_id}/files").json()
        ] == [neighbour_file]


# --------------------------------------------------------------------------- #
# the contract seen as a whole
# --------------------------------------------------------------------------- #


class TestContractAsAWhole:
    def test_exactly_five_file_operations_are_documented(self):
        paths = app.openapi()["paths"]
        file_paths = {
            path: set(item) for path, item in paths.items() if "/files" in path
        }

        assert file_paths == {
            "/documents/{document_id}/files": {"get", "post"},
            "/documents/{document_id}/files/{file_id}": {"get", "delete"},
            "/documents/{document_id}/files/{file_id}/content": {"get"},
        }
        assert sum(len(item) for item in file_paths.values()) == 5

    def test_file_out_never_exposes_the_storage_key(self):
        component = app.openapi()["components"]["schemas"]["FileOut"]

        assert "storage_key" not in component["properties"]
        assert component["properties"]["original_filename"]["type"] == "string"

    def test_the_seven_status_codes_are_all_reachable(
        self, client, db, make_document, upload, download, delete
    ):
        document_id = make_document()
        created = upload(document_id)
        assert created.status_code == 201

        assert download(document_id, created.json()["id"]).status_code == 200

        assert upload(
            document_id, PDF_BYTES + b"x" * (MAX_BYTES + 1)
        ).status_code == 413
        assert upload(
            document_id, UNSUPPORTED_BYTES, "archive.zip", "application/zip"
        ).status_code == 422
        assert delete(document_id, 999999).status_code == 404

        # 409 needs a session that arrives mid-transaction, on both writes.
        db.execute(select(Document.id).limit(1))
        assert client.delete(
            f"/documents/{document_id}/files/{created.json()['id']}"
        ).status_code == 409
        db.rollback()
        db.execute(select(Document.id).limit(1))
        assert client.post(
            f"/documents/{document_id}/files",
            files={"file": ("x.pdf", PDF_BYTES, "application/pdf")},
        ).status_code == 409
        db.rollback()

        assert delete(document_id, created.json()["id"]).status_code == 204

    def test_a_missing_blob_is_a_safe_500_and_metadata_still_answers(
        self, client, db, storage, make_document, upload, download
    ):
        """The decision to carry into ADR-009: a row without a blob is not 404."""
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        row = db.get(File, file_id)
        storage_key = row.storage_key
        db.rollback()
        storage.delete(storage_key)

        response = download(document_id, file_id)

        assert response.status_code == 500
        assert response.json() == {
            "detail": "Stored file content is unavailable"
        }
        assert storage_key not in response.text
        assert str(storage.root_path) not in response.text
        assert client.get(
            f"/documents/{document_id}/files/{file_id}"
        ).status_code == 200

    def test_no_error_response_names_sql_a_path_or_the_blob(
        self, db, storage, make_document, upload, download, delete
    ):
        document_id = make_document()
        file_id = upload(document_id).json()["id"]
        row = db.get(File, file_id)
        storage_key = row.storage_key
        db.rollback()
        storage.delete(storage_key)

        for response in (
            download(document_id, file_id),
            download(document_id, file_id + 1),
            delete(document_id, file_id + 1),
        ):
            assert storage_key not in response.text
            assert str(storage.root_path) not in response.text
            assert "SELECT" not in response.text.upper()
            assert "Traceback" not in response.text
